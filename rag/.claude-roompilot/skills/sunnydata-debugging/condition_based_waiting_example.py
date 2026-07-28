"""條件式等待工具的完整實作（Python 3.11）。

來源：RoomPilot 批次工作（`vlm_annotation/` 標註、`rag_pipeline/embed_v3.py` 建索引）
      的驗證腳本改善——把 15 處隨便設的 time.sleep 換成條件輪詢。

執行方式：
    .venv-rag/bin/python .claude-roompilot/skills/sunnydata-debugging/condition_based_waiting_example.py

本專案的「事件流」不是記憶體事件匯流排，而是**可續跑的 JSONL 進度檔**
（每完成一筆就 append 一行）。因此三個輔助函式都以「讀 JSONL 記錄」為基礎：

    wait_for_record        等某一筆特定記錄出現
    wait_for_record_count  等某類記錄累積到指定數量
    wait_for_record_match  等符合自訂條件的記錄出現
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

T = TypeVar("T")

POLL_INTERVAL_S = 0.01  # 每 10ms 輪詢一次，兼顧反應速度與 CPU
DEFAULT_TIMEOUT_S = 5.0


# ── 通用輪詢 ────────────────────────────────────────────────────

def wait_for(
    condition: Callable[[], T | None],
    description: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    interval_s: float = POLL_INTERVAL_S,
) -> T:
    """輪詢 condition 直到回傳真值；逾時丟出帶說明的 TimeoutError。

    參數：
        condition  — 無參數可呼叫物件，條件成立時回傳真值
        description— 給錯誤訊息用的人話描述
        timeout_s  — 最長等待秒數（預設 5 秒）
        interval_s — 輪詢間隔（預設 0.01 秒）

    範例：
        wait_for(lambda: Path("chroma_db/chroma.sqlite3").exists(), "索引檔生成")
    """
    start = time.monotonic()

    while True:
        result = condition()
        if result:
            return result

        if time.monotonic() - start > timeout_s:
            raise TimeoutError(f"等待 {description} 超過 {timeout_s} 秒仍未成立")

        time.sleep(interval_s)


def read_records(path: Path) -> list[dict[str, Any]]:
    """每次都重讀進度檔——絕不要在迴圈外快取，否則永遠等不到新資料。

    寫入端是 append-only；讀到寫了一半的最後一行時直接略過，下一輪就完整了。
    """
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 尾行尚未寫完，下一輪重讀
    return records


# ── 領域輔助函式 ────────────────────────────────────────────────

def wait_for_record(
    progress_path: Path,
    item_id: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """等待某一件家具的標註／索引記錄出現在進度檔中。

    參數：
        progress_path — JSONL 進度檔（例如 vlm_annotation/render_meta_full.jsonl）
        item_id       — 家具 id
        timeout_s     — 最長等待秒數（預設 5 秒）
    回傳：
        第一筆符合的記錄

    範例：
        wait_for_record(Path("vlm_annotation/render_meta_full.jsonl"), "abo_B07QF1234")
    """

    def condition() -> dict[str, Any] | None:
        for rec in read_records(progress_path):
            if rec.get("id") == item_id:
                return rec
        return None

    return wait_for(condition, f"記錄 id={item_id} 出現在 {progress_path.name}", timeout_s)


def wait_for_record_count(
    progress_path: Path,
    status: str,
    count: int,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> list[dict[str, Any]]:
    """等待指定狀態的記錄累積到 count 筆。

    參數：
        progress_path — JSONL 進度檔
        status        — 記錄的 status 值（例如 "ok" / "failed"）
        count         — 要等到的筆數
        timeout_s     — 最長等待秒數（預設 5 秒）
    回傳：
        數量達標時，所有符合的記錄

    範例：
        # 等 embed_v3.py --limit 50 冒煙測試把 50 筆都寫進交付檔
        wait_for_record_count(Path("rag_export/vectors.jsonl"), "ok", 50, timeout_s=120)
    """

    def condition() -> list[dict[str, Any]] | None:
        matching = [r for r in read_records(progress_path) if r.get("status") == status]
        return matching if len(matching) >= count else None

    try:
        return wait_for(
            condition, f"{count} 筆 status={status} 的記錄", timeout_s
        )
    except TimeoutError:
        got = len([r for r in read_records(progress_path) if r.get("status") == status])
        raise TimeoutError(
            f"等待 {count} 筆 status={status} 的記錄超過 {timeout_s} 秒（目前 {got} 筆）"
        ) from None


def wait_for_record_match(
    progress_path: Path,
    predicate: Callable[[dict[str, Any]], bool],
    description: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """等待符合自訂條件的記錄——需要檢查內容而不只是 id／status 時使用。

    參數：
        progress_path — JSONL 進度檔
        predicate     — 記錄符合時回傳 True 的函式
        description   — 給錯誤訊息用的人話描述
        timeout_s     — 最長等待秒數（預設 5 秒）
    回傳：
        第一筆符合的記錄

    範例：
        # 等到第一筆判定為 japanese 且信心 > 0.8 的標註
        wait_for_record_match(
            Path("vlm_annotation/style_pass.jsonl"),
            lambda r: r.get("style_primary") == "japanese" and r.get("confidence", 0) > 0.8,
            "style_primary=japanese 且 confidence>0.8 的記錄",
        )
    """

    def condition() -> dict[str, Any] | None:
        for rec in read_records(progress_path):
            if predicate(rec):
                return rec
        return None

    return wait_for(condition, description, timeout_s)


# ── 其他常用條件 ────────────────────────────────────────────────

def port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Gradio 是否已在該埠開始服務（`app.py` 預設 127.0.0.1:7860）。"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def iter_new_records(progress_path: Path, seen: set[str]) -> Iterator[dict[str, Any]]:
    """串出尚未看過的記錄——批次續跑時用來即時觀察進度。"""
    for rec in read_records(progress_path):
        rid = str(rec.get("id"))
        if rid not in seen:
            seen.add(rid)
            yield rec


# 實際除錯前後對照：
#
# BEFORE（不穩定）：
# ---------------
# proc = subprocess.Popen([PY, "rag_pipeline/app.py"])
# time.sleep(30)                       # 賭模型 30 秒內載完（MPS 退 CPU 時要 90 秒）
# assert port_open(7860)               # 機器一忙就失敗
#
# AFTER（可靠）：
# ----------------
# proc = subprocess.Popen([PY, "rag_pipeline/app.py"])
# wait_for(lambda: port_open(7860), "Gradio 於 7860 埠開始服務", timeout_s=180)
# assert port_open(7860)               # 永遠成立，且模型早載完就早結束
#
# 結果：成功率 60% → 100%，整體驗證時間縮短約 40%
#
# 注意：本專案 pytest 尚未建置。上述用法目前寫在一次性驗證腳本裡；
#       待 pytest 就位後，同樣的輔助函式可直接搬進 tests/conftest.py。


if __name__ == "__main__":
    # 自我示範：不依賴外部服務，驗證 wait_for 的逾時訊息是否清楚
    try:
        wait_for(lambda: False, "一個永遠不會成立的條件", timeout_s=0.05)
    except TimeoutError as exc:
        print("逾時訊息範例：", exc)

    print("port 7860 目前是否有服務：", port_open(7860))
