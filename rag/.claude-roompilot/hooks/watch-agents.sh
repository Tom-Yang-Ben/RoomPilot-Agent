#!/bin/bash

# Agent Activity Real-time Monitor（RoomPilot 家具風格檢索系統專用）
# 用法: bash <配置目錄>/hooks/watch-agents.sh [options]（例：bash .claude-roompilot/hooks/watch-agents.sh）
#
# Options:
#   --json     顯示結構化 JSONL 格式
#   --last N   顯示最近 N 行記錄
#   --clear    清除所有 log
#   --summary  依 agent 類型／事件統計
#
# 建議在第二個終端機視窗執行（本專案一律本機 macOS 執行，無 CI、無容器化部署）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# 配置目錄由本腳本位置推導（勿硬寫目錄名）——改名為 .claude/ 啟用後自動跟著走
CLAUDE_DIR="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd)"
LOG_DIR="$CLAUDE_DIR/logs"
LOG_FILE="$LOG_DIR/agent-activity.log"
LOG_JSONL="$LOG_DIR/agent-activity.jsonl"

case "${1:-}" in
    --json)
        echo "Watching JSONL log (Ctrl+C to stop)..."
        echo ""
        tail -f "$LOG_JSONL" 2>/dev/null | while IFS= read -r line; do
            echo "$line" | jq '.' 2>/dev/null || echo "$line"
        done
        ;;
    --last)
        N="${2:-20}"
        echo "=== Last $N agent activities ==="
        echo ""
        tail -n "$N" "$LOG_FILE" 2>/dev/null || echo "No log file yet."
        ;;
    --clear)
        rm -f "$LOG_FILE" "$LOG_JSONL"
        echo "Agent activity logs cleared."
        ;;
    --summary)
        echo "=== Agent Activity Summary ==="
        echo ""
        if [ -f "$LOG_JSONL" ]; then
            echo "Total events: $(wc -l < "$LOG_JSONL")"
            echo ""
            echo "By agent type:"
            jq -r '.agent_type' "$LOG_JSONL" 2>/dev/null | sort | uniq -c | sort -rn
            echo ""
            echo "By event:"
            jq -r '.event' "$LOG_JSONL" 2>/dev/null | sort | uniq -c | sort -rn
        else
            echo "No activity recorded yet."
        fi
        ;;
    *)
        echo "Watching agent activity log (Ctrl+C to stop)..."
        echo "Tip: Open a separate terminal and run this command"
        echo ""
        # 顯示既有內容 + 即時追蹤
        tail -f "$LOG_FILE" 2>/dev/null || {
            echo "No log file yet. Waiting for first agent activity..."
            # 等待檔案建立
            while [ ! -f "$LOG_FILE" ]; do sleep 1; done
            tail -f "$LOG_FILE"
        }
        ;;
esac
