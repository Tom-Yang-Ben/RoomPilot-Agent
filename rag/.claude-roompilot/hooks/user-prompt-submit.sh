#!/bin/bash

# TaskMaster User Prompt Submit Hook（RoomPilot 家具風格檢索系統專用）
# 當用戶提交 prompt 時檢查是否包含 TaskMaster 相關命令，
# 並辨識 RoomPilot 的高風險／高成本操作意圖（建索引、批次判定、改權重）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# 配置目錄由本腳本位置推導（勿硬寫目錄名）——改名為 .claude/ 啟用後自動跟著走
CLAUDE_DIR="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd)"
CLAUDE_DIR_NAME="$(basename "$CLAUDE_DIR")"

# 專案 Python 環境（唯一環境，Python 3.11.15）
RAG_PY="$PROJECT_ROOT/.venv-rag/bin/python"

# 確保 logs 目錄存在
mkdir -p "$CLAUDE_DIR/logs" 2>/dev/null

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$CLAUDE_DIR/logs/hooks.log"
}

# 從 stdin 讀取 hook JSON 輸入
INPUT=$(cat)

# 解析用戶輸入
if command -v jq >/dev/null 2>&1; then
    USER_INPUT=$(echo "$INPUT" | jq -r '.content // .message // .prompt // ""')
else
    USER_INPUT=""
fi

log "🪝 RoomPilot User Prompt Submit Hook 觸發"

# 檢查用戶輸入是否包含 TaskMaster 相關命令
if [[ "$USER_INPUT" == *"/task-"* ]]; then
    log "🎯 偵測到 TaskMaster 命令: $USER_INPUT"

    # 解析命令類型
    if [[ "$USER_INPUT" == *"/task-init"* ]]; then
        log "🚀 偵測到專案初始化命令"

        # 確保 TaskMaster 系統準備就緒
        if [ ! -d "$CLAUDE_DIR/taskmaster-data" ]; then
            log "📁 創建 TaskMaster 資料目錄"
            mkdir -p "$CLAUDE_DIR/taskmaster-data"
        fi

        # 觸發初始化準備（一律 Python，以 .venv-rag/bin/python 執行）
        # 註：<配置目錄>/taskmaster.py **尚未建置**，不存在則靜默跳過
        if [ -f "$CLAUDE_DIR/taskmaster.py" ] && [ -x "$RAG_PY" ]; then
            log "🔗 調用 TaskMaster 初始化準備"
            cd "$PROJECT_ROOT"
            "$RAG_PY" "$CLAUDE_DIR/taskmaster.py" --hook-trigger=user-prompt --message="$USER_INPUT"
        fi

    elif [[ "$USER_INPUT" == *"/task-status"* ]]; then
        log "📊 偵測到狀態查詢命令"

    elif [[ "$USER_INPUT" == *"/task-next"* ]]; then
        log "➡️ 偵測到下個任務命令"

    elif [[ "$USER_INPUT" == *"/hub-delegate"* ]]; then
        log "🤖 偵測到智能體委派命令"

    elif [[ "$USER_INPUT" == *"/review-code"* ]]; then
        log "🔍 偵測到程式碼審查命令"
    fi

    exit 0
fi

# 檢查是否包含文檔相關操作
if [[ "$USER_INPUT" == *"docs/"* ]] || [[ "$USER_INPUT" == *".md"* ]]; then
    log "📄 偵測到文檔相關操作"

    # 如果 TaskMaster 已初始化，檢查是否需要更新狀態
    if [ -f "$CLAUDE_DIR/taskmaster-data/project.json" ]; then
        log "🔄 可能需要更新 TaskMaster 狀態"

        # 觸發狀態檢查（Python 處理器尚未建置時自動跳過）
        if [ -f "$CLAUDE_DIR/taskmaster.py" ] && [ -x "$RAG_PY" ]; then
            cd "$PROJECT_ROOT"
            "$RAG_PY" "$CLAUDE_DIR/taskmaster.py" --hook-trigger=document-related --message="$USER_INPUT"
        fi
    fi
fi

# ============================================================================
# RoomPilot 專用意圖偵測：高成本 / 高風險操作先提醒（僅提示，不阻擋）
# ============================================================================

# 建索引：全量約 27 分鐘，增量（--only-changed）646 筆約 1.5 分鐘
if [[ "$USER_INPUT" == *"embed_v3"* ]] || [[ "$USER_INPUT" == *"建索引"* ]] || [[ "$USER_INPUT" == *"重建索引"* ]]; then
    log "🧱 偵測到索引建置意圖（embed_v3.py）"
    echo "💡 提示: 全量建索引約 27 分鐘；先用 --limit 50 冒煙，日常改動用 --only-changed"
fi

# 批次 LLM 工作：會燒額度（六風格全量判定約 US$7）
if [[ "$USER_INPUT" == *"reclassify_styles"* ]] || [[ "$USER_INPUT" == *"風格判定"* ]] || [[ "$USER_INPUT" == *"vlm_annotation"* ]]; then
    log "💰 偵測到批次 LLM 工作意圖"
    echo "💡 提示: 批次工作才會燒額度（六風格全量判定約 US\$7）；先用 --compare 30 抽樣比對"
fi

# 排序權重：定義在 rag_pipeline/retriever.py:47，改動需同步 docs/RAG檢索系統說明.md
if [[ "$USER_INPUT" == *"權重"* ]] || [[ "$USER_INPUT" == *"W_RERANK"* ]] || [[ "$USER_INPUT" == *"rerank"* ]]; then
    log "⚖️ 偵測到排序權重相關討論"
    echo "💡 提示: final = 0.60×rerank + 0.20×style_compat + 0.10×mood + 0.10×confidence（retriever.py:47）"
    echo "   改權重必須同步 docs/RAG檢索系統說明.md"
fi

# 六風格詞表：taxonomy_v2.json 是 SSOT，含 6×6 相容矩陣
if [[ "$USER_INPUT" == *"taxonomy"* ]] || [[ "$USER_INPUT" == *"六風格"* ]] || [[ "$USER_INPUT" == *"style_compat"* ]]; then
    log "🎨 偵測到六風格詞表相關操作"
    echo "💡 提示: 六風格 = scandinavian / japanese / modern_minimal / cream / industrial / american"
    echo "   詞表與 6×6 相容矩陣的 SSOT 是 vlm_annotation/taxonomy_v2.json"
fi

# 金鑰：純文字檔 .anthropic_key，絕不可回顯或提交
if [[ "$USER_INPUT" == *".anthropic_key"* ]] || [[ "$USER_INPUT" == *"sk-ant-"* ]]; then
    log "🔑 偵測到金鑰相關字串（內容不記錄）"
    echo "⚠️ 提醒: .anthropic_key 內容絕不可回顯、貼上或寫入任何檔案（已列入 .gitignore）"
fi

log "✅ User Prompt Submit Hook 處理完成"
exit 0
