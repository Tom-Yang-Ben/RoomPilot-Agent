from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parent / "data" / "questionnaire_visual_catalog.json"
STATIC_ROOT = Path(__file__).resolve().parents[1] / "server" / "static"
ALLOWED_SELECTION_RULES = {"exclusive", "compatible", "weighted"}
ALLOWED_GENERATION_STATUSES = {"planned", "ready"}


class QuestionnaireCatalogError(ValueError):
    """The visual-questionnaire source does not satisfy its public contract."""


def _normalized_option(question: dict, option: dict, prompt_contract: dict) -> dict:
    image_id = option.get("image_id")
    generation_status = option.get("generation_status")
    if not image_id:
        raise QuestionnaireCatalogError(
            f"option must declare image_id: {question['question_id']}/{option.get('option_id')}"
        )
    if generation_status not in ALLOWED_GENERATION_STATUSES:
        raise QuestionnaireCatalogError(
            f"invalid generation_status: {question['question_id']}/{option.get('option_id')}"
        )
    image_path = f"questionnaire_images/{image_id}.png"
    return {
        "image_id": image_id,
        "question_id": question["question_id"],
        "space_type": question["space_type"],
        "option_id": option["option_id"],
        "label_zh": option["label_zh"],
        "image_path": image_path,
        "image_url": f"/static/{image_path}",
        "generation_status": generation_status,
        "image_sha256": option.get("image_sha256"),
        "watermark": "RoomPilot",
        "prompt_contract_id": prompt_contract["prompt_contract_id"],
        "visual_brief_zh": option["visual_brief_zh"],
        "rag_tags": option.get("rag_tags", []),
        "engine_effects": option.get("engine_effects", {}),
        "risk_triggers": question.get("risk_triggers", []),
    }


def _validate_catalog(catalog: dict, asset_root: Path) -> None:
    questions = catalog.get("questions")
    if not isinstance(questions, list):
        raise QuestionnaireCatalogError("questions must be a list")
    if len(questions) != int(catalog.get("question_count", -1)):
        raise QuestionnaireCatalogError("question_count does not match questions")

    question_ids: set[str] = set()
    image_ids: set[str] = set()
    for question in questions:
        question_id = question.get("question_id")
        if not question_id or question_id in question_ids:
            raise QuestionnaireCatalogError(f"duplicate question_id: {question_id}")
        question_ids.add(question_id)
        if question.get("selection_rule") not in ALLOWED_SELECTION_RULES:
            raise QuestionnaireCatalogError(f"invalid selection_rule: {question_id}")
        if question["selection_rule"] == "exclusive" and question.get("allow_both"):
            raise QuestionnaireCatalogError(f"exclusive question cannot allow both: {question_id}")
        if len(question.get("options", [])) != 2:
            raise QuestionnaireCatalogError(f"question must contain exactly two options: {question_id}")

        option_ids: set[str] = set()
        for option in question["options"]:
            option_id = option.get("option_id")
            if not option_id or option_id in option_ids:
                raise QuestionnaireCatalogError(f"duplicate option_id: {question_id}/{option_id}")
            option_ids.add(option_id)
            image_id = option.get("image_id")
            if not image_id or image_id in image_ids:
                raise QuestionnaireCatalogError(f"duplicate image_id: {image_id}")
            image_ids.add(image_id)
            if option.get("generation_status") == "ready":
                path = asset_root / option["image_path"]
                if not path.is_file():
                    raise QuestionnaireCatalogError(f"ready image is missing: {path}")
                expected_sha256 = option.get("image_sha256")
                if not expected_sha256:
                    raise QuestionnaireCatalogError(
                        f"ready image must declare image_sha256: {image_id}"
                    )
                actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual_sha256 != expected_sha256:
                    raise QuestionnaireCatalogError(
                        f"ready image checksum mismatch: {image_id}"
                    )

    if len(image_ids) != int(catalog.get("image_count", -1)):
        raise QuestionnaireCatalogError("image_count does not match options")


def load_questionnaire_visual_catalog(
    path: Path | None = None,
    *,
    asset_root: Path | None = None,
) -> dict:
    source_path = Path(path or CATALOG_PATH)
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    prompt_contract = raw["prompt_contract"]
    catalog = {
        "version": raw["version"],
        "notice_zh": raw["notice_zh"],
        "question_count": raw["question_count"],
        "image_count": raw["image_count"],
        "prompt_contract": deepcopy(prompt_contract),
        "questions": [],
    }
    for sequence, source_question in enumerate(raw["questions"], start=1):
        question = {
            "question_id": source_question["question_id"],
            "sequence": sequence,
            "space_type": source_question["space_type"],
            "title_zh": source_question["title_zh"],
            "purpose_zh": source_question["purpose_zh"],
            "selection_rule": source_question["selection_rule"],
            "allow_both": bool(source_question.get("allow_both", False)),
            "custom_input_example_zh": source_question["custom_input_example_zh"],
            "risk_triggers": source_question.get("risk_triggers", []),
        }
        question["options"] = [
            _normalized_option(question, option, prompt_contract)
            for option in source_question["options"]
        ]
        catalog["questions"].append(question)

    _validate_catalog(catalog, Path(asset_root or STATIC_ROOT))
    return catalog


class QuestionnaireVisualStore:
    """SQLite query index generated from the versioned questionnaire JSON."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS questionnaire_questions (
                    question_id TEXT PRIMARY KEY,
                    space_type TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    ready INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS questionnaire_images (
                    image_id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL,
                    option_id TEXT NOT NULL,
                    generation_status TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(question_id) REFERENCES questionnaire_questions(question_id)
                )
                """
            )

    def sync(self, catalog: dict) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM questionnaire_images")
            connection.execute("DELETE FROM questionnaire_questions")
            for question in catalog["questions"]:
                ready = all(
                    option["generation_status"] == "ready"
                    for option in question["options"]
                )
                connection.execute(
                    """
                    INSERT INTO questionnaire_questions (
                        question_id, space_type, sequence, ready, payload_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        question["question_id"],
                        question["space_type"],
                        question["sequence"],
                        int(ready),
                        json.dumps(question, ensure_ascii=False, sort_keys=True),
                    ),
                )
                for option in question["options"]:
                    connection.execute(
                        """
                        INSERT INTO questionnaire_images (
                            image_id, question_id, option_id, generation_status,
                            image_path, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            option["image_id"],
                            question["question_id"],
                            option["option_id"],
                            option["generation_status"],
                            option["image_path"],
                            json.dumps(option, ensure_ascii=False, sort_keys=True),
                        ),
                    )

    def list_questions(
        self,
        *,
        space_type: str | None = None,
        ready_only: bool = False,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []
        if space_type:
            clauses.append("space_type = ?")
            params.append(space_type)
        if ready_only:
            clauses.append("ready = 1")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM questionnaire_questions{where} ORDER BY sequence",
                params,
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def get_image(self, image_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM questionnaire_images WHERE image_id = ?",
                (image_id,),
            ).fetchone()
        if row is None:
            raise KeyError(image_id)
        return json.loads(row["payload_json"])
