# 使用者驗收測試計畫 (UAT Plan) - RoomPilot Pilot 首輪內部驗收

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** PM 主導（人選待指派，TO-BE）；Bella 支援端到端整合門檻（`tests/` 整合 owner，AGENTS.md:45）；各案例協力 owner 見 §3（AI 衍生，人工核准前為 TO-BE）
> **原則:** UAT 驗的是「符不符合真實設計流程」，不是重跑 QA 測試；Demo 不等於驗收。
> **語域:** L1（業務為主；案例表並列穩定 ID 與必要工程詞供追溯）
> **實例:** 每輪驗收一份——本份為 Pilot 階段、內部驗收、2026-08-11 首輪（`UAT_RoomPilot_Pilot_內部_2026-08-11`）
> **定位宣告:** 本文件回答「本輪內部 UAT 驗哪些情境、怎麼操作、過不過的判準是什麼」；不包含自動化測試策略（見 [test_plan.md](./test_plan.md)）、頁面元件細節（見 [../02_ux_ui/ui_spec-scene.md](../02_ux_ui/ui_spec-scene.md)）與 API 契約（見 [../04_design/api_spec.md](../04_design/api_spec.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 驗收範圍與參與者](#1-驗收範圍與參與者)
- [2. 環境與資料準備](#2-環境與資料準備)
- [3. 驗收情境](#3-驗收情境)
- [4. 通過門檻](#4-通過門檻)
- [5. 問題分級與處理](#5-問題分級與處理)
- [6. 簽核 (Sign-off)](#6-簽核-sign-off)
- [7. 追溯](#7-追溯)

## 1. 驗收範圍與參與者

| 項目 | 內容 |
| :--- | :--- |
| **驗收範圍** | 正式產品八步工作流（`/scene` 單頁精靈）端到端：建專案 → 上傳平面圖 → 標定 → 結構確認 → 問卷 → 配置編輯 → 方案鎖定與色卡 → AI 生圖與成果包。覆蓋 REQ-001～REQ-014，情境展開見 §3（SCN-001～SCN-010） |
| **不在範圍** | ① `pytest -q` 迴歸與 `git diff --check`（ACPT-016，由 [test_plan.md](./test_plan.md) 承擔，UAT 不重跑）；② RAG demo 頁 `/rag` 與模型快取；③ `frontend3d/` 次要原型與舊 DXF 3D 公尺制路徑（`/api/plan`、`/api/upload`，api_spec §1 例外）；④ 八章設計手冊（design-manual）——非正式版、UI 不觸發（api_spec §5.6）；⑤ 效能、資安、無障礙（Pilot 內部工具，api_spec §4） |
| **參與者** | 內部輪次：驗收執行者與簽核權人選待指派（TO-BE）；建議按 AGENTS.md:34-46 目錄 owner 分工——Bella（八步 UI／整合）、Cody（辨識）、Ancai（引擎裁決）、Kai（catalog／DB）、Yen（agent 管線） |
| **時程** | 起訖日期與每日安排待指派（TO-BE）；本文件日期 2026-08-11 為計畫建立日 |

## 2. 環境與資料準備

| 項目 | 內容 | 證據 |
| :--- | :--- | :--- |
| 啟動方式 | repo 根目錄：`Copy-Item .env.example .env`（首次）後 `.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload`，開 `http://127.0.0.1:8002` 進 `/scene` | README.md:47-50、62-66 |
| 樣例平面圖 | `data/testdata/png/builder_plan_630.png`；也可由 `GET /api/floorplan/sample/630` 取得同一張 PNG | main.py:146、3072-3079 |
| 家具資料庫 | PostgreSQL view `roompilot.furniture_catalog_current` 須可連線且回滿 8,675 筆才算 postgres 模式生效；狀態以 `GET /api/catalog/status` 查證 | main.py:909-921（NFR-003） |
| AI 生圖金鑰 | SCN-007 生圖段需伺服器端 OpenRouter 金鑰；未設定時生圖回 503，該段改驗錯誤行為 | api_spec §3 |
| 交付 PDF 引擎 | Playwright Chromium：`uv pip install -r requirements-delivery.txt` ＋ `playwright.exe install chromium`；未裝時提案回 503 附安裝指引（本身即 ACPT-011 的驗法） | README.md:111-117、main.py:2378-2384 |
| 額度是一次性的 | 色卡比較圖**每專案只能成功一次**（main.py:2135-2140）、改圖**每房一次**（main.py:2224-2226）——重測 SCN-007 必須開新專案，不可沿用已耗額度的專案 | ACPT-009、ACPT-010 |
| 執行紀錄 | 每案例截圖／回應存證，落點見 §6 證據欄 | — |

## 3. 驗收情境

以真實設計流程為單位展開登錄簿 SCN-001～SCN-010；ID 沿用 SCN-*，不另編 UAT-*。各步 UI 名稱依 [ui_spec-scene.md](../02_ux_ui/ui_spec-scene.md) §3；旅程對照見 [ux_research_and_journey.md](../02_ux_ui/ux_research_and_journey.md) §4-§5。

### 3.1 SCN-001 中斷後恢復（協力：Bella）

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 專案已走完步 1–5 並在步 6 完成至少一次家具編輯與保存 |
| 操作步驟 | ① 在步 6 保存後直接關閉瀏覽器；② 隔天（或清 session 後）重開 `/scene` 載入同一專案 |
| 預期結果 | 畫面還原到第 6 步（`current_step`）繼續編輯；原始平面圖與已存渲染圖可重新取得 |
| 對應 ACPT | ACPT-001 |

### 3.2 SCN-002 上傳到結構確認全鏈（協力：Cody）

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 新專案；樣例平面圖已備（§2） |
| 操作步驟 | ① 步 1 命名建案；② 步 2 上傳 `builder_plan_630.png` 並確認上傳；③ 等待辨識完成；④ 步 3 在圖上點兩點、輸入實際長度（公分）套用標定；⑤ 步 4 校正牆／門／窗／房間後按「確認結構」；⑥ 嘗試回頭改一處結構，觀察系統要求 |
| 預期結果 | 辨識回應含分析結果與 layout_json，且 layout_json 不含家具／材質；標定後下游尺寸全為公分；確認後結構鎖定，改結構被強制回第 4 步並重新驗證家具 |
| 對應 ACPT | ACPT-002、ACPT-003、ACPT-004 |

### 3.3 SCN-003 逐房 A/B 切換與合成（協力：Ancai）

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 步 6 已自動產生方案 A |
| 操作步驟 | ① 在 AB 方案比較區產生方案 B；② 目視比對 A/B 擺設；③ 開啟逐房方案選擇，各房分別選 A 或 B；④ 合成回單一方案後檢查各房家具位置 |
| 預期結果 | 同一輸入下方案 B 與 A 的擺設不同；合成後各房沿用所選方案的座標、不漂移 |
| 對應 ACPT | ACPT-006 |

### 3.4 SCN-004 門前淨空拒放（協力：Ancai）

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 步 6 場景中有衣櫃（或同級大型櫃體）與至少一扇門 |
| 操作步驟 | ① 2D 或 3D 中把衣櫃拖進門前 75cm 淨空區放開；② 讀取系統訊息；③ 追加：拖到窗前採光帶（高 ≥90cm 家具）與房間外各一次 |
| 預期結果 | 三種落點皆被拒絕，且各有對應分流訊息（如「讓開動線」）；家具不落在違規位置 |
| 對應 ACPT | ACPT-007 |

### 3.5 SCN-005 確認白模不重排（協力：Ancai）

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 步 6 已手動微調過數件家具位置 |
| 操作步驟 | ① 記下（截圖）微調後各件家具位置；② 按「確認白模」；③ 比對確認前後位置 |
| 預期結果 | 每件家具座標照舊、絕不整屋重排；系統只回報合法與否 |
| 對應 ACPT | ACPT-008 |

### 3.6 SCN-006 家具資料庫斷線的可見失敗（協力：Kai）

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 可控地使 PostgreSQL 不可用（停 DB 服務或斷連線；具體手段待與 Kai 確認，§7） |
| 操作步驟 | ① DB 斷線狀態下進步 6 開家具庫；② 查 `GET /api/catalog/status`；③ 依 [runbook-catalog-db-unavailable](../06_ops/runbook-catalog-db-unavailable.md) 走回復路徑 |
| 預期結果 | 失敗清楚可見（status 回報 provider 失敗），系統不悄悄改用其他資料來源；只有明確設定才走已驗證 JSON 回退 |
| 對應 ACPT | ACPT-012 |

### 3.7 SCN-007 鎖視角 → 生圖 → 改圖 → 成果包（協力：Bella）

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 步 6 完成且無違規；OpenRouter 金鑰與 Playwright Chromium 依 §2 就緒（未就緒時走替代驗法，見預期結果） |
| 操作步驟 | ① 步 7 逐房調整視角並「鎖定視角」；② 生成色卡比較圖（注意：色卡 UI 在第 8 步面板的比較模式，ui_spec §3.8 註）；③ 對同一專案再請求一次色卡；④ 步 8 逐房生圖或一鍵全生（含客廳夜間圖）；⑤ 任選一房改圖一次，再嘗試第二次；⑥ 產出交付提案 PDF 與工程估價 |
| 預期結果 | 色卡第二次請求回 409（每專案一次）；改圖第二次回 409（每房一次額度）；Chromium 就緒時取得提案 PDF 與估價，未就緒時回 503 附安裝指引、不產出殘缺 PDF |
| 對應 ACPT | ACPT-009、ACPT-010、ACPT-011 |

### 3.8 SCN-008 家電不進擺設（協力：Yen）

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 新專案走到步 5 |
| 操作步驟 | ① 步 5 問卷填入家電需求（冰箱、洗衣機）並完成問卷；② 步 6 產生方案後在 2D/3D 逐房找家電；③ QA 支援：檢查 scene_json 的 `scene_objects` 與 `render_context.appliance_requirements`（scene_service.py:3058-3062） |
| 預期結果 | 問卷產出 client_brief（schema 1.1）含硬／軟需求與家電三分流；2D/3D 擺設完全不出現家電；家電只存在於生圖上下文 |
| 對應 ACPT | ACPT-005、ACPT-013 |

### 3.9 SCN-009 兩分頁同時編輯（協力：Bella）

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 同一專案在兩個瀏覽器分頁同時開啟 |
| 操作步驟 | ① 分頁甲做一次編輯並保存；② 分頁乙（未重載）做另一次編輯並保存；③ 觀察分頁乙的提示與重載後狀態 |
| 預期結果 | 落後的分頁乙收到 409 版本衝突（`project_revision_conflict`，project_store.py:28-33）並被要求重載；分頁甲的變更不被覆寫 |
| 對應 ACPT | ACPT-014 |

### 3.10 SCN-010 併存管線與對帳（協力：Yen；API 級案例）

本案無 UI 入口，由 QA 支援以 API 工具執行（端點見 api_spec §5.5）。

| 欄位 | 內容 |
| :--- | :--- |
| 前置條件 | 專案已有確認後的 layout_json；伺服器可重啟切換環境變數 |
| 操作步驟 | ① 未設 `ROOMPILOT_AGENT_PIPELINE` 時呼叫管線 start，並查 `GET /api/agent/pipeline/status`；② 設 `ROOMPILOT_AGENT_PIPELINE=1` 重啟後 start → submit（問卷→A/B 擺放）→ undo → 再 submit；③ 以同批 step6 選定家具呼叫 reconcile 對帳 |
| 預期結果 | 未啟用時 start 回錯誤（404 附啟用指引，main.py:3510-3515）而 status 永遠可查；啟用後管線與正式步 6 並行不互相取代；reconcile 回報擺放覆蓋率與合法性 |
| 對應 ACPT | ACPT-015 |

## 4. 通過門檻

| 分類 | ACPT | 判準 |
| :--- | :--- | :--- |
| **必須全過**（任一失敗＝本輪不通過） | ACPT-001～ACPT-010、ACPT-013、ACPT-014 | 核心八步流程與三條鐵律（公分制、引擎裁決、家電分流）的可觀察行為；§3.1–3.5、3.7（色卡/改圖段）、3.8、3.9 |
| **條件式容忍**（環境未備時以錯誤行為驗證即算過） | ACPT-011（缺 Chromium 驗 503＋指引）、ACPT-012（DB 斷線手段待定，可延至次輪）、ACPT-015（flag 實驗性管線） | 記入 §6 未解決項目，附雙方同意的處理方式 |
| **不在本輪**（不計入 UAT 判定） | ACPT-016 | pytest 迴歸與 diff 檢查歸 [test_plan.md](./test_plan.md)；UAT 不重跑 QA 測試 |

## 5. 問題分級與處理

| 等級 | 定義 | 處理 |
| :--- | :--- | :--- |
| A－阻擋 | 八步流程走不下去，或「必須全過」ACPT 失敗 | 修復後重驗，本輪 UAT 不通過 |
| B－重要 | 有替代做法但影響效率（如需手動重載、需重開專案） | 修復或列入下版，需簽核人同意 |
| C－建議 | 體驗改善（文案、動線、提示） | 進需求候選（`/intake`），不影響本輪判定 |

## 6. 簽核 (Sign-off)

| 項目 | 內容 |
| :--- | :--- |
| **結果** | 通過 / 條件式通過（附條件）/ 不通過 —— TO-BE（留白待本輪執行） |
| **未解決項目** | TO-BE（清單與雙方同意的處理方式） |
| **簽核人／日期** | TO-BE（owner 依 §1 參與者指派後填入；簽核權人選未定） |
| **證據** | TO-BE（建議 `UAT_RoomPilot_Pilot_內部_20260811.xlsx`：每 SCN 一列，附截圖／API 回應存證位置） |

> 簽核結果回寫 `requirements_tracker.xlsx` ③Gate；證據依穩定 ID 進 `qa_tracker.xlsx` ②執行證據（不得被生成覆寫）。

## 7. 追溯

| 項目 | ID／來源 |
| :--- | :--- |
| 上游 | [../00-registry.md](../00-registry.md) §2：SCN-001～SCN-010（本文件 §3 逐案展開）、ACPT-001～ACPT-015（§3 各案對應欄與 §4 門檻）、REQ-001～REQ-014；操作步驟依 [../02_ux_ui/ui_spec-scene.md](../02_ux_ui/ui_spec-scene.md) §3-§4 與 [../02_ux_ui/ux_research_and_journey.md](../02_ux_ui/ux_research_and_journey.md) §4-§5 |
| 相鄰 | [test_plan.md](./test_plan.md)（ACPT-016 與自動化證據）、[../04_design/api_spec.md](../04_design/api_spec.md)（端點與錯誤碼）、[../06_ops/runbook-catalog-db-unavailable.md](../06_ops/runbook-catalog-db-unavailable.md)、[../06_ops/runbook-delivery-proposal-503.md](../06_ops/runbook-delivery-proposal-503.md) |
| 簽核回寫 | `requirements_tracker.xlsx` ③Gate |
| 證據 | `qa_tracker.xlsx` ②執行證據（以 SCN-* 為鍵） |
| 待確認 | 見 §1 參與者／時程、§3.6 DB 斷線手段、§6 全欄；REQ 優先序尚未經 ①需求決策 owner 核准（同登錄簿 §7） |
