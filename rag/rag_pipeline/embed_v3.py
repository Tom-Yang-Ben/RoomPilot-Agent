"""furniture_enriched_v3.json → bge-m3 向量 → ChromaDB + rag_export/ 四個交付檔。

一次算向量、同時寫兩邊，保證 Chroma 內的向量與交給 SQL 的 jsonl 是同一批、同一個
text_hash，不會出現「demo 正常但 SQL 端結果不同」的情況。

用法：
    .venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50   # 冒煙測試
    .venv-rag/bin/python rag_pipeline/embed_v3.py              # 全量
    .venv-rag/bin/python rag_pipeline/embed_v3.py --device cpu # MPS 出問題時退回
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 模型已在本機快取；不設離線的話每次載入都會連 HF Hub 檢查更新，
# 未登入被限流時會乾等數分鐘。首次在新機器跑需 HF_HUB_OFFLINE=0 先下載。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

PROJ = Path(__file__).resolve().parent.parent
SRC = PROJ / "rag_dataset" / "furniture_enriched_v3.json"
EXPORT_DIR = PROJ / "rag_export"
CHROMA_DIR = PROJ / "chroma_db"

MODEL_NAME = "BAAI/bge-m3"
DIMENSION = 1024
MAX_SEQ_LEN = 512  # 文本中位 326 字（約 250–400 token），無需 bge-m3 預設的 8192
COLLECTION = "furniture_v3"
# json_adjustment/i_need_rag.md 指定的交付檔名與 ID 欄位名（舊規格 RAGSQL.md 用 furniture_id）
EMBEDDINGS_FILE = "furniture_embeddings_bge_m3.jsonl"
TZ8 = timezone(timedelta(hours=8))


def pick_device(requested: str) -> str:
    import torch

    if requested != "auto":
        return requested
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def fmt_eta(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只處理前 N 筆（冒煙測試）")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--device", default="auto", choices=["auto", "mps", "cpu", "cuda"])
    ap.add_argument("--skip-chroma", action="store_true")
    ap.add_argument("--only-changed", action="store_true",
                    help="只重算 text_hash 與既有 rag_export 不同的品項，其餘沿用舊向量")
    args = ap.parse_args()

    from sentence_transformers import SentenceTransformer

    src = json.loads(SRC.read_text(encoding="utf-8"))
    items = [i for i in src["items"] if i.get("rag_indexable")]
    skipped = [i for i in src["items"] if not i.get("rag_indexable")]
    if args.limit:
        items = items[: args.limit]

    # 增量模式：沿用 text_hash 未變者的舊向量，只重算變動的
    reused: dict = {}
    if args.only_changed:
        old_path = EXPORT_DIR / EMBEDDINGS_FILE
        if not old_path.exists():
            old_path = EXPORT_DIR / "furniture_embeddings.jsonl"  # 舊檔名的相容讀取
        if not old_path.exists():
            print("找不到既有 rag_export，改跑全量")
        else:
            with old_path.open(encoding="utf-8") as fh:
                for line in fh:
                    row = json.loads(line)
                    # 沿用的舊列會被原樣寫回，所以在這裡就把欄位名正規化成
                    # 目前規格的 item_id，否則增量重跑時舊檔的 furniture_id 會殘留
                    if "furniture_id" in row:
                        row = {("item_id" if k == "furniture_id" else k): v for k, v in row.items()}
                    reused[row["item_id"]] = row
            before = len(items)
            changed = [i for i in items
                       if reused.get(i["id"], {}).get("text_hash") != i["text_hash"]]
            keep_ids = {i["id"] for i in items} - {i["id"] for i in changed}
            reused = {k: v for k, v in reused.items() if k in keep_ids}
            print(f"增量模式：{before} 筆中 {len(changed)} 筆 text_hash 變動需重算，"
                  f"{len(reused)} 筆沿用舊向量")
            items = changed

    device = pick_device(args.device)
    print(f"[1/4] 載入 {MODEL_NAME}（device={device}）…", flush=True)
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME, device=device)
    model.max_seq_length = MAX_SEQ_LEN
    print(f"      模型就緒，耗時 {time.time() - t0:.1f}s", flush=True)

    texts = [i["embedded_text"] for i in items]
    print(f"[2/4] 編碼 {len(texts)} 筆（batch={args.batch_size}, max_len={MAX_SEQ_LEN}）…", flush=True)

    vectors = []
    failures = []
    started = time.time()
    for start in range(0, len(texts), args.batch_size):
        chunk = texts[start : start + args.batch_size]
        try:
            emb = model.encode(
                chunk,
                batch_size=len(chunk),
                normalize_embeddings=True,  # 交付規格宣告 normalized=true
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            vectors.extend(emb)
        except Exception as exc:  # 單批失敗不中斷全量
            for item in items[start : start + len(chunk)]:
                failures.append(
                    {
                        "item_id": item["id"],
                        "error_type": "model_error",
                        "error_message": f"{type(exc).__name__}: {exc}",
                    }
                )
            vectors.extend([None] * len(chunk))

        done = start + len(chunk)
        if done % (args.batch_size * 20) == 0 or done >= len(texts):
            elapsed = time.time() - started
            rate = done / elapsed
            eta = (len(texts) - done) / rate if rate else 0
            print(
                f"      {done}/{len(texts)}  {rate:.1f} 筆/秒  已用 {fmt_eta(elapsed)}  剩餘 {fmt_eta(eta)}",
                flush=True,
            )

    encode_seconds = time.time() - started

    # ── 驗證與交付檔 ───────────────────────────────────────────
    print("[3/4] 寫出 rag_export/…", flush=True)
    EXPORT_DIR.mkdir(exist_ok=True)
    now = datetime.now(TZ8).isoformat(timespec="seconds")

    ok_items, ok_vectors = [], []
    by_id = {i["id"]: i for i in src["items"]}
    with (EXPORT_DIR / EMBEDDINGS_FILE).open("w", encoding="utf-8") as fh:
        # 增量模式：先把沿用的舊向量原樣寫回，Chroma 也用它們重建，保持兩邊一致
        for fid, row in reused.items():
            item = by_id.get(fid)
            if not item:
                continue
            ok_items.append(item)
            ok_vectors.append(row["embedding"])
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        for item, vec in zip(items, vectors):
            if vec is None:
                continue
            if len(vec) != DIMENSION:
                failures.append(
                    {
                        "item_id": item["id"],
                        "error_type": "invalid_dimension",
                        "expected_dimension": DIMENSION,
                        "actual_dimension": int(len(vec)),
                    }
                )
                continue
            if not item["embedded_text"].strip():
                failures.append(
                    {
                        "item_id": item["id"],
                        "error_type": "empty_embedded_text",
                        "error_message": "embedded_text is empty",
                    }
                )
                continue
            ok_items.append(item)
            ok_vectors.append(vec)
            fh.write(
                json.dumps(
                    {
                        "item_id": item["id"],
                        "embedded_text": item["embedded_text"],
                        "text_hash": item["text_hash"],
                        "embedding_model": MODEL_NAME,
                        "embedding_dimension": DIMENSION,
                        "embedding": [round(float(x), 6) for x in vec],
                        "embedded_at": now,
                        "text_format_version": item["text_format_version"],
                        "source_schema_version": src["schema_version"],
                        "normalized": True,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    for item in skipped:
        failures.append(
            {
                "item_id": item["id"],
                "error_type": "not_indexable",
                "error_message": "rag_indexable=false（is_active=False 或無文本）",
            }
        )

    with (EXPORT_DIR / "embedding_failures.jsonl").open("w", encoding="utf-8") as fh:
        for row in failures:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    (EXPORT_DIR / "embedding_metadata.json").write_text(
        json.dumps(
            {
                "dataset_name": src.get("dataset_name"),
                "source_file": "rag_dataset/furniture_enriched_v3.json",
                "source_schema_version": src["schema_version"],
                "source_item_count": len(src["items"]),
                "embedded_count": len(ok_items),
                "reused_vector_count": len(reused),
                "failed_count": len(failures),
                "embedding_model": MODEL_NAME,
                "embedding_dimension": DIMENSION,
                "distance_metric": "cosine",
                "normalized": True,
                "text_format_version": src["text_format_version"],
                "text_fields": src["text_fields"],
                "id_key": "item_id",
                "encode_seconds": round(encode_seconds, 1),
                "device": device,
                "generated_at": now,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    ids = [i["id"] for i in ok_items]
    (EXPORT_DIR / "embedding_validation_report.json").write_text(
        json.dumps(
            {
                "total_source_items": len(src["items"]),
                "total_embedding_records": len(ok_items),
                "unique_furniture_ids": len(set(ids)),
                "duplicate_furniture_ids": len(ids) - len(set(ids)),
                "missing_furniture_ids": len(src["items"]) - len(ok_items),
                "invalid_vector_count": sum(1 for f in failures if f["error_type"] == "invalid_dimension"),
                "null_vector_count": sum(1 for f in failures if f["error_type"] == "model_error"),
                "dimension_distribution": {str(DIMENSION): len(ok_items)},
                "model_distribution": {MODEL_NAME: len(ok_items)},
                "coverage_percent": round(len(ok_items) / len(src["items"]) * 100, 2),
                "generated_at": now,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ── 寫入 Chroma ───────────────────────────────────────────
    if not args.skip_chroma:
        import chromadb

        print("[4/4] 寫入 ChromaDB…", flush=True)
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
        coll = client.create_collection(
            COLLECTION,
            metadata={"hnsw:space": "cosine", "embedding_model": MODEL_NAME, "source": src["schema_version"]},
        )
        CHUNK = 1000
        for start in range(0, len(ok_items), CHUNK):
            batch = ok_items[start : start + CHUNK]
            coll.add(
                ids=[i["id"] for i in batch],
                embeddings=[[float(x) for x in v] for v in ok_vectors[start : start + CHUNK]],
                documents=[i["embedded_text"] for i in batch],
                metadatas=[i["chroma_metadata"] for i in batch],
            )
            print(f"      {min(start + CHUNK, len(ok_items))}/{len(ok_items)}", flush=True)
        print(f"      collection '{COLLECTION}' count = {coll.count()}", flush=True)

    print(
        f"\n完成：成功 {len(ok_items)}（其中沿用 {len(reused)}） / 失敗 {len(failures)}"
        f" / 覆蓋率 {len(ok_items) / len(src['items']) * 100:.2f}%"
        f" / 編碼耗時 {fmt_eta(encode_seconds)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
