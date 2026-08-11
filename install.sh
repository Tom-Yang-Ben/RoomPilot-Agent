#!/usr/bin/env bash
# RoomPilot 一鍵安裝所有依賴（Linux / uv）
#
# 用法：
#   bash install.sh                  # 全裝
#   bash install.sh --skip-ocr       # 跳過 PaddleOCR（體積大且平台相依）
#   bash install.sh --skip-frontend  # 跳過 frontend/ npm（次要 React 原型）
#
# 涵蓋：requirements.txt（server/vision/catalog/RAG/tests）＋ OCR ＋ 交付 PDF
#      （playwright/pikepdf）＋ Playwright Chromium ＋ frontend npm。
# 不含：RAG 模型快取（約 9 GB，需要時另跑 scripts/rag/prefetch_models.py --download）。

set -euo pipefail
cd "$(dirname "$0")"

skip_ocr=0
skip_frontend=0
for arg in "$@"; do
  case "$arg" in
    --skip-ocr) skip_ocr=1 ;;
    --skip-frontend) skip_frontend=1 ;;
    *) echo "未知選項：$arg" >&2; exit 2 ;;
  esac
done

command -v uv >/dev/null 2>&1 || {
  echo "找不到 uv，請先安裝：https://docs.astral.sh/uv/" >&2; exit 1;
}

py=".venv/bin/python"

# 1) 建立 venv（若不存在）
if [ ! -x "$py" ]; then
  echo "==> uv 建立 .venv (Python 3.12)"
  uv venv --python 3.12 .venv
fi

# 2) Python 依賴（requirements-ocr.txt 內含 -r requirements.txt）
if [ "$skip_ocr" -eq 1 ]; then
  echo "==> 安裝基線依賴（跳過 OCR）"
  uv pip install --python "$py" -r requirements.txt
else
  echo "==> 安裝基線 + OCR 依賴"
  uv pip install --python "$py" -r requirements-ocr.txt
fi

# 3) 交付提案 PDF 依賴 + Chromium 瀏覽器
echo "==> 安裝交付 PDF 依賴（playwright / pikepdf）"
uv pip install --python "$py" -r requirements-delivery.txt
echo "==> 下載 Playwright Chromium（首次若缺系統庫：.venv/bin/playwright install-deps）"
.venv/bin/playwright install chromium

# 4) 前端 npm 依賴（次要原型）
if [ "$skip_frontend" -eq 0 ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "==> 安裝 frontend/ npm 依賴"
    npm --prefix frontend install
  else
    echo "!! 找不到 npm，跳過前端依賴（如需 3D 原型請先裝 Node.js）"
  fi
fi

echo
echo "完成。啟動後端："
echo "  $py -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload"
