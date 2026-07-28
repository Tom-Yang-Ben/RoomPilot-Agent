# StatusLine 自訂指南（RoomPilot 家具風格檢索系統）

> 檔案位置：`.claude-roompilot/statusline.sh`
> 除錯包裝：`.claude-roompilot/statusline-debug.sh`
> 註冊位置：`.claude-roompilot/settings.json` 的 `statusLine.command`

> **平台範圍：本專案只維護 macOS bash 版。**
> RoomPilot 只在本機 macOS（Apple Silicon，MPS 優先退 CPU）執行，
> 沒有 Windows／Linux 需求，因此 `statusline-linux.sh`、`statusline-go.exe` 已捨棄，
> 腳本內的 GNU `date -d`／`stat -c`、winget/apt/dnf 安裝分支也一併移除，
> 一律使用 BSD 版 `date -j`／`stat -f` 與 Homebrew。

---

## 運作原理

```
Claude Code 每次互動時
    │
    │  stdin 傳入 JSON
    │  （model、context_window、cost、cwd、workspace 等）
    ▼
statusline.sh 解析 + 格式化
    │
    │  stdout 回傳格式化字串
    ▼
Claude Code 渲染到終端底部
```

StatusLine 不是即時更新，而是**每次你送出訊息或收到回覆時刷新**。

---

## Claude Code 傳入的 JSON 結構

```json
{
  "session_id": "...",
  "model": { "id": "claude-opus-4-6[1m]", "display_name": "Opus 4.6 (1M context)" },
  "cwd": "/Users/<you>/Public/AIPE_03/final_term/Demo2/RAG",
  "context_window": {
    "context_window_size": 1000000,
    "used_percentage": 43,
    "current_usage": {
      "input_tokens": 1,
      "output_tokens": 125,
      "cache_creation_input_tokens": 209,
      "cache_read_input_tokens": 434498
    }
  },
  "cost": {
    "total_cost_usd": 41.65,
    "total_duration_ms": 16438711
  },
  "workspace": { "current_dir": "...", "project_dir": "..." },
  "version": "2.1.76",
  "output_style": { "name": "default" }
}
```

> 注意：沒有 `session.start_time` 和 `effortLevel` 欄位。
> Session 時間從 `cost.total_duration_ms` 計算，花費從 `cost.total_cost_usd` 取得。

---

## 目前顯示格式（Apple UI 風格）

```
🦁 Opus 4.6 (1M context) │ 🌊 43% (439k/1.0m) │ 📂 RoomPilot │ ⏱ 4h35m │ 💰 $42.84
⚡ ●●●○○○○○○○  28% 🔄 19:00
📅 ●●●●●●●●○○  79% 🔄 03/23 10:00
💳 ○○○○○○○○○○ $0.00/$50.00
```

**第一行：** 模型 icon+名 │ 水位 icon+Context% (token 數) │ 📂 專案標籤 🌿 分支（dirty 時加 💫）│ ⏱ 時間 │ 💰 花費  
**第二行起：** Rate Limit（⚡ 即時 / 📅 週期 / 💳 額外用量）

> **專案標籤**：本專案目錄名是 `RAG`，直接顯示看不出是哪個專案，
> 因此腳本偵測到 `.venv-rag/` 或 `rag_pipeline/app.py` 時會顯示 **RoomPilot**（`project_label` 變數）。
>
> **🌿 分支為什麼沒出現**：RoomPilot **專案尚未 git init**，
> `git rev-parse --is-inside-work-tree` 失敗，整個 git 區段自動略過。
> 日後 git init 後不需改腳本，會自動開始顯示分支與 💫 dirty 標記。

### 模型 Icon（動物／力量系）

| 模型 | Icon | 色彩 | 寓意 |
|------|------|------|------|
| Opus | 🦁 | Tesla Red | 獅王 — 最強、王者風範 |
| Sonnet | 🦅 | Electric Blue | 鷹 — 銳利、高視角 |
| Haiku | 🐦 | Neon Green | 鳥 — 輕盈、快速 |
| 未知 | 🤖 | Cyber Cyan | 機器人 — 通用 AI |

### Token 水位 Icon（依 Context 使用百分比）

