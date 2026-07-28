#!/bin/bash

# TaskMaster Hook 工具函數庫（RoomPilot 家具風格檢索系統專用）
# 提供 hooks 共用的工具函數
#
# 專案事實：
#   - 純 Python 3.11.15 專案，唯一環境 .venv-rag/，執行方式 .venv-rag/bin/python
#   - 本專案無 CI、無容器化部署；hook 一律 bash（僅需 macOS 版），輔助處理器一律 Python
#   - 配置目錄目前為 .claude-roompilot/（所有 log、taskmaster-data 路徑都在此目錄下），
#     但目錄名**不硬寫**：一律由本檔位置推導，改名為 .claude/ 啟用時無須改任何腳本
#   - 專案尚未 git init，故本檔不做任何 git 相關假設

# 專案 Python 直譯器（全專案唯一環境）
RAG_PY="${RAG_PY:-.venv-rag/bin/python}"

# ── 配置目錄自動推導（勿硬寫目錄名） ──────────────────────────────
# 本檔位於 <配置目錄>/hooks/hook-utils.sh，往上一層即配置目錄本身。
# 因此 `mv .claude-roompilot .claude` 啟用後，以下值自動變為 .claude，
# hook 不會再因為找不到 .claude-roompilot 而失敗。
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)}"
CLAUDE_DIR_NAME="${CLAUDE_DIR_NAME:-$(basename "$CLAUDE_CONFIG_DIR")}"
# 極端情況（無法解析路徑）才退回目前的目錄名，避免變數為空導致路徑組成 "/logs"
[ -n "$CLAUDE_DIR_NAME" ] || CLAUDE_DIR_NAME=".claude-roompilot"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${CYAN}[INFO]${NC} [$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} [$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} [$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} [$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_debug() {
    if [ "$TASKMASTER_DEBUG" = "true" ]; then
        echo -e "${PURPLE}[DEBUG]${NC} [$(date '+%Y-%m-%d %H:%M:%S')] $1"
    fi
}

# 檢查必要檔案是否存在
# （原模板檢查 taskmaster.js / VibeCoding 範本；本專案改檢查 RAG 管線關鍵資產）
check_required_files() {
    local project_root="$1"
    local claude_dir="$project_root/$CLAUDE_DIR_NAME"

    log_debug "檢查必要檔案: $claude_dir"

    # 檢查 RAG 管線核心檔案（相當於原模板的「TaskMaster 核心檔案」）
    if [ ! -f "$project_root/rag_pipeline/retriever.py" ]; then
        log_error "RAG 檢索核心不存在: rag_pipeline/retriever.py"
        return 1
    fi

    # 檢查 hooks 配置
    if [ ! -f "$claude_dir/hooks-config.json" ]; then
        log_warning "Hooks 配置檔案不存在: $claude_dir/hooks-config.json"
    fi

    # 檢查 SSOT 文件目錄（相當於原模板的 VibeCoding 範本目錄）
    if [ ! -d "$project_root/docs" ]; then
        log_warning "SSOT 文件目錄不存在: $project_root/docs（RAG檢索系統說明.md 等）"
    fi

    # 檢查向量索引（ChromaDB collection furniture_v3，9,349 筆）
    if [ ! -d "$project_root/chroma_db" ]; then
        log_warning "ChromaDB 索引不存在: chroma_db/ → 先跑 $RAG_PY rag_pipeline/embed_v3.py"
    fi

    # 檢查六風格詞表與檢索群組表
    if [ ! -f "$project_root/vlm_annotation/taxonomy_v2.json" ]; then
        log_warning "六風格詞表不存在: vlm_annotation/taxonomy_v2.json"
    fi
    if [ ! -f "$project_root/rag_pipeline/category_groups.json" ]; then
        log_warning "檢索群組表不存在: rag_pipeline/category_groups.json"
    fi

    return 0
}

# 檢查 TaskMaster 初始化狀態
check_taskmaster_status() {
    local project_root="$1"
    local claude_dir="$project_root/$CLAUDE_DIR_NAME"
    local data_dir="$claude_dir/taskmaster-data"

    if [ -f "$data_dir/project.json" ]; then
        log_debug "TaskMaster 已初始化"
        return 0
    else
        log_debug "TaskMaster 尚未初始化"
        return 1
    fi
}

# 獲取專案資訊
get_project_info() {
    local project_root="$1"
    local claude_dir="$project_root/$CLAUDE_DIR_NAME"
    local project_file="$claude_dir/taskmaster-data/project.json"

    if [ -f "$project_file" ] && command -v jq >/dev/null 2>&1; then
        local project_name=$(jq -r '.name // "RoomPilot 家具風格檢索系統"' "$project_file")
        local project_phase=$(jq -r '.currentPhase // "未知階段"' "$project_file")

        echo "專案名稱: $project_name"
        echo "當前階段: $project_phase"
    else
        echo "專案資訊: 無法讀取"
    fi
}

# 顯示 TaskMaster 狀態摘要（彩色版本）
show_taskmaster_summary() {
    local project_root="$1"
    local claude_dir="$project_root/$CLAUDE_DIR_NAME"

    if check_taskmaster_status "$project_root"; then
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${BLUE}  📊 TaskMaster 狀態摘要（RoomPilot）${NC}"
        echo ""
        get_project_info "$project_root" | while IFS= read -r line; do
            echo -e "  ${WHITE}$line${NC}"
        done
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
    fi
}

# 檢查是否為文檔檔案
is_document_file() {
    local file_path="$1"

    case "$file_path" in
        *.md|*.markdown|*.rst|*.txt|*.doc|*.docx)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 檢查是否為專案文檔
is_project_document() {
    local file_path="$1"

    if is_document_file "$file_path" && [[ "$file_path" == *"docs/"* ]]; then
        return 0
    else
        return 1
    fi
}

# 檢查是否為 SSOT 契約文件
# （原模板的 is_vibecoding_template；本專案對應物 = docs/ 三份說明 + 兩份 README + 交付規格）
is_ssot_document() {
    local file_path="$1"

    case "$file_path" in
        *"docs/RAG檢索系統說明.md"|*"docs/query_parser_spec.md"|*"docs/GLB標註pipeline執行說明.md")
            return 0
            ;;
        *"rag_pipeline/README.md"|*"json_adjustment/RAGSQL.md"|*"json_adjustment/i_need_rag.md")
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 檢查是否為 RAG 管線程式碼（rag_pipeline / json_adjustment / vlm_annotation 的 .py）
is_pipeline_source() {
    local file_path="$1"

    if [[ "$file_path" == *.py ]] && {
        [[ "$file_path" == *"rag_pipeline/"* ]] ||
        [[ "$file_path" == *"json_adjustment/"* ]] ||
        [[ "$file_path" == *"vlm_annotation/"* ]]
    }; then
        return 0
    else
        return 1
    fi
}

