from __future__ import annotations

import math
import re

from .knowledge import JsonEngineeringKnowledgeRepository
from .models import (
    ProjectSnapshot,
    QuantityResult,
    RetrievalResult,
    ScheduleResult,
    ScheduleTask,
)


def _task_id(room_id: str, work_item_code: str) -> str:
    raw = f"task-{room_id}-{work_item_code}".lower()
    return re.sub(r"[^a-z0-9-]+", "-", raw).strip("-")


class ScheduleService:
    """Use structured ProductivityRecord and TaskDependency only."""

    def __init__(
        self,
        knowledge: JsonEngineeringKnowledgeRepository,
        *,
        demo_mode: bool = False,
    ) -> None:
        self.knowledge = knowledge
        self.demo_mode = demo_mode

    def plan(
        self,
        snapshot: ProjectSnapshot,
        quantities: QuantityResult,
        retrieval: RetrievalResult,
    ) -> ScheduleResult:
        del snapshot, quantities
        productivity_by_code: dict[str, dict] = {}
        for item in self.knowledge.productivity_records():
            is_synthetic = item.get("is_synthetic") is True
            if is_synthetic and not self.demo_mode:
                continue
            if item.get("daily_productivity") is None:
                continue
            existing = productivity_by_code.get(item["work_item_code"])
            if existing is None or str(item.get("effective_date", "")) >= str(
                existing.get("effective_date", "")
            ):
                productivity_by_code[item["work_item_code"]] = item

        tasks: list[ScheduleTask] = []
        task_by_room_code: dict[tuple[str, str], ScheduleTask] = {}
        for room in retrieval.rooms:
            for work_item in room.work_items:
                record = productivity_by_code.get(work_item.work_item_code)
                if record:
                    daily = float(record["daily_productivity"])
                    crew = max(1, int(record.get("crew_count", 1)))
                    preparation_days = float(record.get("preparation_days", 0))
                    construction_days = float(
                        max(1, math.ceil(work_item.quantity / (daily * crew)))
                    )
                    waiting_days = float(record.get("waiting_days", 0))
                    total_days = (
                        preparation_days + construction_days + waiting_days
                    )
                    source = record.get("source")
                    confidence = record.get("confidence", "low")
                    status = "estimated"
                else:
                    daily = None
                    crew = None
                    preparation_days = 0.0
                    construction_days = None
                    waiting_days = 0.0
                    total_days = None
                    source = None
                    confidence = "low"
                    status = "productivity_data_missing"
                task = ScheduleTask(
                    task_id=_task_id(room.room_id, work_item.work_item_code),
                    room_id=room.room_id,
                    work_item_code=work_item.work_item_code,
                    name=work_item.name,
                    quantity=work_item.quantity,
                    unit=work_item.unit,
                    daily_productivity=daily,
                    crew_count=crew,
                    preparation_days=preparation_days,
                    construction_days=construction_days,
                    waiting_days=waiting_days,
                    total_days=total_days,
                    predecessor_task_ids=[],
                    start_day=None,
                    finish_day=None,
                    source=source,
                    confidence=confidence,
                    status=status,
                )
                tasks.append(task)
                task_by_room_code[(room.room_id, work_item.work_item_code)] = task

        lag_by_pair: dict[tuple[str, str], float] = {}
        for dependency in self.knowledge.task_dependencies():
            if dependency.get("dependency_type") != "finish_to_start":
                continue
            for (room_id, code), task in list(task_by_room_code.items()):
                if code != dependency.get("task_code"):
                    continue
                predecessor = task_by_room_code.get(
                    (room_id, dependency.get("predecessor_code"))
                )
                if predecessor is None:
                    continue
                task.predecessor_task_ids.append(predecessor.task_id)
                lag_by_pair[(task.task_id, predecessor.task_id)] = float(
                    dependency.get("lag_days", 0)
                )

        by_id = {task.task_id: task for task in tasks}
        unresolved = {task.task_id for task in tasks}
        while unresolved:
            progressed = False
            for task_id in list(unresolved):
                task = by_id[task_id]
                predecessors = [by_id[item] for item in task.predecessor_task_ids]
                if any(item.task_id in unresolved for item in predecessors):
                    continue
                if task.total_days is not None and all(
                    item.finish_day is not None for item in predecessors
                ):
                    start_day = 1.0
                    if predecessors:
                        start_day = max(
                            float(item.finish_day)
                            + lag_by_pair.get((task.task_id, item.task_id), 0)
                            + 1
                            for item in predecessors
                        )
                    task.start_day = round(start_day, 2)
                    task.finish_day = round(
                        start_day + task.total_days - 1,
                        2,
                    )
                unresolved.remove(task_id)
                progressed = True
            if progressed:
                continue
            for task_id in unresolved:
                task = by_id[task_id]
                task.status = "productivity_data_missing"
                task.start_day = None
                task.finish_day = None
            break

        known_finishes = [
            task.finish_day for task in tasks if task.finish_day is not None
        ]
        unknown_duration_count = sum(task.total_days is None for task in tasks)
        if self.demo_mode:
            disclaimer = (
                "示範資料，非正式工期。ROOMPILOT_DEMO_MODE=true，工期使用 DEMO_ONLY "
                "合成工率；實際工期由工班、材料交期與現場條件確認。"
            )
        else:
            disclaimer = (
                "正式模式只使用非合成 ProductivityRecord 與 TaskDependency；缺少工率時"
                "保留 productivity_data_missing，不由 LLM 補算。"
            )
        return ScheduleResult(
            tasks=tasks,
            estimated_total_days=(max(known_finishes) if known_finishes else None),
            unknown_duration_count=unknown_duration_count,
            disclaimer=disclaimer,
        )

