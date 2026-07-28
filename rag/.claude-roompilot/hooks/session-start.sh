#!/bin/bash

# TaskMaster Session Start Hook（RoomPilot 家具風格檢索系統專用）
# 當 Claude Code 會話開始時自動執行
# 本專案只在 macOS（Darwin 24.5、Apple Silicon）執行；平台偵測保留作為防呆，
# 非 macOS 時僅提示，不阻斷（本專案無 Windows／Linux／WSL 需求）

# ============================================================================
# 平台檢測和兼容性設置
# ============================================================================

# 檢測操作系統平台
detect_platform() {
    local uname_output="$(uname -s)"

    # 優先檢查環境變量（更準確）
    # WSL_DISTRO_NAME 只存在於 WSL 環境
    if [ -n "$WSL_DISTRO_NAME" ]; then
        echo "wsl"
        return
    fi

    # 檢查是否在 Windows Git Bash
    # MSYSTEM 環境變量存在於 Git Bash
    if [ -n "$MSYSTEM" ]; then
        echo "windows"
        return
    fi

    # 使用 uname 判斷
    case "$uname_output" in
        MINGW*|MSYS*|CYGWIN*)
            echo "windows"
            ;;
        Linux)
            # 二次確認是否為 WSL
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo "wsl"
            else
                echo "linux"
            fi
            ;;
        Darwin)
            echo "macos"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

PLATFORM=$(detect_platform)

# 兼容性：不使用 set -e，避免任何非零退出碼中斷 Claude Code 啟動

# 路徑處理
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd)"
# 配置目錄由本腳本位置推導（勿硬寫目錄名）——改名為 .claude/ 啟用後自動跟著走
CLAUDE_DIR="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd)"
CLAUDE_DIR_NAME="$(basename "$CLAUDE_DIR")"

# 專案 Python 環境（唯一環境，Python 3.11.15）
RAG_PY="$PROJECT_ROOT/.venv-rag/bin/python"

# 路徑驗證（所有平台）
if [ -z "$PROJECT_ROOT" ] || [ -z "$CLAUDE_DIR" ]; then
    echo "❌ 無法確定專案路徑 (Platform: $PLATFORM)" >&2
    exit 0  # 改為 exit 0，避免中斷 Claude Code
fi

# 確保 logs 目錄存在
mkdir -p "$CLAUDE_DIR/logs" 2>/dev/null

# 日誌函數
log() {
    local timestamp="[$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo '????-??-?? ??:??:??')]"
    echo "$timestamp $1" | tee -a "$CLAUDE_DIR/logs/hooks.log" 2>/dev/null || echo "$timestamp $1"
}

log "🪝 RoomPilot Session Start Hook 觸發 (Platform: $PLATFORM)"

if [ "$PLATFORM" != "macos" ]; then
    log "⚠️ 本專案僅在 macOS 驗證過（MPS 優先退 CPU）；目前平台: $PLATFORM"
fi

# ============================================================================
# 環境自檢：RAG 管線的三個必要條件
# ============================================================================
if [ ! -x "$RAG_PY" ]; then
    log "⚠️ 找不到 .venv-rag/bin/python（RAG 管線唯一環境，Python 3.11.15）"
fi

if [ ! -d "$PROJECT_ROOT/chroma_db" ]; then
    log "⚠️ chroma_db/ 不存在 → 需先建索引：.venv-rag/bin/python rag_pipeline/embed_v3.py"
fi

if [ -f "$PROJECT_ROOT/.anthropic_key" ]; then
    log "🔑 偵測到 .anthropic_key（需求解析用；內容絕不回顯、絕不提交）"
elif [ -z "$ANTHROPIC_API_KEY" ]; then
    log "⚠️ 未偵測到 .anthropic_key 或 ANTHROPIC_API_KEY → query_parser.py 將無法呼叫 claude-haiku-4-5"
fi

# ============================================================================
# 時間追蹤：歸檔上一次 Session 的時間
# ============================================================================
TIMELOG_DIR="$CLAUDE_DIR/taskmaster-data"
SNAPSHOT_FILE="$TIMELOG_DIR/.session-snapshot"
TIMELOG_FILE="$TIMELOG_DIR/timelog.jsonl"

if [ -f "$SNAPSHOT_FILE" ]; then
    # 讀取上次 session 的快照
    snapshot=$(cat "$SNAPSHOT_FILE" 2>/dev/null)
    if [ -n "$snapshot" ] && command -v jq >/dev/null 2>&1; then
        snap_duration=$(echo "$snapshot" | jq -r '.duration_ms // 0' 2>/dev/null)
        if [ "$snap_duration" -gt 0 ] 2>/dev/null; then
            # 追加到 timelog.jsonl（不覆蓋，追加）
            echo "$snapshot" >> "$TIMELOG_FILE" 2>/dev/null
            log "⏱️ 上次 Session 時間已歸檔 (${snap_duration}ms)"
        fi
    fi
    # 清除快照
    rm -f "$SNAPSHOT_FILE" 2>/dev/null
fi

# 記錄本次 session 開始時間
mkdir -p "$TIMELOG_DIR" 2>/dev/null
date '+%H:%M' > "$TIMELOG_DIR/.session-start" 2>/dev/null

