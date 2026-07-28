#!/bin/bash

# TaskMaster Post Write Hook（RoomPilot 家具風格檢索系統專用）
# 當 Claude Code 寫入檔案後觸發，關注 SSOT 文檔生成與資料契約變更
#
# Exit code 語義：0 = 放行（PostToolUse 一律不阻擋，僅提示與記錄）

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

# 解析寫入的檔案路徑
if command -v jq >/dev/null 2>&1; then
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
else
    FILE_PATH=""
fi

log "🪝 RoomPilot Post Write Hook 觸發: $FILE_PATH"

# ============================================================================
# 金鑰防呆：寫入金鑰檔後提醒（本專案 .anthropic_key 為純文字、已 .gitignore）
# ============================================================================
if [[ "$FILE_PATH" == *".anthropic_key" ]] || [[ "$FILE_PATH" == *".env" ]]; then
    log "🔑 金鑰檔已被寫入: $FILE_PATH"
    echo "⚠️ 提醒: $FILE_PATH 屬機敏檔案 — 內容不得回顯，且必須維持在 .gitignore 內"
fi

# 檢查是否為文檔檔案
if [[ "$FILE_PATH" == *.md ]]; then
    log "📄 偵測到 Markdown 文檔寫入: $FILE_PATH"

    # 檢查是否為專案文檔目錄
    if [[ "$FILE_PATH" == *"docs/"* ]]; then
        log "📋 專案 SSOT 文檔更新: $FILE_PATH"

        # 如果 TaskMaster 已初始化，通知文檔生成完成
        if [ -f "$CLAUDE_DIR/taskmaster-data/project.json" ]; then
            log "🔔 通知 TaskMaster 文檔生成完成"

            # 觸發文檔生成完成處理（一律 Python，以 .venv-rag/bin/python 執行）
            # 註：<配置目錄>/taskmaster.py **尚未建置**，不存在則靜默跳過
            if [ -f "$CLAUDE_DIR/taskmaster.py" ] && [ -x "$RAG_PY" ]; then
                cd "$PROJECT_ROOT"
                "$RAG_PY" "$CLAUDE_DIR/taskmaster.py" --hook-trigger=document-generated --file="$FILE_PATH"
            fi

            # 顯示駕駛員審查提示
            cat << EOF

┌──────────────────────────────────────────────────────────┐
│  📄 SSOT 文檔生成完成通知                                 │
│                                                          │
│  檔案: $(basename "$FILE_PATH")                          │
│  路徑: $FILE_PATH                           │
│                                                          │
│  🔍 駕駛員審查檢查點                                      │
│  docs/ 是契約文件，請確認與程式行為一致後：              │
│                                                          │
│  ✅ 確認一致: /verify（解析→檢索→索引覆蓋率冒煙）        │
│  🔄 需要修訂: /review-code（對照六個坑與契約）           │
│  ⏸️ 先擱置: 本通知不阻擋，可直接繼續                     │
│                                                          │
└──────────────────────────────────────────────────────────┘

EOF
        fi
    fi

    # 檢查是否為 SQL 端交付規格更新（原模板的 VibeCoding 範本對應物）
    if [[ "$FILE_PATH" == *"RAGSQL.md"* ]] || [[ "$FILE_PATH" == *"i_need_rag.md"* ]]; then
        log "📦 SQL 端交付規格更新: $FILE_PATH"
        echo "💡 提示: 交付規格變更 → 需重新產出 rag_export/（.venv-rag/bin/python rag_pipeline/embed_v3.py）"

        # 如果 TaskMaster 已初始化，可能需要重新評估任務
        if [ -f "$CLAUDE_DIR/taskmaster-data/project.json" ]; then
            log "🔄 交付規格更新，可能需要重新評估任務"
        fi
    fi
fi

