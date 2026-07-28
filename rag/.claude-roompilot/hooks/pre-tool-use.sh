#!/bin/bash

# TaskMaster Pre Tool Use Hook（RoomPilot 家具風格檢索系統專用）
# 在工具使用前檢查 TaskMaster 狀態並提供上下文
#
# Exit code 語義：
#   0 = 放行（預設，所有提示皆為非阻斷）
#   2 = 阻擋（目前僅用於：偵測到把 Anthropic 金鑰字面值寫進專案檔案）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# 配置目錄由本腳本位置推導（勿硬寫目錄名）——改名為 .claude/ 啟用後自動跟著走
CLAUDE_DIR="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd)"
CLAUDE_DIR_NAME="$(basename "$CLAUDE_DIR")"

# 確保 logs 目錄存在
mkdir -p "$CLAUDE_DIR/logs" 2>/dev/null

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$CLAUDE_DIR/logs/hooks.log"
}

# 從 stdin 讀取 hook JSON 輸入
INPUT=$(cat)

# 解析工具名稱和參數
if command -v jq >/dev/null 2>&1; then
    TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
    TOOL_ARGS=$(echo "$INPUT" | jq -r '.tool_input | tostring' 2>/dev/null || echo "")
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || echo "")
    NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // .tool_input.new_string // ""' 2>/dev/null || echo "")
else
    TOOL_NAME="unknown"
    TOOL_ARGS=""
    FILE_PATH=""
    NEW_CONTENT=""
fi

log "🪝 RoomPilot Pre Tool Use Hook 觸發: $TOOL_NAME"

# ============================================================================
# 安全閘門：金鑰保護（.anthropic_key 為純文字檔、已列入 .gitignore）
# ============================================================================

# (1) 阻擋：把 Anthropic 金鑰字面值寫進任何專案檔案
if echo "$NEW_CONTENT" | grep -Eq 'sk-ant-[A-Za-z0-9_-]{20,}'; then
    log "🛑 阻擋：偵測到 Anthropic 金鑰字面值即將寫入 $FILE_PATH"
    echo "🛑 已阻擋：偵測到 Anthropic 金鑰字面值被寫進檔案。" >&2
    echo "   金鑰只能放在 .anthropic_key（純文字、已 .gitignore）或環境變數 ANTHROPIC_API_KEY。" >&2
    echo "   請改為讀取金鑰，不要把金鑰內容寫進程式碼、文件或 JSON。" >&2
    exit 2
fi

# (2) 警告：直接改寫金鑰檔本身
if [[ "$FILE_PATH" == *".anthropic_key" ]] || [[ "$FILE_PATH" == *".env" ]]; then
    log "⚠️ 警告：即將寫入金鑰檔 $FILE_PATH"
    echo "⚠️ 注意: 這是金鑰檔。內容絕不可回顯到對話、log 或任何交付物中。"
fi

# 如果 TaskMaster 已初始化，提供當前狀態上下文
if [ -f "$CLAUDE_DIR/taskmaster-data/project.json" ]; then
    log "📊 TaskMaster 已初始化，提供上下文資訊"

    # 讀取當前專案狀態
    if command -v jq >/dev/null 2>&1 && [ -f "$CLAUDE_DIR/taskmaster-data/project.json" ]; then
        PROJECT_NAME=$(jq -r '.name // "RoomPilot 家具風格檢索系統"' "$CLAUDE_DIR/taskmaster-data/project.json")

        echo "📋 TaskMaster 當前狀態:"
        echo "   專案名稱: $PROJECT_NAME"

        # 檢查是否有待審查的文檔
        if [ -d "$PROJECT_ROOT/docs" ]; then
            PENDING_DOCS=$(find "$PROJECT_ROOT/docs" -name "*.md" -newer "$CLAUDE_DIR/taskmaster-data/project.json" 2>/dev/null | wc -l)
            if [ "$PENDING_DOCS" -gt 0 ]; then
                echo "   🔍 待審查文檔: $PENDING_DOCS 個"
            fi
        fi
    fi
fi