# 檢查是否存在 CLAUDE_TEMPLATE.md
if [ -f "$PROJECT_ROOT/CLAUDE_TEMPLATE.md" ]; then
    log "📄 偵測到 CLAUDE_TEMPLATE.md"

    # 檢查是否已經初始化過
    if [ ! -f "$CLAUDE_DIR/taskmaster-data/project.json" ]; then
        log "🚀 準備自動觸發 TaskMaster 初始化"

        # 顯示提示訊息（Jobs 式極簡設計）
        echo ""
        echo -e "\033[1;37m╭─────────────────────────────────────────────────────────────╮\033[0m"
        echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m     \033[1;97m🚀 RoomPilot TaskMaster Ready\033[0m                        \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m     \033[0;90mTemplate detected. Start with:\033[0m                      \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m     \033[1;36m/task-init [project-name]\033[0m                           \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
        echo -e "\033[1;37m├─────────────────────────────────────────────────────────────┤\033[0m"
        echo -e "\033[1;37m│\033[0m \033[1;97mWorkflow\033[0m                                                   \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m   \033[1;32m①\033[0m  \033[0;37m蒐集檢索需求與允收標準\033[0m         \033[0;90m→ Human review\033[0m    \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m   \033[1;33m②\033[0m  \033[0;37m更新 docs/ SSOT 文件\033[0m           \033[0;90m→ Quality gate\033[0m    \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m   \033[1;36m③\033[0m  \033[0;37m改管線並重建索引\033[0m               \033[0;90m→ After approval\033[0m  \033[1;37m│\033[0m"
        echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
        echo -e "\033[1;37m╰─────────────────────────────────────────────────────────────╯\033[0m"
        echo ""

        # 觸發 TaskMaster 處理器（一律 Python，以 .venv-rag/bin/python 執行）
        # 註：<配置目錄>/taskmaster.py **尚未建置**，不存在則靜默跳過
        if [ -f "$CLAUDE_DIR/taskmaster.py" ] && [ -x "$RAG_PY" ]; then
            log "🔗 調用 TaskMaster Python 處理器"
            cd "$PROJECT_ROOT" 2>/dev/null || exit 0
            "$RAG_PY" "$CLAUDE_DIR/taskmaster.py" --hook-trigger=session-start || true
        fi

        exit 0
    else
        log "ℹ️ TaskMaster 已初始化"

        # 檢查是否有現有 WBS 檔案，提示恢復
        if [ -f "$CLAUDE_DIR/taskmaster-data/wbs.md" ]; then
            log "📋 偵測到現有 WBS 任務清單"

            echo ""
            echo -e "\033[1;37m╭─────────────────────────────────────────────────────────────╮\033[0m"
            echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
            echo -e "\033[1;37m│\033[0m     \033[1;97m📋 WBS 任務清單已載入\033[0m                              \033[1;37m│\033[0m"
            echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
            echo -e "\033[1;37m│\033[0m     \033[0;90mResume with:\033[0m                                        \033[1;37m│\033[0m"
            echo -e "\033[1;37m│\033[0m     \033[1;36m/task-status\033[0m  查看進度                              \033[1;37m│\033[0m"
            echo -e "\033[1;37m│\033[0m     \033[1;36m/task-next\033[0m    取得下一個任務                        \033[1;37m│\033[0m"
            echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
            echo -e "\033[1;37m╰─────────────────────────────────────────────────────────────╯\033[0m"
            echo ""
        fi

        exit 0
    fi
else
    log "ℹ️ 未偵測到 CLAUDE_TEMPLATE.md，TaskMaster 待命中"

    # RoomPilot 速查卡：本專案沒有 CLAUDE_TEMPLATE.md，改顯示管線常用指令
    echo ""
    echo -e "\033[1;37m╭─────────────────────────────────────────────────────────────╮\033[0m"
    echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
    echo -e "\033[1;37m│\033[0m     \033[1;97m🛋  RoomPilot 家具風格檢索系統\033[0m                       \033[1;37m│\033[0m"
    echo -e "\033[1;37m│\033[0m     \033[0;90mChromaDB furniture_v3 · 9,349 筆 · 六風格\033[0m           \033[1;37m│\033[0m"
    echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
    echo -e "\033[1;37m├─────────────────────────────────────────────────────────────┤\033[0m"
    echo -e "\033[1;37m│\033[0m \033[1;97m常用指令（PY=.venv-rag/bin/python）\033[0m                       \033[1;37m│\033[0m"
    echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
    echo -e "\033[1;37m│\033[0m   \033[1;36m\$PY rag_pipeline/app.py\033[0m        \033[0;90m→ UI :7860\033[0m            \033[1;37m│\033[0m"
    echo -e "\033[1;37m│\033[0m   \033[1;36m\$PY rag_pipeline/retriever.py \"…\"\033[0m \033[0;90m→ CLI 檢索\033[0m       \033[1;37m│\033[0m"
    echo -e "\033[1;37m│\033[0m   \033[1;36m\$PY rag_pipeline/embed_v3.py --limit 50\033[0m \033[0;90m→ 冒煙\033[0m       \033[1;37m│\033[0m"
    echo -e "\033[1;37m│\033[0m                                                             \033[1;37m│\033[0m"
    echo -e "\033[1;37m╰─────────────────────────────────────────────────────────────╯\033[0m"
    echo ""

    exit 0
fi
