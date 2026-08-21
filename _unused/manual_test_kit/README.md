# manual_test_kit — 直接測試「最後一步」（生圖 + 設計手冊 PDF）

一鍵把 agent pipeline（`MasterAgent` → 生圖 → `ReportAgent`）從問卷跑到
**設計手冊 PDF**，用來驗證「客廳日光 + 夜間兩張圖都進手冊」這個功能。

> 這條路徑（`backend/agent/`）就是客廳夜間光影功能所在。
> Bella 線上第 8 步（`backend/server/ai_render_service.py`）的圖來自前端 payload，
> 不走這裡，也還沒接夜間圖。

## 怎麼跑

從 **repo 根目錄** 執行（用專案 venv 的 python）：

```bash
# 離線假圖模式（免金鑰、免網路，最快）
.venv/Scripts/python.exe manual_test_kit/run_manual_test.py

# 真實模式：真的打 OpenRouter 生圖（需 OPENROUTER_API_KEY）
.venv/Scripts/python.exe manual_test_kit/run_manual_test.py --real
```

輸出：`manual_test_kit/output/design_manual.pdf`

## 兩種模式差別

| | 影像 | 手冊前言/設計理念文字 | 家具候選 | 需要金鑰 |
|---|---|---|---|---|
| 離線（預設） | 假色塊：**日光=暖色 / 夜間=深藍**，圖上印 DAY/NIGHT | deterministic 底稿 | `data/` 假型錄 | 否 |
| `--real` | OpenRouter nano banana 實際生圖 | 真模型（LLM）撰寫 | `data/` 假型錄 | 是（`OPENROUTER_API_KEY`） |

離線模式的重點：日光和夜間用兩種顏色，翻開 PDF 第七章「渲染成果」就能一眼看到
**客廳有兩張、其他房只有一張**。

## 資料夾內容（改資料不用動程式）

```
manual_test_kit/
├─ run_manual_test.py          # 驅動腳本
├─ data/
│  ├─ layout_json.json         # 格局：客廳(living_room) + 主臥
│  ├─ questionnaire.json       # 問卷：風格/預算/材質/色卡/逐房需求
│  └─ furniture_candidates.json# 假家具型錄（離線 RAG 用；key=房名關鍵字）
└─ output/                     # 執行後產生 design_manual.pdf
```

- 想測不同房型：改 `layout_json.json`（客廳判定看 `room_type=="living_room"` 或房名含「客廳」）。
- 想換家具/風格/色卡：改 `questionnaire.json` 與 `furniture_candidates.json`。

## 預期結果（離線模式）

```
生圖紀錄：
  palette_compare   living   ...      (色卡比對 ×2)
  full_render       living   ...      (客廳日光)
  full_render_night living   ...      (客廳夜間)   ← 功能重點
  full_render       bedroom  ...      (主臥日光)
客廳夜間圖數量：1 → living
設計手冊 PDF：manual_test_kit/output/design_manual.pdf
```

## 備註

- 執行時 stdout 會印出每張圖的生圖提示詞（`genpic_info.py` 既有的 `print`），
  可順便檢查夜間那張結尾是「光影以夜晚室內燈光為主…」。
- 需求：專案 venv 已裝的 Pillow（PDF 排版與假圖都靠它），無額外依賴。
