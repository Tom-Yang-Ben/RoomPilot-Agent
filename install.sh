#!/usr/bin/env bash
# RoomPilot local development installer (Linux / uv).
set -euo pipefail
cd "$(dirname "$0")"

extras=(--extra portable)
with_delivery=0
for arg in "$@"; do
  case "$arg" in
    --full) extras+=(--extra postgres) ;;
    --with-rag) extras+=(--extra rag) ;;
    --with-ocr) extras+=(--extra ocr) ;;
    --with-delivery) extras+=(--extra delivery); with_delivery=1 ;;
    *) echo "未知選項：$arg" >&2; exit 2 ;;
  esac
done

command -v uv >/dev/null 2>&1 || {
  echo "找不到 uv；請先安裝：https://docs.astral.sh/uv/" >&2
  exit 1
}

uv sync "${extras[@]}" --group dev
if [ "$with_delivery" -eq 1 ]; then
  uv run playwright install chromium
fi
[ -f .env ] || cp .env.example .env

echo
echo "完成。預設 portable profile 啟動指令："
echo "  uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload"
