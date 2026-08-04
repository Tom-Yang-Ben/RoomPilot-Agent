---
name: roompilot-budget
description: RoomPilot 工程預算報告產生 skill — 把 ReportPayload 排成可交付的工程估價與排程文件（含工程量、逐項明細、初步排程、水電空調建議、風險待確認、台灣市場行情參考），附列印樣式可直接存 PDF。文件零 LLM 文字，全部欄位取自 payload，並以一致性腳本核對。當使用者要工程報價單、預算書、估價明細、施工排程或要把工程報告交給客戶／廠商時使用。
origin: RoomPilot-Agent 專案原生
---

<!-- 繁中：本 skill 只產生新檔案，不修改 backend、不動 Bella 的 report_html 與任何 static 檔。 -->

# RoomPilot Budget

> 資料來源：`POST /api/v1/projects/{id}/engineering-packages` 產出的 ReportPayload
> 工程報告本體（`report_html`／`estimate_xlsx`）：`backend/server/engineering/`（owner: Bella），**本 skill 不碰**
> 商業提案（同源另一份文件）：`roompilot-proposal`

## 這個 skill 存在的理由

`ReportPayload` 裡的東西已經算完了——工程量、逐項估價、排程、風險。但 `report_json`
是給機器讀的，`report_html` 是系統的既定版面，`estimate_xlsx` 需要 Node 的
`@oai/artifact-tool`（且該路徑目前沒有測試覆蓋）。

本 skill 補的是**第四種出口**：一份排版完整、可直接列印成 PDF 交給客戶或廠商的預算書，
外加一個既有管線做不到的東西——**台灣市場行情參考區塊**。

行情資料（`taiwan_renovation_price_seed.json`）早就在 repo 裡，但**沒有任何程式讀它**。
不接進 `CostService` 是刻意的：依 `PRICE_AND_PRODUCTIVITY_POLICY.md` 的價格優先順序，
它屬「公開資料參考」，而政策明文「網路文章價格 ≠ 廠商正式報價」。所以它只能**並列參考**，
不能進小計——這也讓本 skill 完全不必動 `ReportPayload` 契約。

## 與商業提案的分工

| | `roompilot-proposal` | 本 skill |
| :--- | :--- | :--- |
| 對象 | 屋主 | 屋主／廠商／工班 |
| 目的 | 說服 | 落地與詢價 |
| LLM 文字 | 風格故事、空間敘事 | **零** |
| 主要防線 | 擋 LLM 編造數字 | 擋排版時弄錯資料 |

兩份共用同一個 `snapshot_hash`，所以客戶拿兩份對照時數字必然一致。

## 何時啟動

- 使用者要預算書、估價單、報價明細、工程排程
- 要把工程報告交給廠商詢價
- 想知道系統算出來的價格跟台灣行情差多少

## 邊界：這個 skill 不做什麼

| 不做 | 原因／誰做 |
| :--- | :--- |
| 修改 `documents.py`、`report_html`、任何 `static/` 檔案 | 那是 Bella 的產出格式，本 skill 只生**新檔案** |
| 把行情帶進估價小計 | 違反價格優先順序政策，且會製造假總價 |
| 自己算面積、單價、工期 | 全部取自 payload。缺價就是缺價，不補猜 |
| 產出 xlsx | 需要 `@oai/artifact-tool`；本 skill 走 HTML→PDF |
| 判斷承重牆、迴路、防水規格 | 一律列待專業確認，系統不自動判定 |

---

## 工作流

### 步驟 1：取得 ReportPayload

與 `roompilot-proposal` 完全相同（三條路：跑中的服務 API／既有檔案／測試客戶端示範資料）。
revision 未鎖定會回 `409 REVISION_NOT_LOCKED`。

```bash
BASE=http://localhost:8000
curl -s -X POST $BASE/api/v1/projects/$PID/engineering-packages \
  -H 'content-type: application/json' -d "{\"revision\":\"$REV\",\"documents\":[\"report_json\"]}"
curl -s $BASE/api/v1/jobs/<job_id>                    # 輪詢到 completed
curl -s $BASE/api/v1/packages/<package_id> > report_payload.json
```

