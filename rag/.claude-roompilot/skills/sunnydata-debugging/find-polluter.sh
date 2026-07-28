#!/usr/bin/env bash
# 二分搜尋腳本：找出是哪個測試建立了非預期的檔案／狀態
# 用法：./find-polluter.sh <要檢查的檔案或目錄> <測試檔 glob>
# 範例：./find-polluter.sh 'chroma_db' 'tests/test_*.py'
#
# ⚠️ 本專案 pytest 尚未建置（沒有 tests/、也還沒把 pytest 裝進 .venv-rag/）。
#    先跑：.venv-rag/bin/python -m pip install pytest && mkdir -p tests
#    在 pytest 就位之前，等價的手動做法是：一次只跑一支腳本，每跑完檢查一次是否冒出非預期檔案。
#
# RoomPilot 常見的污染對象：
#   chroma_db/                             測試誤寫正式索引
#   rag_export/                            測試誤覆蓋 SQL 端交付檔
#   rag_dataset/furniture_enriched_v3.json 測試誤改現役資料集
#   vlm_annotation/render_meta_full.jsonl  測試誤 append 標註進度

set -e

PY=.venv-rag/bin/python

if [ $# -ne 2 ]; then
  echo "用法：$0 <要檢查的檔案> <測試檔 glob>"
  echo "範例：$0 'chroma_db' 'tests/test_*.py'"
  exit 1
fi

POLLUTION_CHECK="$1"
TEST_PATTERN="$2"

if [ ! -x "$PY" ]; then
  echo "❌ 找不到 $PY —— 本專案唯一環境是 .venv-rag/，請先確認它存在"
  exit 1
fi

if ! "$PY" -m pytest --version > /dev/null 2>&1; then
  echo "❌ .venv-rag/ 尚未安裝 pytest（本專案測試套件尚未建置）"
  echo "   先跑：$PY -m pip install pytest"
  exit 1
fi

echo "🔍 正在尋找建立了下列項目的測試：$POLLUTION_CHECK"
echo "測試檔樣式：$TEST_PATTERN"
echo ""

# 取得測試檔清單
TEST_FILES=$(find . -path "$TEST_PATTERN" | sort)
TOTAL=$(echo "$TEST_FILES" | wc -l | tr -d ' ')

echo "找到 $TOTAL 個測試檔"
echo ""

COUNT=0
for TEST_FILE in $TEST_FILES; do
  COUNT=$((COUNT + 1))

  # 若污染已經存在就跳過
  if [ -e "$POLLUTION_CHECK" ]; then
    echo "⚠️  在第 $COUNT/$TOTAL 個測試之前，污染就已存在"
    echo "   略過：$TEST_FILE"
    continue
  fi

  echo "[$COUNT/$TOTAL] 測試中：$TEST_FILE"

  # 跑這一支測試
  "$PY" -m pytest "$TEST_FILE" -q > /dev/null 2>&1 || true

  # 檢查污染是否出現
  if [ -e "$POLLUTION_CHECK" ]; then
    echo ""
    echo "🎯 找到污染者！"
    echo "   測試：$TEST_FILE"
    echo "   建立了：$POLLUTION_CHECK"
    echo ""
    echo "污染細節："
    ls -la "$POLLUTION_CHECK"
    echo ""
    echo "接著這樣查："
    echo "  $PY -m pytest $TEST_FILE -q    # 只跑這一支測試"
    echo "  cat $TEST_FILE                 # 檢視測試碼"
    exit 1
  fi
done

echo ""
echo "✅ 沒有找到污染者 —— 所有測試都乾淨！"
exit 0
