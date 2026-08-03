---
name: roompilot-proposal
description: RoomPilot 商業提案簡報產生 skill — 把工程 ReportPayload 轉成給屋主看的設計提案文件。文案由 agent 寫，數字由腳本從 payload 取出，並以核對腳本擋下任何編造的數字。當使用者要做提案簡報、設計說明、給客戶看的成果文件，或要把工程報告轉成銷售用途時使用。
origin: RoomPilot-Agent 專案原生
---

<!-- 繁中：本 skill 只產生新檔案，不修改 backend、不動 Bella 的靜態檔與既有 report_html。 -->

# RoomPilot Proposal

> 資料來源：`POST /api/v1/projects/{id}/engineering-packages` 產出的 ReportPayload
> 工程報告本體（產出 B）：`backend/server/engineering/`（owner: Bella），**本 skill 不碰**
> 檢索需求轉譯：`roompilot-furniture-query`

## 這個 skill 存在的理由

系統已經能產出工程報告（`report_html` / `report_json`），那是給施工看的：面積、工項、
單價、工期。**屋主看不懂，也不會被說服。**

反過來，行銷簡報如果讓 LLM 自由發揮，會生出「28 坪只要 14.5 萬，比行情省 35%」這種
好看但全是幻覺的句子——而屋主真的會拿它去對報價單。

本 skill 的設計就是把這兩件事切開：

| 誰負責 | 內容 | 保證方式 |
| :--- | :--- | :--- |
| **agent** | 風格故事、空間敘事、開場收尾 | 自由發揮 |
| **腳本** | 面積、金額、工期、尺寸、材料、家具 | 直接從 payload 取，agent 碰不到 |
| **核對腳本** | 全文每一個數字 | 找不到出處就 FAIL |

## 何時啟動

- 使用者要「給客戶看的提案」「設計說明」「成果簡報」
- 已經有鎖定版本與工程報告，要轉成銷售用途
- 要把生圖、色卡、家具配置整理成一份可交付的文件

## 邊界：這個 skill 不做什麼

| 不做 | 原因／誰做 |
| :--- | :--- |
| 修改 `documents.py`、`report_html`、任何 `static/` 檔案 | 那是 Bella 的產出格式，本 skill 只生**新檔案** |
| 新增 API 端點、改前端頁面 | skill 跑在 agent 這端，不是產品功能——使用者在瀏覽器按不到 |
| 自己算面積、金額、工期 | 全部取自 payload。`ReportPayload` 已經算好，重算只會製造不一致 |
| 產出 xlsx | 需要 `@oai/artifact-tool`，且該路徑目前無測試覆蓋 |
| 判斷擺不擺得下 | `backend/engine/`（Ancai） |

---

## 工作流

### 步驟 1：取得 ReportPayload

三條路，擇一：

**A. 服務跑著（正式路徑）**

```bash
BASE=http://localhost:8000
PID=<project_id>; REV=D3
curl -s -X POST $BASE/api/v1/projects/$PID/engineering-packages \
  -H 'content-type: application/json' \
  -d "{\"revision\":\"$REV\",\"documents\":[\"report_json\"]}"      # → 202 JobStatus
curl -s $BASE/api/v1/jobs/<job_id>                                   # 輪詢到 completed
curl -s $BASE/api/v1/packages/<package_id> > report_payload.json
```

**B. 已經有檔案** — 直接用既有的 `report_payload.json`。

**C. 沒有真實專案，要跑通流程** — 用測試客戶端造一份示範資料
（`ROOMPILOT_DEMO_MODE=true`，見 `tests/test_engineering_documents_api.py` 的
`_project` / `_save_and_lock` 流程）。此時 `demo_mode=true`，**示範聲明必須留在文件上**。

> revision 未鎖定會回 `409 REVISION_NOT_LOCKED`。要先 lock 才生得出報告。

### 步驟 2：讀懂手上的素材

先看過 payload 再動筆，不要憑印象寫。至少確認這幾項：

```bash
python3 -c "
import json; p=json.load(open('report_payload.json'))
r=p['snapshot']['rooms']
print('房間', [(x['room_id'], x['name'], x.get('style')) for x in r])
print('生圖', [(x['room_id'], len(x.get('renders') or [])) for x in r])
print('demo_mode', p['demo_mode'])
for k,v in p['narratives'].items(): print(k, ':', v)
"
```

