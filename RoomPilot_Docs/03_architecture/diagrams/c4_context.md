# 系統情境圖 (C4 System Context) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（跨模組整合，依 `AGENTS.md` 目錄責任；本檔為 AI 衍生草稿，人工核准前為 TO-BE）
> **語域:** L3（工程；本檔為 drawio 生成規格）
> **實例:** 單例（每專案一張；多環境／future state 以分頁承載，不另開檔）
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c
>
> **定位**：C4 L1 溝通級 drawio 版的生成規格；與 [sad](../sad.md) §1.1 mermaid 二擇一，不得雙軌維護。系統內部歸 [c4_container](./c4_container.md)；視覺規範歸模板 [README](../../../VibeCoding_Workflow_Templates/03_architecture/diagrams/README.md)。ID 沿用 [../../00-registry.md](../../00-registry.md)。

## 目錄

- [1. 圖面資訊](#1-圖面資訊)
- [2. 生成 prompt](#2-生成-prompt)
- [3. 約束與檢查](#3-約束與檢查)
- [4. 待確認](#4-待確認)
- [5. 追溯](#5-追溯)

## 1. 圖面資訊

| 欄位 | 值 |
|---|---|
| 受眾 | 所有人（最通用、變動最慢的一張圖） |
| 回答的問題 | 誰在用 RoomPilot？它與哪些外部系統互動？ |
| 正典來源 | [sad](../sad.md) §1.1 |
| 最後校驗 | 2026-08-11（對照 git yen@8863a36c） |
| 階段 | Pilot（對外溝通時以本規格轉 drawio） |

## 2. 生成 prompt

畫 C4 System Context：中心＝**RoomPilot（AIPE03 第四組 AI 室內設計系統）**，一個圓角矩形邊界。內部僅以淡色分格示意「八步 FastAPI/Three.js 工作流（`backend/server/` ＋ `backend/server/static/`，單一 app，port 8002）」，不展開子系統（子系統歸 [c4_container](./c4_container.md)）。

**前置盤點（防 Partial Disclosure）**——完整清單如下，全部有程式碼證據：

| 類別 | 清單 |
|---|---|
| Actors | 使用者／室內設計師（同一 Web 入口走八步流程；設計師另用鎖定後的工程文件 MVP，`README.md:157-191`）。營運人員、管理員：**無**（無登入/後台證據，見 §4） |
| 外部系統 | ① OpenRouter（LLM/VLM/生圖統一閘道）② PostgreSQL 家具庫（Kai）③ AWS S3/CloudFront（GLB 與三視角圖）。訊息平台：無。備份系統：無。其餘素材（已驗證 JSON、surface_catalog、色卡）為 repo 內本地檔，不畫外部系統 |

### 2.1 元素

| 元素 | 類型 | 一句話責任（畫進圖內） | 證據 |
|---|---|---|---|
| 使用者／室內設計師 | Actor | 上傳平面圖、校正結構、答問卷、編輯 2D/3D 家具、鎖視角、取得渲染圖與交付 PDF | `README.md:3-5`、事實檔 01-product §1-2 |
| RoomPilot | 本系統 | 八步可恢復網頁流程：辨識→校正→需求→配置→編輯→視角→渲染→交付；狀態存 workflow JSON（SQLite ProjectStore） | `backend/server/main.py:195`、`project_store.py:77-84` |
| OpenRouter | 外部系統 | 唯一 LLM/VLM/生圖閘道：問卷解析、場景規劃、nano banana 逐房生圖/改圖 | `intake_service.py:52`、`backend/agent/llm.py:133`、`main.py:2064` |
| PostgreSQL 家具庫 | 外部系統 | view `roompilot.furniture_catalog_current`（8,675 件官方家具）的唯一正式讀取面 | `main.py:909-926`、`main.py:3229`、ADR-003 |
| AWS S3/CloudFront | 外部系統 | 家具 GLB 模型與三視角圖資產；API 以 307 redirect 導向 | `main.py:4012`、事實檔 05-data §5 |

### 2.2 連線（每條標互動語意，協定留 L2）

| 從 → 到 | 互動語意（領域動詞） | 證據 |
|---|---|---|
| 使用者 → RoomPilot | 建案、上傳平面圖、確認結構、填需求、編輯家具、鎖視角、要求生圖與交付 | `main.py:1784,1870,4149,3336,3591,2070` |
| RoomPilot → OpenRouter | 解析問卷、規劃場景敘述、生成/修改渲染圖（**一條線註明「統一閘道」**，不畫多條直連） | `OPENROUTER_API_KEY` 單一金鑰，事實檔 06-ops §OpenRouter |
| RoomPilot → PostgreSQL | 查詢第 6 步候選家具（DB 失敗必須可見、不悄悄回退 JSON） | `main.py:909-926`、NFR-003 |
| RoomPilot → CloudFront | 取家具 GLB／三視角圖（307 redirect，瀏覽器直載資產） | `main.py:4012` |

### 2.3 邊界鐵律（畫進註記帶）

- 辨識止於 `layout_json`，方案與編輯用 `scene_json`（ADR-001）。
- 家具幾何合法性只由 `backend/engine/` 計算，不在 LLM／瀏覽器（ADR-002、NFR-004）——OpenRouter 連線不得標「決定擺位」。
- 家電只進 `render_context` 供生圖，不進 2D/3D（ADR-004）。
- `frontend3d/` 為次要原型，不入圖（ADR-006）。

## 3. 約束與檢查

- [ ] 方塊只有三種：人（actor ×1）、本系統（圓角矩形 ×1）、外部系統（直角矩形、灰 ×3）
- [ ] 無內部模組、無開發工具（GitHub／IDE／CI／Playwright Chromium 為本機依賴不入圖）
- [ ] 每條連線標互動語意（§2.2 領域動詞），協定留給 [c4_container](./c4_container.md)
- [ ] LLM/生圖經 OpenRouter 統一閘道，在線上註明，不畫成多條直連
- [ ] 圖例列出實際用到的配色；metadata banner 已附（版本 0.1、git yen@8863a36c）

## 4. 待確認

1. 營運人員／管理員 actor：程式碼未見登入、權限或後台端點證據，暫定「無」，待 owner 確認。
2. 屋主與設計師是否拆成兩個 actor：`README.md:157-191` 有設計師鎖定流程，但無獨立身分機制，暫合併為一。
3. 正典來源 `../sad.md` §1.1 尚未產出（登錄簿 §6 已列計畫）；產出後本檔外部系統清單須與其對齊。
4. PostgreSQL 部署位置（本機或雲端託管）無 repo 證據，圖上僅標「外部資料庫」不標供應商。

## 5. 追溯

- 上游：[../../00-registry.md](../../00-registry.md)（ADR-001/002/003/004/006、NFR-003/004）、[../sad.md](../sad.md) §1.1（外部系統正典，待產出）、[../../01_requirements/srs.md](../../01_requirements/srs.md)（actor 定義）；事實檔 01-product／02-api／05-data／06-ops（git yen@8863a36c）。
- 下游：[c4_container](./c4_container.md)、簡報／onboarding 材料。
- 產圖：以本 §2 規格走 `VibeCoding_Workflow_Templates/03_architecture/diagrams/_tools/drawio_kit.py` 生成 `.drawio`，再以 `_tools/analyze_layout.py` 驗 cross=0, pierce=0（參考 `_examples/prompt_filled.md` 鏈路）。