# ============================================================================
# 管線程式碼寫入：提示對應的 SSOT 同步與重跑動作
# ============================================================================
if [[ "$FILE_PATH" == *.py ]]; then
    log "🐍 Python 檔案更新: $FILE_PATH"

    case "$FILE_PATH" in
        *"rag_pipeline/retriever.py")
            log "⚖️ 檢索核心已變更"
            echo "🔁 後續動作: 同步 docs/RAG檢索系統說明.md；驗證指令"
            echo "   .venv-rag/bin/python rag_pipeline/retriever.py \"北歐風小坪數客廳 預算三萬\""
            ;;
        *"rag_pipeline/query_parser.py")
            log "🧠 需求解析已變更"
            echo "🔁 後續動作: 同步 docs/query_parser_spec.md；驗證指令"
            echo "   .venv-rag/bin/python rag_pipeline/query_parser.py \"日式無印風臥室\""
            ;;
        *"rag_pipeline/embed_v3.py")
            log "🧱 索引建置腳本已變更"
            echo "🔁 後續動作: .venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50（冒煙）"
            echo "   確認無誤再 --only-changed 或全量重建（約 27 分鐘）"
            ;;
        *"rag_pipeline/app.py")
            log "🖼️ Gradio UI 已變更"
            echo "🔁 後續動作: .venv-rag/bin/python rag_pipeline/app.py → http://127.0.0.1:7860"
            echo "   注意 Gradio 6 的 theme 要在 launch() 傳"
            ;;
        *"json_adjustment/"*|*"vlm_annotation/"*)
            log "🗂️ 資料建置／標註腳本已變更: $FILE_PATH"
            echo "🔁 後續動作: 批次腳本會燒額度，先用 --dry-run / --compare 30 抽樣驗證"
            ;;
    esac
fi

# ============================================================================
# 資料契約 JSON 寫入：taxonomy_v2 / category_groups / rag_dataset / rag_export
# ============================================================================
if [[ "$FILE_PATH" == *.json ]]; then
    case "$FILE_PATH" in
        *"vlm_annotation/taxonomy_v2.json")
            log "🎨 六風格詞表已更新: $FILE_PATH"
            echo "⚠️ taxonomy_v2.json 是 SSOT（六風格 + 6×6 style_compat 相容矩陣）"
            echo "   → 同步 docs/RAG檢索系統說明.md，並重跑 embed_v3.py --only-changed"
            ;;
        *"rag_pipeline/category_groups.json")
            log "🗃️ 檢索群組表已更新: $FILE_PATH"
            echo "⚠️ category_groups.json 是 SSOT（64 細類 → 19 檢索群組 + 房型典型組合）"
            echo "   → 同步 docs/RAG檢索系統說明.md，並確認 retriever.py 硬過濾行為"
            ;;
        *"rag_dataset/"*)
            log "📚 資料集已更新: $FILE_PATH"
            echo "🔁 後續動作: furniture_enriched_v3.json 為現役（9,349 筆）→ 需重建 chroma_db"
            ;;
        *"rag_export/"*)
            log "📦 交付檔已更新: $FILE_PATH"
            echo "💡 提示: rag_export/ 由 embed_v3.py 產出，請勿手動編輯"
            ;;
    esac
fi

# 檢查是否為 WBS 檔案更新
if [[ "$FILE_PATH" == *"taskmaster-data/wbs.md"* ]]; then
    log "📋 WBS 任務清單已更新: $FILE_PATH"

    # 記錄 WBS 更新歷史
    WBS_LOG="$CLAUDE_DIR/taskmaster-data/wbs-history.log"
    mkdir -p "$CLAUDE_DIR/taskmaster-data" 2>/dev/null
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WBS 更新" >> "$WBS_LOG"

    cat << EOF

┌──────────────────────────────────────────────────────────┐
│  📋 WBS 任務清單已同步                                    │
│                                                          │
│  檔案: taskmaster-data/wbs.md（於配置目錄下）             │
│  時間: $(date '+%Y-%m-%d %H:%M:%S')                     │
│                                                          │
│  📊 /task-status  查看最新狀態                            │
│  ➡️  /task-next    取得下一個任務                          │
└──────────────────────────────────────────────────────────┘

EOF
fi

# 檢查是否為 TaskMaster 核心檔案更新
if [[ "$FILE_PATH" == *"/$CLAUDE_DIR_NAME/taskmaster"* ]] && [[ "$FILE_PATH" != *"taskmaster-data"* ]]; then
    log "🔧 TaskMaster 核心檔案更新: $FILE_PATH"

    # 可以在這裡加入核心檔案更新後的處理邏輯
    # 例如：重新載入配置、驗證系統狀態等
fi

# 檢查是否為 hooks 配置更新
if [[ "$FILE_PATH" == *"hooks-config.json"* ]] || [[ "$FILE_PATH" == *"settings.local.json"* ]]; then
    log "⚙️ Hooks 配置檔案更新: $FILE_PATH"

    # 可以在這裡加入配置更新後的處理邏輯
    # 註：本專案無 CI，配置變更需重開 Claude Code session 才生效
fi

log "✅ Post Write Hook 處理完成"
exit 0
