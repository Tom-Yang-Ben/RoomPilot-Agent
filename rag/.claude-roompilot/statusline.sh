#!/bin/bash
# RoomPilot 家具風格檢索系統 — Claude Code StatusLine（僅維護 macOS bash 版）
# 設定於 .claude-roompilot/settings.json 的 statusLine.command
# 說明文件：<配置目錄>/STATUSLINE_GUIDE.md
set -f

# ── 配置目錄自動推導（勿硬寫目錄名） ────────────────────
# 本檔位於配置目錄根層；`mv .claude-roompilot .claude` 啟用後
# CLAUDE_DIR_NAME 自動變為 .claude，timelog 路徑不會失效。
CLAUDE_CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
CLAUDE_DIR_NAME="$(basename "$CLAUDE_CONFIG_DIR")"
[ -n "$CLAUDE_DIR_NAME" ] && [ "$CLAUDE_DIR_NAME" != "/" ] || CLAUDE_DIR_NAME=".claude-roompilot"

input=$(cat)

if [ -z "$input" ]; then
    printf "Claude"
    exit 0
fi

# ── jq PATH fix (macOS only) ────────────────────────────
# RoomPilot 只在 macOS（Apple Silicon）本機執行，因此只處理 Homebrew 的兩個安裝路徑。
# 沒有 Windows／Linux 需求：statusline-linux.sh、statusline-go.exe 已捨棄。
if ! command -v jq >/dev/null 2>&1; then
    for p in \
        "/opt/homebrew/bin/jq" \
        "/usr/local/bin/jq" \
        "$HOME/.local/bin/jq"; do
        if [ -x "$p" ]; then
            eval "jq() { \"$p\" \"\$@\"; }"
            export -f jq 2>/dev/null
            break
        fi
    done
fi

if ! command -v jq >/dev/null 2>&1; then
    printf "Claude (jq not found - install: brew install jq)"
    exit 0
fi

# ── Colors (Tesla High-Contrast) ───────────────────────
red='\033[38;2;232;33;39m'        # Tesla Red #E82127
blue='\033[38;2;56;172;255m'      # Electric Blue #38ACFF
green='\033[38;2;0;230;118m'      # Neon Green #00E676
cyan='\033[38;2;0;229;255m'       # Cyber Cyan #00E5FF
orange='\033[38;2;255;167;38m'    # Amber #FFA726
yellow='\033[38;2;255;234;0m'     # Volt Yellow #FFEA00
white='\033[38;2;245;245;245m'    # Pure White #F5F5F5
silver='\033[38;2;176;190;197m'   # Tesla Silver #B0BEC5（備用）
gray='\033[38;2;120;120;130m'     # Steel Gray #787882（備用）
pink='\033[38;2;255;82;82m'       # Signal Red / dirty #FF5252
dim='\033[2m'
reset='\033[0m'

sep=" ${dim}│${reset} "

# ── Helpers ─────────────────────────────────────────────
format_tokens() {
    local num=$1
    if [ "$num" -ge 1000000 ] 2>/dev/null; then
        awk "BEGIN {printf \"%.1fm\", $num / 1000000}"
    elif [ "$num" -ge 1000 ] 2>/dev/null; then
        awk "BEGIN {printf \"%.0fk\", $num / 1000}"
    else
        printf "%d" "$num"
    fi
}

color_for_pct() {
    local pct=$1
    if [ "$pct" -ge 90 ] 2>/dev/null; then printf "$red"
    elif [ "$pct" -ge 70 ] 2>/dev/null; then printf "$yellow"
    elif [ "$pct" -ge 50 ] 2>/dev/null; then printf "$orange"
    else printf "$green"
    fi
}

# Context % → 水位 icon（與 STATUSLINE_GUIDE「Token 水位」表一致）
level_icon_for_pct() {
    local pct=$1
    if [ "$pct" -lt 30 ] 2>/dev/null; then printf '%s' '❄️'
    elif [ "$pct" -lt 50 ] 2>/dev/null; then printf '%s' '🌊'
    elif [ "$pct" -lt 70 ] 2>/dev/null; then printf '%s' '🌡'
    elif [ "$pct" -lt 85 ] 2>/dev/null; then printf '%s' '♨️'
    elif [ "$pct" -lt 95 ] 2>/dev/null; then printf '%s' '🔥'
    else printf '%s' '💥'
    fi
}