| 水位 | % | Icon | 寓意 |
|------|---|------|------|
| 冷靜 | 0–29 | ❄️ | 冰雪 — 資源充裕 |
| 流動 | 30–49 | 🌊 | 海浪 — 穩定使用中 |
| 溫熱 | 50–69 | 🌡 | 溫度計 — 開始升溫 |
| 蒸氣 | 70–84 | ♨️ | 溫泉 — 高溫警告 |
| 燃燒 | 85–94 | 🔥 | 火焰 — 即將耗盡 |
| 爆炸 | 95+ | 💥 | 爆炸 — 緊急 |

### 其他 Icon

| 元素 | Icon | 寓意 |
|------|------|------|
| 資料夾 | 📂 | 打開的資料夾（本專案顯示 RoomPilot） |
| Git 分支 | 🌿 | 分支＝樹枝（尚未 git init，目前不顯示） |
| Git dirty | 💫 | 閃爍＝有未提交變動 |
| Session 時間 | ⏱ | 碼錶 |
| 花費 | 💰 | 錢袋 |
| Rate limit（即時） | ⚡ | 閃電 |
| Rate limit（週期） | 📅 | 日曆 |
| Rate limit（額外） | 💳 | 信用卡 |
| Reset time | 🔄 | 循環＝重置 |

---

## 修改方式

### 1. 顏色

在腳本開頭的 `Colors (Tesla High-Contrast)` 區段，格式為 `\033[38;2;R;G;Bm`：

```bash
red='\033[38;2;232;33;39m'        # Tesla Red #E82127
blue='\033[38;2;56;172;255m'      # Electric Blue #38ACFF
green='\033[38;2;0;230;118m'      # Neon Green #00E676
cyan='\033[38;2;0;229;255m'       # Cyber Cyan #00E5FF
orange='\033[38;2;255;167;38m'    # Amber #FFA726
yellow='\033[38;2;255;234;0m'     # Volt Yellow #FFEA00
white='\033[38;2;245;245;245m'    # Pure White #F5F5F5
silver='\033[38;2;176;190;197m'   # Tesla Silver #B0BEC5
gray='\033[38;2;120;120;130m'     # Steel Gray #787882
pink='\033[38;2;255;82;82m'       # Signal Red #FF5252（Git dirty 💫）
dim='\033[2m'                     # 淡化
reset='\033[0m'                   # 重置
```

**Tesla High-Contrast RGB 對照：**

| 顏色 | 名稱 | Hex | R | G | B | 用途 |
|------|------|-----|---|---|---|------|
| 紅 | Tesla Red | #E82127 | 232 | 33 | 39 | Opus 模型、危險、高使用率條 |
| 藍 | Electric Blue | #38ACFF | 56 | 172 | 255 | Sonnet 模型 |
| 綠 | Neon Green | #00E676 | 0 | 230 | 118 | Haiku、低使用率、Git 分支文字 |
| 青 | Cyber Cyan | #00E5FF | 0 | 229 | 255 | 目錄名、未知模型 |
| 橘 | Amber | #FFA726 | 255 | 167 | 38 | 中高使用率 |
| 黃 | Volt Yellow | #FFEA00 | 255 | 234 | 0 | 花費、中使用率 |
| 白 | Pure White | #F5F5F5 | 245 | 245 | 245 | 一般文字 |
| 銀 | Tesla Silver | #B0BEC5 | 176 | 190 | 197 | 輔助文字 |
| 灰 | Steel Gray | #787882 | 120 | 120 | 130 | 淡化元素 |
| 粉紅 | Signal Red | #FF5252 | 255 | 82 | 82 | Git dirty 標記 |

---

### 2. 分隔符

```bash
sep=" ${dim}│${reset} "          # 目前（box drawing）
sep=" ${dim}|${reset} "          # 普通 pipe
sep=" ${dim}·${reset} "          # 中點
sep="  "                          # 純空格
sep=" ${dim}»${reset} "          # 箭頭
```

---

### 3. 進度條

在 `build_bar` 函式中修改符號：

```bash
# 目前（圓形）
filled_str+="●"    empty_str+="○"

# 方塊
filled_str+="█"    empty_str+="░"

# ASCII
filled_str+="="    empty_str+="-"

# 方形
filled_str+="■"    empty_str+="□"
```

**進度條寬度：** 搜尋 `bar_width=10`，改為想要的格數。