### 步驟 2：先確認這份 payload 是什麼模式

**這一步不能跳。** 交付前你必須知道自己手上是示範價還是真實價：

```bash
python3 -c "
import json; p=json.load(open('report_payload.json')); e=p['estimate']
print('demo_mode      ', p['demo_mode'])
print('已知小計       ', e['known_subtotal'])
print('預估總額       ', e['estimated_total'])
print('待詢價工項     ', e['pending_quote_count'], '/', len(e['lines']))
print('價格來源       ', {l['price_region'] for l in e['lines']})
"
```

| 看到什麼 | 意思 | 交付時要說什麼 |
| :--- | :--- | :--- |
| `demo_mode: True`、`price_region: DEMO_ONLY` | 合成示範價 | **必須**口頭與書面都聲明「非市場報價」 |
| `pending_quote` 等於工項總數、`estimated_total: None` | 正式模式但尚無廠商報價 | 說明這是詢價用清單，金額待廠商填 |
| 部分 priced、部分 pending | 混合 | 說清楚總額只涵蓋已有價格的部分 |

### 步驟 3：排版

```bash
python3 .claude/skills/roompilot-budget/build_budget.py \
  --payload report_payload.json --out budget_report.html
```

產出七節：工程量 → 估價明細 → 初步排程 → 水電空調建議 → 風險待確認 →
市場行情參考 → 前提與排除。

`--no-market-reference` 可拿掉行情區塊（例如客戶只要純估價單時）。

### 步驟 4：核對一致性（不可略過）

```bash
python3 .claude/skills/roompilot-budget/verify_budget.py \
  --payload report_payload.json --html budget_report.html
```

八項檢查：明細行數、逐行小計、待詢價不得有金額、已知小計、排程作業數、總工期、
示範聲明是否保留、行情數字是否混入估價。任何一項不符就 FAIL。

### 步驟 5：交付

HTML 自帶 `@media print`（A4、表頭跨頁重複、列不被切斷）。瀏覽器「列印 → 另存 PDF」即可。

---

## 鐵律

1. **缺價就是缺價。** `pending_quote` 的工項顯示「待詢價」，永遠不補值、不估、不用行情頂替。
2. **行情不是報價。** 第六節與第二節之間沒有任何數字往來，核對腳本會驗。
3. **示範聲明不得移除。** `demo_mode=true` 時聲明是強制的，拿掉就是把合成價當真實價交出去。
4. **總額有條件才出現。** 只要還有一個工項待詢價，就不產生總額——寧可沒有數字，不要假數字。
5. **待確認事項照實列。** 承重牆、迴路、線徑、管徑、排水坡度、防水規格、空調容量、
   法規核准全部列在第五節，不得因為「客戶看了會擔心」而拿掉。
6. **文案改動後重跑核對。** 手動編輯過 HTML 就一定要重驗。

## 已知限制

1. **行情只有 6 個工項，且多數對不上。** 正式工項有 29 個；語意與單位都對得上的只有
   電力點位那兩項。文件的「與本報告工項的對應」欄位會逐項標明，不會假裝有覆蓋。
2. **不產 xlsx。** 需要 `@oai/artifact-tool`，且該測試目前是 skipped。
3. **Advanced RAG 的語意檢索目前是 Noop。** 第四節的建議來自 Structured Retrieval，
   `NoopEngineeringSemanticRetriever` 自己標示「這不是向量檢索」。
4. **這不是產品功能。** 使用者在瀏覽器按不到，每份報告都要由 agent 跑一次流程。

## 驗證與退出標準

```bash
python3 .claude/skills/roompilot-budget/verify_budget.py \
  --payload report_payload.json --html budget_report.html    # 必須 PASS
```

- 交付前用瀏覽器列印預覽確認表格沒有被切斷、表頭有跨頁重複。
- 與 `roompilot-proposal` 同時交付時，比對兩份頁尾的 `snapshot_hash` 必須相同。
- `demo_mode=true` 的文件，交付時再說一次那是示範價。