build_bar() {
    local pct=$1
    local width=$2
    [ "$pct" -lt 0 ] 2>/dev/null && pct=0
    [ "$pct" -gt 100 ] 2>/dev/null && pct=100

    local filled=$(( pct * width / 100 ))
    local empty=$(( width - filled ))
    local bar_color
    bar_color=$(color_for_pct "$pct")

    local filled_str="" empty_str=""
    for ((i=0; i<filled; i++)); do filled_str+="●"; done
    for ((i=0; i<empty; i++)); do empty_str+="○"; done

    printf "${bar_color}${filled_str}${dim}${empty_str}${reset}"
}

# macOS 的 date 是 BSD 版：只走 `date -j -f`，不使用 GNU 的 `date -d`。
iso_to_epoch() {
    local iso_str="$1"
    local epoch
    local stripped="${iso_str%%.*}"
    stripped="${stripped%%Z}"
    stripped="${stripped%%+*}"
    stripped="${stripped%%-[0-9][0-9]:[0-9][0-9]}"
    epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$stripped" +%s 2>/dev/null)
    if [ -n "$epoch" ]; then
        echo "$epoch"
        return 0
    fi
    return 1
}

format_reset_time() {
    local iso_str="$1"
    local style="$2"
    [ -z "$iso_str" ] || [ "$iso_str" = "null" ] && return

    local epoch
    epoch=$(iso_to_epoch "$iso_str")
    [ -z "$epoch" ] && return

    local result=""
    case "$style" in
        time)
            # BSD date：以 epoch 反查（-r），24 小時制
            result=$(date -j -r "$epoch" +"%H:%M" 2>/dev/null)
            [ -z "$result" ] && result=$(date -j -r "$epoch" +"%l:%M%p" 2>/dev/null | sed 's/^ //; s/\.//g' | tr '[:upper:]' '[:lower:]')
            ;;
        datetime)
            result=$(date -j -r "$epoch" +"%m/%d %H:%M" 2>/dev/null)
            [ -z "$result" ] && result=$(date -j -r "$epoch" +"%b %-d, %l:%M%p" 2>/dev/null | sed 's/  / /g; s/^ //; s/\.//g' | tr '[:upper:]' '[:lower:]')
            ;;
    esac
    printf "%s" "$result"
}

# ── Extract JSON data ───────────────────────────────────
model_name=$(echo "$input" | jq -r '.model.display_name // "Claude"')
model_name_lc=$(printf '%s' "$model_name" | tr '[:upper:]' '[:lower:]')
case "$model_name_lc" in
    *opus*)   model_icon='🦁'; model_color=$red ;;
    *sonnet*) model_icon='🦅'; model_color=$blue ;;
    *haiku*)  model_icon='🐦'; model_color=$green ;;
    *)        model_icon='🤖'; model_color=$cyan ;;
esac

size=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')
[ "$size" -eq 0 ] 2>/dev/null && size=200000

input_tokens=$(echo "$input" | jq -r '.context_window.current_usage.input_tokens // 0')
cache_create=$(echo "$input" | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0')
cache_read=$(echo "$input" | jq -r '.context_window.current_usage.cache_read_input_tokens // 0')
current=$(( input_tokens + cache_create + cache_read ))

used_tokens=$(format_tokens $current)
total_tokens=$(format_tokens $size)

if [ "$size" -gt 0 ] 2>/dev/null; then
    pct_used=$(( current * 100 / size ))
else
    pct_used=0
fi

# ── Session duration from cost.total_duration_ms ────────
session_duration=""
total_duration_ms=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')
if [ "$total_duration_ms" -gt 0 ] 2>/dev/null; then
    elapsed=$(( total_duration_ms / 1000 ))
    if [ "$elapsed" -ge 3600 ] 2>/dev/null; then
        session_duration="$(( elapsed / 3600 ))h$(( (elapsed % 3600) / 60 ))m"
    elif [ "$elapsed" -ge 60 ] 2>/dev/null; then
        session_duration="$(( elapsed / 60 ))m"
    else
        session_duration="${elapsed}s"
    fi
fi

# ── Cost ────────────────────────────────────────────────
total_cost=$(echo "$input" | jq -r '.cost.total_cost_usd // 0' | awk '{printf "$%.2f", $1}')

# ── Context used percentage (from API) ──────────────────
pct_used_api=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
if [ -n "$pct_used_api" ] && [ "$pct_used_api" != "null" ]; then
    pct_used=$pct_used_api
fi

# ── LINE 1 ──────────────────────────────────────────────
pct_color=$(color_for_pct "$pct_used")
level_icon=$(level_icon_for_pct "$pct_used")
cwd=$(echo "$input" | jq -r '.cwd // ""')
[ -z "$cwd" ] || [ "$cwd" = "null" ] && cwd=$(pwd)
dirname=$(basename "$cwd")

# ── 專案標籤（RoomPilot 情境）───────────────────────────
# 目錄名是 RAG，直接顯示會看不出是哪個專案；
# 偵測到 .venv-rag/ 或 rag_pipeline/app.py 就判定為 RoomPilot 家具風格檢索系統。
project_label="$dirname"
if [ -d "$cwd/.venv-rag" ] || [ -f "$cwd/rag_pipeline/app.py" ]; then
    project_label="RoomPilot"
fi

# 注意：RoomPilot 專案尚未 git init，下列區段會整段略過（不顯示 🌿 分支）。
# 日後 git init 後不需修改腳本，會自動開始顯示分支與 dirty 標記。
git_branch=""
git_dirty=""
if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git_branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)
    if [ -n "$(git -C "$cwd" status --porcelain 2>/dev/null)" ]; then
        git_dirty="y"
    fi