**Token 水位 icon：** 在 `level_icon_for_pct` 依 Context 使用百分比回傳 emoji（見「Token 水位 Icon」表）；改區間閾值時編輯該函式。

---

### 4. 第一行元素

在 `# Build line 1` 區段調整（模型 icon／顏色由 `model_name_lc` 的 `case` 設定 `model_icon`、`model_color`）：

```bash
# 目前順序
1. 模型 icon+名   ${model_color}${model_icon} ${model_name}${reset}
2. 水位+Context%  ${level_icon} ${pct_color}${pct_used}%${reset} (${used_tokens}/${total_tokens})
3. 📂 專案標籤    ${cyan}📂 ${project_label}${reset}   ← 偵測到 .venv-rag/ 就顯示 RoomPilot
4. 🌿 Git 分支    ${green}🌿 ${git_branch}${reset}${pink}💫${reset}  ← 有 git；dirty 時加 💫
5. ⏱ Session 時間 ${white}⏱ ${session_duration}${reset}  ← 有值才顯示
6. 💰 花費        ${yellow}💰 ${total_cost}${reset}     ← > $0.00 才顯示
```

**改回顯示原始目錄名（`RAG`）：** 把 `${project_label}` 換成 `${dirname}`。

**加上其他 RoomPilot 狀態：** `project_label` 那段是加料的好位置，例如索引是否存在
（`[ -d "$cwd/chroma_db" ]` → collection `furniture_v3` 已建）；
但每次互動都會執行，**只放檔案存在檢查，不要在此呼叫 `.venv-rag/bin/python`**（會拖慢每次刷新）。

**刪除 Session 時間：** 註解掉對應 `if` 區塊。

**刪除花費：** 註解掉對應 `if` 區塊。

**只顯示 % 不顯示 token 數：** 拿掉 `${dim}(${used_tokens}/${total_tokens})${reset}` 那段。

---

### 5. Rate Limit 區段

**修改標籤：**
```bash
# 目前（icon 風格）
${white}⚡${reset}    ${white}📅${reset}    ${white}💳${reset}

# 文字風格
${white}current${reset}    ${white}weekly${reset}    ${white}extra${reset}

# 縮寫
${white}5h${reset}         ${white}7d${reset}         ${white}ex${reset}
```

**修改重置符號：**
```bash
${dim}🔄${reset}           # 目前（循環 icon）
${dim}⟳${reset}            # Unicode 符號
${dim}reset${reset}        # 文字
${dim}→${reset}            # 箭頭
```

**完全隱藏 Rate Limit：** 註解掉輸出最後一行
```bash
printf "%b" "$line1"
# [ -n "$rate_lines" ] && printf "\n%b" "$rate_lines"
```

**隱藏 Extra 用量：** 註解掉 `extra_enabled` 整個 if 區塊

---

### 6. 使用率顏色閾值

在 `color_for_pct` 函式中調整：

```bash
# 目前
>= 90%  紅色
>= 70%  黃色
>= 50%  橘色
< 50%   綠色

# 更寬鬆
>= 95%  紅色
>= 80%  黃色
>= 60%  橘色
< 60%   綠色
```

---

### 7. Rate Limit 快取時間

```bash
cache_max_age=60     # 目前（60 秒查一次 API）
cache_max_age=30     # 更頻繁
cache_max_age=300    # 更省流量（5 分鐘）
```

---

## 預設樣式範本

### 精簡風格

```
🦁 Opus 4.6 │ 🌊 43% │ 📂 RoomPilot │ 💰 $42.84
```

做法：移除 token 數、session 時間、整個 rate limit。

### 完整風格（目前，Apple UI）

```
🦁 Opus 4.6 (1M context) │ 🌊 43% (439k/1.0m) │ 📂 RoomPilot │ ⏱ 4h35m │ 💰 $42.84
⚡ ●●●○○○○○○○  28% 🔄 19:00
📅 ●●●●●●●●○○  79% 🔄 03/23 10:00
💳 ○○○○○○○○○○ $0.00/$50.00
```

> 日後 `git init` 之後，第一行會多出 `🌿 feat/retriever-weights💫` 這段。

### 方塊風格

```
🦁 Opus 4.6 │ 🌊 43% (439k/1.0m) │ 📂 RoomPilot │ ⏱ 4h35m │ 💰 $42.84
⚡ █░░░░░░░░░  12%  🔄 19:00
📅 ████████░░  79%  🔄 03/23
```

