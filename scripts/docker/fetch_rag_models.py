"""建置期把家具 RAG 的兩份權重抓進映像，並當場驗證載得起來。

只在 Dockerfile 的 models stage 執行，執行期不會用到。

為什麼不是直接 COPY 本機的 ~/.cache/huggingface：
  1. 那份快取 6.4GB，其中 bge-m3 同時存了 pytorch_model.bin 與 model.safetensors
     兩種格式（各 2.27GB），是同一份權重；
  2. HuggingFace 快取內部是 blobs + symlink，Windows 的 symlink 進 build context
     會壞；
  3. 快取不在 repo 內，本來就不在 build context 裡。
所以改成建置期用 huggingface_hub 重抓一份乾淨的 HF 快取版面。

為什麼要維持「HF 快取版面」而不是攤平成一般資料夾：
  backend/spatial_data/rag/model_runtime.py 是用
      SentenceTransformer("BAAI/bge-m3", cache_folder=..., local_files_only=True)
  載入的——傳的是 repo id 不是路徑，sentence-transformers 會走 HuggingFace 的
  快取解析（models--<org>--<repo>/snapshots/<rev>/ 加上 refs/main）。攤平成
  /opt/rag-models/bge-m3/ 只能騙過 model_runtime.py:23 的 _repo_is_cached，
  真正 load 的時候還是會失敗。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download


CACHE_DIR = Path(os.getenv("ROOMPILOT_RAG_MODEL_CACHE", "/opt/rag-models"))

EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

# 只排掉 sentence-transformers 一定不會讀的檔。
#
# ⚠ 千萬不要排 *.bin。2026-08-09 第一次 build 就是這樣炸的：
#   本機快取裡 bge-m3 有 pytorch_model.bin 與 model.safetensors 兩份 2.27GB，
#   看起來像重複格式可以砍一份——但那兩份分屬**不同 revision**。
#   main 上實際只有 pytorch_model.bin，排掉 *.bin 等於刪光唯一的權重檔，
#   建置期驗證直接回
#     OSError: BAAI/bge-m3 does not appear to have a file named
#              pytorch_model.bin or model.safetensors
#   兩種權重格式都留著，載入時 transformers 自己會挑；這兩個 repo 各自
#   只有一種，不會真的重複下載。
#
#   *.h5 / *.msgpack / *.ot —— TensorFlow 與 Flax 的權重，本專案只用 PyTorch。
#   onnx/、openvino/        —— 給其他推論 runtime 的匯出檔。
#   *.pt                    —— colbert_linear.pt / sparse_linear.pt 是
#                              FlagEmbedding 的多向量頭；本專案只用稠密向量
#                              （model_runtime.py:16 EMBED_DIMENSION=1024）。
#   imgs/                   —— README 用的圖。
IGNORE = ["*.h5", "*.msgpack", "*.ot", "*.pt", "onnx/*", "openvino/*", "imgs/*"]


def fetch(repo_id: str) -> str:
    print(f"[models] downloading {repo_id} -> {CACHE_DIR}", flush=True)
    path = snapshot_download(
        repo_id=repo_id,
        cache_dir=str(CACHE_DIR),
        ignore_patterns=IGNORE,
        max_workers=4,
    )
    # 把實際落地的權重檔印出來。日後換 revision 或改 ignore 清單時，
    # 這一行是判斷「到底抓到什麼」最快的證據。
    weights = sorted(
        f"{p.name} ({p.stat().st_size / 1024 / 1024:.0f}MB)"
        for p in Path(path).glob("*")
        if p.suffix in {".bin", ".safetensors"}
    )
    print(f"[models] {repo_id} ready at {path}", flush=True)
    print(f"[models]   weights: {', '.join(weights) or 'NONE — 這一定是錯的'}", flush=True)
    return path


def download() -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fetch(EMBED_MODEL)
    fetch(RERANK_MODEL)
    return 0


def verify() -> int:
    # 建置期就把執行期那條路走一遍。這一步是刻意的：抓得到檔 != 載得起來。
    # 少了 model.safetensors、少了 1_Pooling/config.json、或 ignore 清單誤殺了
    # 必要檔，都只會在這裡爆，不會拖到使用者按下第 6 步才發現。
    from sentence_transformers import CrossEncoder, SentenceTransformer

    print("[models] verifying SentenceTransformer load (local_files_only)", flush=True)
    embedder = SentenceTransformer(
        EMBED_MODEL,
        device="cpu",
        cache_folder=str(CACHE_DIR),
        local_files_only=True,
    )
    embedder.max_seq_length = 512
    vector = embedder.encode(["三人沙發 淺灰 北歐風"], normalize_embeddings=True)[0]
    if len(vector) != 1024:
        print(
            f"[models] FATAL embedding dimension {len(vector)} != 1024 "
            "(backend/spatial_data/rag/model_runtime.py:16 EMBED_DIMENSION)",
            file=sys.stderr,
        )
        return 1
    print(f"[models] embedding OK, dim={len(vector)}", flush=True)

    print("[models] verifying CrossEncoder load (local_files_only)", flush=True)
    reranker = CrossEncoder(
        RERANK_MODEL,
        device="cpu",
        max_length=512,
        cache_folder=str(CACHE_DIR),
        local_files_only=True,
    )
    scores = reranker.predict([("北歐風沙發", "淺灰色三人布沙發")])
    print(f"[models] rerank OK, score={float(scores[0]):.4f}", flush=True)

    return 0


MODES = {"download": download, "verify": verify}


if __name__ == "__main__":
    # download 與 verify 分開，是為了讓 4.5GB 的下載自成一層：
    # 只裝 huggingface-hub 的輕量 stage 負責下載，快取鍵穩定；
    # 改 requirements 只會重跑 verify，不會重抓權重。
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in MODES:
        print(f"usage: {sys.argv[0]} {{download|verify}}", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(MODES[mode]())