fi

# Build line 1: icon+Model | 水位+pct% | 📂 dir 🌿 branch💫 | ⏱ | 💰
# 多數終端對 emoji 寬度與游標前進不一致，emoji 後多補一個空格避免與後續文字疊字。
line1="${model_color}${model_icon}  ${model_name}${reset}"
line1+="${sep}"
line1+="${level_icon}${reset}  ${pct_color}${pct_used}%${reset} ${dim}(${used_tokens}/${total_tokens})${reset}"
line1+="${sep}"
line1+="${cyan}📂  ${project_label}${reset}"
if [ -n "$git_branch" ]; then
    line1+=" ${green}🌿  ${git_branch}${reset}"
    [ -n "$git_dirty" ] && line1+="${pink}💫${reset}"
fi
if [ -n "$session_duration" ]; then
    line1+="${sep}"
    line1+="${white}⏱  ${session_duration}${reset}"
fi
if [ "$total_cost" != "\$0.00" ]; then
    line1+="${sep}"
    line1+="${yellow}💰  ${total_cost}${reset}"
fi

# ── OAuth token resolution ──────────────────────────────
get_oauth_token() {
    if [ -n "$CLAUDE_CODE_OAUTH_TOKEN" ]; then
        echo "$CLAUDE_CODE_OAUTH_TOKEN"
        return 0
    fi
    if command -v security >/dev/null 2>&1; then
        local blob
        blob=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
        if [ -n "$blob" ]; then
            local token
            token=$(echo "$blob" | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)
            if [ -n "$token" ] && [ "$token" != "null" ]; then
                echo "$token"; return 0
            fi
        fi
    fi
    # 注意：這是 Claude Code 自身的全域憑證檔（$HOME/.claude/），
    # 不是本專案的配置目錄（$CLAUDE_DIR_NAME），路徑不可改寫。
    local creds_file="${HOME}/.claude/.credentials.json"
    if [ -f "$creds_file" ]; then
        local token
        token=$(jq -r '.claudeAiOauth.accessToken // empty' "$creds_file" 2>/dev/null)
        if [ -n "$token" ] && [ "$token" != "null" ]; then
            echo "$token"; return 0
        fi
    fi
    # 第三順位：舊版 Claude Code 的 macOS 備援憑證檔（Linux 的 secret-tool 分支已移除）
    local legacy_creds="${HOME}/Library/Application Support/Claude/credentials.json"
    if [ -f "$legacy_creds" ]; then
        local token
        token=$(jq -r '.claudeAiOauth.accessToken // empty' "$legacy_creds" 2>/dev/null)
        if [ -n "$token" ] && [ "$token" != "null" ]; then
            echo "$token"; return 0
        fi
    fi
    echo ""
}

# ── Fetch usage data (cached) ──────────────────────────
cache_dir="${TMPDIR:-/tmp}/claude"
cache_file="${cache_dir}/statusline-usage-cache.json"
cache_max_age=60
mkdir -p "$cache_dir"

needs_refresh=true
usage_data=""

if [ -f "$cache_file" ]; then
    # macOS 是 BSD stat：取 mtime 用 -f %m（GNU 的 -c %Y 分支已移除）
    cache_mtime=$(stat -f %m "$cache_file" 2>/dev/null)
    now=$(date +%s)
    cache_age=$(( now - cache_mtime ))
    if [ "$cache_age" -lt "$cache_max_age" ] 2>/dev/null; then
        needs_refresh=false
        usage_data=$(cat "$cache_file" 2>/dev/null)
    fi
fi