做法：進度條改 `█░`。

### 批次工作風格（跑 embed_v3 建索引時）

```
🐦 Haiku 4.5 │ ❄️ 12% (24k/200k) │ 📂 RoomPilot │ ⏱ 27m │ 💰 $7.02
📅 ████████░░  79%  🔄 03/23
```

做法：全量建索引（約 27 分鐘）與六風格全量判定（約 US$7）都是長時間批次，
只留 ⏱／💰 與 📅 週期額度，隱藏 ⚡ 即時額度以免整排跳動。

---

## 時間追蹤持久化

StatusLine 除了顯示資訊外，還負責**開發時間追蹤**的資料持久化：

### 運作方式

```
StatusLine 每次更新時
    │
    │  從 JSON 取得 total_duration_ms、cost_usd、session_id
    │  從 .current-task 讀取當前 WBS 任務
    ▼
寫入 .claude-roompilot/taskmaster-data/.session-snapshot（覆寫）
    │
    │  下次 session 啟動時（session-start.sh）
    ▼
歸檔到 .claude-roompilot/taskmaster-data/timelog.jsonl（追加）
    │
    │  使用 /time-log 查看
    ▼
按日期/按 WBS 任務彙總顯示報表
```

### 相關檔案

| 檔案 | 用途 |
|------|------|
| `.session-snapshot` | 暫存當前 session 的最新 duration（每次 StatusLine 更新覆寫） |
| `.session-start` | 記錄本次 session 開始時間 |
| `.current-task` | 當前進行中的 WBS 任務編號（由 `/task-next` 寫入） |
| `timelog.jsonl` | 歸檔的時間日誌（每 session 一筆，JSON Lines 格式） |

### 資料格式（timelog.jsonl）

```json
{"session_id":"abc","date":"2026-07-28","start":"14:07","duration_ms":3600000,"cost_usd":12.50,"task":"2.1"}
```

> 範例：`task` `2.1` 對應 WBS 上的「retriever 排序權重調校」這類 RoomPilot 任務編號，
> 由 `/task-next` 寫入 `.claude-roompilot/taskmaster-data/.current-task`。

---

## 修改後生效

改完 `.claude-roompilot/statusline.sh` 後，**不需要重啟 Claude Code**。下次互動時自動使用新腳本。

---

## 除錯

### 方法 1：手動測試

在專案根目錄（`RAG/`）執行，`cwd` 帶入當前路徑才看得到 📂 RoomPilot 標籤：

```bash
echo '{"model":{"display_name":"Test"},"context_window":{"context_window_size":1000000,"used_percentage":43,"current_usage":{"input_tokens":1,"cache_creation_input_tokens":209,"cache_read_input_tokens":434498}},"cost":{"total_cost_usd":42.84,"total_duration_ms":16438711},"cwd":"'$(pwd)'"}' | bash .claude-roompilot/statusline.sh
```

### 方法 2：抓取 Claude Code 真實 JSON

1. 把 settings.json 的 statusline command 改為：
   ```json
   "command": "bash .claude-roompilot/statusline-debug.sh"
   ```

2. 互動一次後查看：
   ```bash
   cat /tmp/statusline-debug.json
   ```

3. 確認完改回：
   ```json
   "command": "bash .claude-roompilot/statusline.sh"
   ```

### 方法 3：確認 jq 可用

```bash
which jq || echo "jq 未安裝"
# macOS（本專案唯一支援的平台）：
brew install jq
# 腳本已內建 Homebrew 路徑備援：/opt/homebrew/bin/jq、/usr/local/bin/jq、~/.local/bin/jq
```

### 方法 4：語法檢查

改完腳本後先過語法檢查再交給 Claude Code：

```bash
bash -n .claude-roompilot/statusline.sh && echo "SYNTAX OK"
```

### 畫面上 emoji 與數字疊在一起

部分終端（含內嵌終端）對 emoji 的**顯示寬度**與**游標前進格數**不一致，後面的 `%`、括號內 token 會與水位 icon 重疊。腳本已在各 emoji 後多補空格並在區段間加 `${reset}`；若仍異常，可改用等寬字型或縮短第一行（精簡風格）。