`narratives` 是既有的**事實底稿**（五段：design／construction／cost／schedule／risk
summary）。你的文案要與它一致，不是取代它——腳本會把其中三段原樣放進文件。

### 步驟 3：寫 prose.json

```json
{
  "hero_title": "把光留下來，其餘的讓木頭說話",
  "hero_subtitle": "一句話說完這個空間的主張",
  "style_card": "自然木質",
  "style_story": "設計理念。用 \\n\\n 分段。",
  "rooms": {
    "living-1": { "headline": "客廳：一個不急著被填滿的空間", "story": "空間敘事" }
  },
  "closing": "下一步"
}
```

- `style_card` 從該風格的三張色票挑一張（見 `references/style-voice.md`），決定提案的色帶。
- `rooms` 的鍵必須是 payload 裡真實的 `room_id`，寫錯會靜默略過那段文案。
- **文案裡不要出現任何數字。** 面積、金額、尺寸、工期腳本都會排版好；你寫了只會被核對腳本擋下來。

### 步驟 4：組版

```bash
python3 .claude/skills/roompilot-proposal/build_proposal.py \
  --payload report_payload.json --prose prose.json --out proposal.html \
  --base-url http://localhost:8000
```

`--base-url` 用來把生圖的相對路徑（`/api/projects/.../renders/...`）補成可載入的網址。
不給的話圖片會壞掉——交付前務必確認圖有出來。

### 步驟 5：核對數字（不可略過）

```bash
python3 .claude/skills/roompilot-proposal/verify_numbers.py \
  --payload report_payload.json --html proposal.html
```

- **PASS** → 文件裡每個數字都能在 payload 找到出處。
- **FAIL** → 逐項處理。改成引用 payload 既有欄位，或直接刪掉那個數字。
  **不要用 `--allow` 繞過**，那個參數是給年份之類真的與資料無關的數字用的，而且會在報告上被標出來。

### 步驟 6：交付

HTML 自帶 `@media print`（A4、避免圖與表格跨頁截斷）。瀏覽器直接「列印 → 另存 PDF」
即可交付，不需要任何額外套件。

---

## 鐵律

1. **數字不准寫。** 這是唯一一條沒有例外的規則。步驟 5 會抓。
2. **示範資料的聲明必須留著。** `demo_mode=true` 時腳本會自動放上聲明區塊，不得移除——
   那是 DEMO_ONLY 合成價，不是市場報價。
3. **風格詞用系統的六風格與十八色票**，不要自創「侘寂輕奢風」這種混搭詞。
   屋主之後拿這個詞回來找家具會找不到（見 `roompilot-furniture-query`）。
4. **家電不是設計品項。** 冰箱、洗衣機、冷氣屬 `equipment_requirements`／MEP 建議，
   不要寫成「我們為您挑選的家電」。
5. **待確認事項不要美化掉。** 承重牆、迴路、防水規格、法規核准都列在 `risks`，
   提案可以不細講，但不能反過來宣稱「已完成評估」。
6. **兩份文件同源。** 提案與工程報告共用同一個 `snapshot_hash`，腳本會印在頁尾。
   屋主拿兩份對照時數字必須一致——這是這套做法最值錢的地方，別破壞它。

## 已知限制

1. **核對腳本擋得住「無中生有」，擋不住「碰巧撞上」。** payload 有近百個數字，
   編造的小整數可能剛好等於某個無關欄位（實測：`35%` 曾撞上 `daily_productivity=35.0`）。
   百分比已另立規則（`N%` 要求 `N/100` 有出處），但其他小整數仍有殘餘風險——
   所以鐵律 1 是「不准寫」，而不是「寫了再驗」。
2. **圖片靠 `--base-url`**，服務沒跑就載不到。要離線交付得自行把圖轉成 base64 內嵌。
3. **不產 xlsx**，也不重排 Bella 的 `report_html`。
4. **這不是產品功能。** 每份提案都要由 agent 執行一次流程，使用者無法自助產生。

## 驗證與退出標準

```bash
python3 .claude/skills/roompilot-proposal/verify_numbers.py \
  --payload report_payload.json --html proposal.html    # 必須 PASS
```

- 交付前用瀏覽器開一次，確認**生圖有載入**、列印預覽沒有把圖或表格切斷。
- `demo_mode=true` 的文件，交付時口頭與書面都要再說一次那是示範價。
- 文案改動後**一定要重跑核對**，不要只跑一次就當永久有效。
