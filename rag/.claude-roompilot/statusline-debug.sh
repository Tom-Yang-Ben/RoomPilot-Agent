#!/bin/bash
# RoomPilot 家具風格檢索系統 — StatusLine 除錯包裝（僅維護 macOS bash 版）
# 用法：把 <配置目錄>/settings.json 的 statusLine.command 暫時指向本檔
# 把 Claude Code 傳給 statusline 的原始 JSON 存到檔案，用於除錯
input=$(cat)
echo "$input" > /tmp/statusline-debug.json
# 同時正常執行 statusline
echo "$input" | bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/statusline.sh"