if $needs_refresh; then
    token=$(get_oauth_token)
    if [ -n "$token" ] && [ "$token" != "null" ]; then
        response=$(curl -s --max-time 5 \
            -H "Accept: application/json" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $token" \
            -H "anthropic-beta: oauth-2025-04-20" \
            -H "User-Agent: claude-code/2.1.34" \
            "https://api.anthropic.com/api/oauth/usage" 2>/dev/null)
        if [ -n "$response" ] && echo "$response" | jq -e '.five_hour' >/dev/null 2>&1; then
            usage_data="$response"
            echo "$response" > "$cache_file"
        fi
    fi
    if [ -z "$usage_data" ] && [ -f "$cache_file" ]; then
        usage_data=$(cat "$cache_file" 2>/dev/null)
    fi
fi

# ── Rate limit lines ────────────────────────────────────
rate_lines=""

if [ -n "$usage_data" ] && echo "$usage_data" | jq -e . >/dev/null 2>&1; then
    bar_width=10

    five_hour_pct=$(echo "$usage_data" | jq -r '.five_hour.utilization // 0' | awk '{printf "%.0f", $1}')
    five_hour_reset_iso=$(echo "$usage_data" | jq -r '.five_hour.resets_at // empty')
    five_hour_reset=$(format_reset_time "$five_hour_reset_iso" "time")
    five_hour_bar=$(build_bar "$five_hour_pct" "$bar_width")
    five_hour_pct_color=$(color_for_pct "$five_hour_pct")
    five_hour_pct_fmt=$(printf "%3d" "$five_hour_pct")

    rate_lines+="${white}⚡${reset}  ${five_hour_bar} ${five_hour_pct_color}${five_hour_pct_fmt}%${reset}"
    [ -n "$five_hour_reset" ] && rate_lines+=" ${dim}🔄${reset}  ${white}${five_hour_reset}${reset}"

    seven_day_pct=$(echo "$usage_data" | jq -r '.seven_day.utilization // 0' | awk '{printf "%.0f", $1}')
    seven_day_reset_iso=$(echo "$usage_data" | jq -r '.seven_day.resets_at // empty')
    seven_day_reset=$(format_reset_time "$seven_day_reset_iso" "datetime")
    seven_day_bar=$(build_bar "$seven_day_pct" "$bar_width")
    seven_day_pct_color=$(color_for_pct "$seven_day_pct")
    seven_day_pct_fmt=$(printf "%3d" "$seven_day_pct")

    rate_lines+="\n${white}📅${reset}  ${seven_day_bar} ${seven_day_pct_color}${seven_day_pct_fmt}%${reset}"
    [ -n "$seven_day_reset" ] && rate_lines+=" ${dim}🔄${reset}  ${white}${seven_day_reset}${reset}"

    extra_enabled=$(echo "$usage_data" | jq -r '.extra_usage.is_enabled // false')
    if [ "$extra_enabled" = "true" ]; then
        extra_pct=$(echo "$usage_data" | jq -r '.extra_usage.utilization // 0' | awk '{printf "%.0f", $1}')
        extra_used=$(echo "$usage_data" | jq -r '.extra_usage.used_credits // 0' | awk '{printf "%.2f", $1/100}')
        extra_limit=$(echo "$usage_data" | jq -r '.extra_usage.monthly_limit // 0' | awk '{printf "%.2f", $1/100}')
        extra_bar=$(build_bar "$extra_pct" "$bar_width")
        extra_pct_color=$(color_for_pct "$extra_pct")

        rate_lines+="\n${white}💳${reset}  ${extra_bar} ${extra_pct_color}\$${extra_used}${dim}/${reset}${white}\$${extra_limit}${reset}"
    fi
fi

# ── Persist session duration for time tracking ──────────
# Write current session's duration to a temp file so session-start can finalize it
timelog_dir="$cwd/$CLAUDE_DIR_NAME/taskmaster-data"
if [ -d "$timelog_dir" ] && [ "$total_duration_ms" -gt 0 ] 2>/dev/null; then
    session_id=$(echo "$input" | jq -r '.session_id // ""')
    today=$(date '+%Y-%m-%d' 2>/dev/null)
    start_time=""
    [ -f "$timelog_dir/.session-start" ] && start_time=$(cat "$timelog_dir/.session-start" 2>/dev/null | head -1)
    total_cost_raw=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
    # Read current task if any
    current_task=""
    [ -f "$timelog_dir/.current-task" ] && current_task=$(cat "$timelog_dir/.current-task" 2>/dev/null | head -1)
    # Write snapshot (overwrite each time)
    cat > "$timelog_dir/.session-snapshot" 2>/dev/null <<SNAPSHOT
{"session_id":"${session_id}","date":"${today}","start":"${start_time}","duration_ms":${total_duration_ms},"cost_usd":${total_cost_raw},"task":"${current_task}"}
SNAPSHOT
fi

# ── Output ──────────────────────────────────────────────
printf "%b" "$line1"
[ -n "$rate_lines" ] && printf "\n%b" "$rate_lines"

exit 0