# 特定工具的預處理
case "$TOOL_NAME" in
    "Write")
        log "📝 Write 工具即將使用"
        # 檢查是否為文檔目錄寫入（docs/ 為 SSOT，文件為契約）
        if [[ "$TOOL_ARGS" == *"docs/"* ]]; then
            log "📄 即將寫入專案 SSOT 文檔"
            echo "💡 提示: docs/ 是契約文件，寫入後將觸發駕駛員審查流程"
        fi
        # 檢查是否新增管線 .py（rag_pipeline / json_adjustment / vlm_annotation）
        if [[ "$FILE_PATH" == *.py ]]; then
            log "🐍 即將寫入 Python 檔案: $FILE_PATH"
            echo "💡 提示: 一律以 .venv-rag/bin/python 執行（Python 3.11.15，專案唯一環境）"
        fi
        ;;

    "Edit")
        log "✏️ Edit 工具即將使用"
        # 檢查是否編輯關鍵檔案
        if [[ "$TOOL_ARGS" == *"/$CLAUDE_DIR_NAME/"* ]]; then
            log "⚙️ 即將編輯 TaskMaster 核心檔案"
        fi
        # 排序權重定義在 rag_pipeline/retriever.py:47
        if [[ "$FILE_PATH" == *"rag_pipeline/retriever.py" ]]; then
            log "⚖️ 即將編輯檢索核心 retriever.py"
            echo "⚠️ 提醒: 排序權重（W_RERANK/W_STYLE/W_MOOD/W_CONF = 0.60/0.20/0.10/0.10）"
            echo "   與 VEC_TOP_K=50、RERANK_TOP_K=20、FINAL_TOP_K=8 屬契約值，"
            echo "   改動後必須同步 docs/RAG檢索系統說明.md"
            echo "   另注意：rag_indexable 不能寫進 Chroma where；rerank 分數不可再套 sigmoid"
        fi
        # 需求解析 schema 的 SSOT 是 docs/query_parser_spec.md
        if [[ "$FILE_PATH" == *"rag_pipeline/query_parser.py" ]]; then
            log "🧠 即將編輯需求解析 query_parser.py"
            echo "⚠️ 提醒: structured outputs 可為 null 的 enum 要用 anyOf（寫 type 陣列會 400）；"
            echo "   schema 變更需同步 docs/query_parser_spec.md"
        fi
        # 六風格詞表 / 檢索群組表：資料契約
        if [[ "$FILE_PATH" == *"taxonomy_v2.json" ]] || [[ "$FILE_PATH" == *"category_groups.json" ]]; then
            log "🎨 即將編輯資料契約 JSON: $FILE_PATH"
            echo "⚠️ 提醒: 六風格詞表 / 19 檢索群組為 SSOT，改動後必須同步"
            echo "   docs/RAG檢索系統說明.md，並重跑 .venv-rag/bin/python rag_pipeline/embed_v3.py --only-changed"
        fi
        # 索引建置腳本
        if [[ "$FILE_PATH" == *"embed_v3.py" ]]; then
            log "🧱 即將編輯索引建置腳本 embed_v3.py"
            echo "💡 提示: 改動後先跑 --limit 50 冒煙，再決定是否全量重建（約 27 分鐘）"
        fi
        ;;

    "Read")
        log "📖 Read 工具即將使用"
        # 如果讀取 SSOT 契約文件，提供上下文
        if [[ "$TOOL_ARGS" == *"docs/"* ]] || [[ "$TOOL_ARGS" == *"RAGSQL.md"* ]] || [[ "$TOOL_ARGS" == *"i_need_rag.md"* ]]; then
            log "📐 即將讀取 SSOT 契約文件"
        fi
        # 金鑰檔內容禁止讀入對話
        if [[ "$FILE_PATH" == *".anthropic_key" ]]; then
            log "🔑 偵測到讀取金鑰檔"
            echo "⚠️ 注意: .anthropic_key 內容不得回顯或摘要，程式請以讀檔方式取用"
        fi
        ;;

    "Bash")
        log "🖥️ Bash 工具即將使用"
        # 本專案無 CI、無容器化部署，所有執行都在本機 .venv-rag/
        if [[ "$TOOL_ARGS" == *"python"* ]] && [[ "$TOOL_ARGS" != *".venv-rag/bin/python"* ]]; then
            log "🐍 偵測到非 .venv-rag 的 Python 呼叫"
            echo "💡 提示: 本專案唯一環境是 .venv-rag/bin/python（.venv/ 已不存在）"
        fi
        ;;

    "Task"|"Agent")
        log "🤖 Task 工具即將使用 (智能體委派)"
        # 提供智能體協調上下文
        if [ -f "$CLAUDE_DIR/taskmaster-data/project.json" ]; then
            echo "🤖 TaskMaster Hub 協調模式啟用"
            echo "   所有智能體委派將記錄在 WBS Todo List 中"
        fi
        ;;
esac

log "✅ Pre Tool Use Hook 處理完成"
exit 0