# 檢查是否為受管控的資料契約 JSON
# （taxonomy_v2.json 六風格詞表、category_groups.json 19 群組、rag_dataset/ 資料集）
is_data_contract_json() {
    local file_path="$1"

    case "$file_path" in
        *"vlm_annotation/taxonomy_v2.json"|*"rag_pipeline/category_groups.json")
            return 0
            ;;
        *"rag_dataset/"*.json|*"rag_export/"*.json)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 檢查是否為金鑰檔案（.anthropic_key 為純文字檔，已列入 .gitignore，絕不可回顯內容）
is_secret_file() {
    local file_path="$1"

    case "$file_path" in
        *".anthropic_key"|*".env"|*".env."*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# 檢查文字內容是否夾帶 Anthropic 金鑰字面值
contains_anthropic_key() {
    local content="$1"

    if [[ "$content" == *"sk-ant-"* ]]; then
        return 0
    else
        return 1
    fi
}

# 檢查是否為 TaskMaster 核心檔案
is_taskmaster_core() {
    local file_path="$1"

    if [[ "$file_path" == *"/$CLAUDE_DIR_NAME/taskmaster"* ]] || [[ "$file_path" == *"/$CLAUDE_DIR_NAME/hooks"* ]]; then
        return 0
    else
        return 1
    fi
}

# 觸發 TaskMaster 處理器
# 註：本專案沒有 JavaScript 執行環境，處理器一律是 Python，
#     位置為 <配置目錄>/taskmaster.py（**尚未建置**，不存在時靜默跳過，不影響 hook 流程）
trigger_taskmaster() {
    local project_root="$1"
    local hook_type="$2"
    shift 2
    local additional_args="$@"

    local claude_dir="$project_root/$CLAUDE_DIR_NAME"
    local taskmaster_py="$claude_dir/taskmaster.py"
    local py_bin="$project_root/$RAG_PY"

    if [ -f "$taskmaster_py" ] && [ -x "$py_bin" ]; then
        log_debug "觸發 TaskMaster 處理器: $hook_type"
        cd "$project_root" || return 1
        "$py_bin" "$taskmaster_py" --hook-trigger="$hook_type" $additional_args
        return $?
    else
        log_debug "TaskMaster Python 處理器尚未建置，跳過: $taskmaster_py"
        return 0
    fi
}

# 顯示駕駛員通知（彩色版本）
show_driver_notification() {
    local title="$1"
    local message="$2"
    local actions="$3"

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${PURPLE}  $title${NC}"
    echo ""

    # 分行顯示訊息
    echo "$message" | fold -s -w 56 | while IFS= read -r line; do
        echo -e "  ${WHITE}$line${NC}"
    done

    if [ -n "$actions" ]; then
        echo ""
        echo "$actions" | while IFS= read -r line; do
            echo -e "  ${YELLOW}$line${NC}"
        done
    fi

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# 驗證環境
validate_environment() {
    local project_root="$1"

    log_debug "驗證 RoomPilot hook 環境"

    # 檢查專案 Python 環境（本專案唯一執行環境為 .venv-rag/）
    if [ ! -x "$project_root/$RAG_PY" ]; then
        log_error "找不到專案 Python 環境: $RAG_PY（Python 3.11.15，RAG 管線唯一環境）"
        return 1
    fi

    # 檢查 jq（所有 hook 解析 stdin JSON 都仰賴 jq）
    if ! command -v jq >/dev/null 2>&1; then
        log_warning "jq 未安裝，hook 將無法解析 stdin JSON（功能降級但不阻擋）"
    fi

    # 檢查基本目錄結構
    if [ ! -d "$project_root/$CLAUDE_DIR_NAME" ]; then
        log_error "Claude 配置目錄不存在: $project_root/$CLAUDE_DIR_NAME"
        return 1
    fi

    # 檢查必要檔案
    if ! check_required_files "$project_root"; then
        return 1
    fi

    log_success "RoomPilot hook 環境驗證通過"
    return 0
}
