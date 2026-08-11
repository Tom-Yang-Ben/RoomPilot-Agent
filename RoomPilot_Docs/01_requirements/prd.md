# 產品需求文件 (PRD) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（`backend/server/`＋`backend/server/static/` 八步工作流整合 owner，AGENTS.md:36）
> **語域:** L1（業務主述；REQ→FR/ACPT 映射屬 L2，ID 見 [../00-registry.md](../00-registry.md)）
> **定位:** 問題、使用者、範圍與允收標準的單一來源；商業流程細節歸 [brd.md](brd.md)，正式規格歸 [srs.md](srs.md)。
> **實例:** 單例
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 專案總覽](#1-專案總覽)
- [2. 商業目標](#2-商業目標)
- [3. 使用者故事與允收標準](#3-使用者故事與允收標準)
- [4. 範圍與限制](#4-範圍與限制)
- [5. 待辦問題與決策](#5-待辦問題與決策)
- [6. 待確認](#6-待確認)
- [7. 追溯](#7-追溯)

## 1. 專案總覽

| 項目 | 內容 |
| :--- | :--- |
| **專案名稱** | RoomPilot（AIPE03 第四組 AI 室內設計系統） |
| **狀態** | 開發中（Pilot 階段，登錄簿 §1） |
| **目標發布日期** | 待確認（見 §6） |
| **核心團隊** | Bella（伺服器/前端整合）、Cody（平面圖辨識）、Django（空間資料）、Kai（家具目錄）、Yen（需求 Agent）、Ancai（幾何引擎）、Ben（辨識 QA）——目錄責任見 `docs/TEAM_AI_OWNERSHIP.md:19-34` |

## 2. 商業目標

| 項目 | 內容 |
| :--- | :--- |
| **背景與痛點** | 從一張平面圖走到可交付的室內設計方案，中間的辨識、尺度換算、需求訪談、家具挑選、擺放合法性、渲染與報價是多套工具的斷裂流程。RoomPilot 把「平面圖辨識 → 人工校正 → 逐房需求 → 家具資料庫 → 幾何配置 → 2D/3D 編輯 → 方案視角 → AI 渲染與交付」整合成一個可恢復的網頁流程（`README.md:3-5`） |
| **策略契合度** | 課程專題（AIPE03）交付；以單一 FastAPI＋Three.js 八步精靈驗證端到端可行性（`README.md:49,63`） |
| **成功指標** | 待確認——repo 內無正式 KPI 定義；可驗證的完成定義暫以登錄簿 ACPT-001～016 為準（見 §6） |

## 3. 使用者故事與允收標準

以八步流程為 Epic 主軸。ID 沿用 [../00-registry.md](../00-registry.md) §2 的 REQ/ACPT/SCN，允收標準完整 Given/When/Then 見該檔 §2.3。

### Epic 1：專案建立與可恢復（步 1，橫切）

| ID | 描述 (As a / I want to / So that) | 允收標準（摘要） | 情境ID |
| :--- | :--- | :--- | :--- |
| REQ-001 | As a 使用者, I want to 建立專案並隨時中斷再回來, so that 八步進度不因關瀏覽器而遺失。 | Given 已保存的專案，When 重開瀏覽器載入專案，Then 還原到離開時的步驟，原圖與渲染圖可重取（ACPT-001）；兩分頁互踩時落後方被擋下不覆寫（ACPT-014） | SCN-001、SCN-009 |

可觀察行為：專案以單一工作流快照保存（≤2MB，樂觀鎖，`project_store.py:11,28-33`），`GET /api/projects/{id}` 恢復（`main.py:1800`）。

### Epic 2：平面圖到公分制結構（步 2–4）

| ID | 描述 | 允收標準（摘要） | 情境ID |
| :--- | :--- | :--- | :--- |
| REQ-002 | As a 使用者, I want to 上傳 PNG/JPG/DXF 平面圖並自動辨識牆/門/窗/房間, so that 不必手畫空間結構。 | Given 上傳的平面圖，When 執行辨識，Then 回應含辨識結果＋layout_json 且不含任何家具/材質欄位（ACPT-002） | SCN-002 |
| REQ-003 | As a 使用者, I want to 在圖上點兩點並輸入實際距離, so that 整張圖換算成真實公分尺度。 | Given 兩點標定完成，When 進入後續步驟，Then 所有下游幾何欄位皆為公分 `_cm`（ACPT-003） | SCN-002 |
| REQ-004 | As a 使用者, I want to 人工校正牆/門/窗/樑/柱後確認, so that 後續設計建立在我認可的結構上。 | Given 第 4 步已確認，When 之後想改結構，Then 必須回到第 4 步且家具重新驗證（ACPT-004，`README.md:154-155`） | SCN-002 |

### Epic 3：逐房需求與風格（步 5）

| ID | 描述 | 允收標準（摘要） | 情境ID |
| :--- | :--- | :--- | :--- |
| REQ-005 | As a 使用者, I want to 逐房回答問卷、勾家電需求、挑三張風格色卡, so that 系統知道每個房間要什麼。 | Given 問卷完成，When 產出需求結構，Then 含硬/軟需求與家電三分流（ACPT-005） | SCN-008 |
| REQ-014 | As a 使用者, I want to 家電需求只影響最後的寫實生圖, so that 2D/3D 擺設不被冰箱/洗衣機占位干擾。 | Given 問卷勾了家電，When 檢視 2D/3D 場景，Then 場景物件不含任何家電，家電僅出現在生圖上下文（ACPT-013，`AGENTS.md:56`） | SCN-008 |

### Epic 4：自動配置與 2D/3D 編輯（步 6）

| ID | 描述 | 允收標準（摘要） | 情境ID |
| :--- | :--- | :--- | :--- |
| REQ-006 | As a 使用者, I want to 一鍵產生方案 A/B 兩種家具配置, so that 有真實可比較的起點。 | Given 同一輸入，When 產生 A 與 B，Then 兩案擺設不同（ACPT-006） | SCN-003 |
| REQ-007 | As a 使用者, I want to 在 2D 與 3D 同步拖曳、旋轉、替換家具, so that 用最直覺的方式微調配置。 | Given 拖曳落點違規（門前 75cm 淨空、窗前採光帶、房外），When 放下家具，Then 被拒且有分流訊息（ACPT-007）；只驗證不重排時每件座標照舊（ACPT-008）；未處理的碰撞/淨空/超界阻擋下一步（`README.md:154-155`） | SCN-004、SCN-005 |
| REQ-008 | As a 使用者, I want to 調材質、天花、燈光並在 3D 內走動預覽, so that 確認方案再往下走。 | Given 材質/燈光調整，When 套用，Then 3D 即時反映且相關測試通過（ACPT-016；行為證據 04-frontend §5） | SCN-005 |
| REQ-013 | As a 使用者, I want to 家具只來自 8,675 件已驗證官方目錄, so that 每件都有真實尺寸、3D 模型與圖片。 | Given 資料庫回傳不足 8,675 筆，When 查家具，Then 不採用該結果且失敗狀態可查（ACPT-012，`main.py:909-926`、`README.md:299-304`） | SCN-006 |

### Epic 5：方案鎖定與視角（步 7）

| ID | 描述 | 允收標準（摘要） | 情境ID |
| :--- | :--- | :--- | :--- |
| REQ-009 | As a 使用者, I want to 鎖定方案並逐房調好生成視角, so that 後續 AI 生圖照我選的角度畫。 | Given 視角已鎖定，When 進第 8 步生圖，Then 以鎖定視角截圖作為生圖參考（ACPT-016；`scene.html:943`） | SCN-007 |
| REQ-010 | As a 使用者, I want to 用代表房比較三張色卡的低解析效果圖, so that 快速定調風格。 | Given 已生成過色卡比較圖，When 再次請求，Then 被拒（每專案一次，ACPT-009，`main.py:2135-2140`） | SCN-007 |

### Epic 6：AI 渲染與交付成果包（步 8）

| ID | 描述 | 允收標準（摘要） | 情境ID |
| :--- | :--- | :--- | :--- |
| REQ-011 | As a 使用者, I want to 逐房生成寫實效果圖並有一次改圖機會, so that 拿到接近成品的視覺。 | Given 該房已用過改圖額度，When 再改，Then 被拒（ACPT-010）；客廳另有夜間圖（04-frontend §7） | SCN-007 |
| REQ-012 | As a 使用者, I want to 一鍵產出交付提案 PDF、設計手冊、工程報告與台灣行情估價, so that 有可交付的完整成果包。 | Given 渲染環境未就緒，When 產出提案，Then 明確回報缺件與安裝指引，不產出殘缺 PDF（ACPT-011，`README.md:111-117`） | SCN-007 |

## 4. 範圍與限制

| 項目 | 內容 |
| :--- | :--- |
| **功能範圍** | 上表 REQ-001～014 的八步網頁工作流：`backend/server/`（FastAPI）＋`backend/server/static/`（Three.js 單頁精靈）為唯一正式產品（`AGENTS.md`、01-product §1） |
| **非功能需求** | 公分制契約（NFR-001）、可恢復保存與樂觀鎖（NFR-002）、家具目錄 DB 優先且失敗可見（NFR-003）、幾何合法性單一權威在 `backend/engine/`（NFR-004）、隔離區資料不進正式面（NFR-005）、測試決定論離線（NFR-006）——完整定義見 [../00-registry.md](../00-registry.md) §2.2 |
| **不做什麼** | 辨識不越過 layout_json 產生設計決策；Graph RAG/LLM/瀏覽器不決定幾何；家電不進 2D/3D 擺設；quarantine 與 inactive（599 件）家具不進正式 API；`frontend3d/` 原型不取代正式前端；不建第二套 FastAPI；第一版 /rag 檢索頁不接管第 6 步候選（01-product §4） |
| **假設與依賴** | 依賴：PostgreSQL view `roompilot.furniture_catalog_current`（家具）、CloudFront GLB 資產、OpenRouter 生圖服務、Playwright Chromium（提案 PDF）（01-product §2 步 8、REQ-013 證據）。假設：單機 uvicorn 部署（port 8002，`README.md:49,63`） |

## 5. 待辦問題與決策

| ID | 描述 | 狀態 | 負責人 |
| :--- | :--- | :--- | :--- |
| D-001 | 既成架構決策共 8 條（辨識邊界、幾何權威、目錄優先序、家電去處、併存管線、正式前端、快照保存、混合引擎），見 [../00-registry.md](../00-registry.md) §3 ADR-001～008 | 已決定 | 各目錄 owner |
| Q-001 | 保存機制契約分歧：README/Phase 3 契約稱 PostgreSQL JSONB，本分支程式實際為 SQLite ProjectStore（01-product §5 待確認） | 待討論 | Bella |
| Q-002 | REQ 優先序、里程碑與範圍尚未經 `requirements_tracker.xlsx` ①需求決策 owner 核准 | 待討論 | 產品 owner |

## 6. 待確認

1. **目標發布日期**：repo 內無日期承諾，未填。
2. **成功指標（KPI）**：無正式 KPI 文件；暫以 ACPT-001～016 作為可驗證完成定義，非業務 KPI。
3. **核心團隊之 PM/UX 職稱**：僅有目錄 owner 對照（`docs/TEAM_AI_OWNERSHIP.md`），無 PM/UX 角色指派紀錄。
4. **本 PRD 全文為 AI 衍生（TO-BE）**：REQ 清單與優先序未經需求決策 owner 核准（同 Q-002）。
5. **保存機制的正式定位**：SQLite 與 PostgreSQL Phase 3 契約的落差（同 Q-001）。

## 7. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游 | 事實檔 01-product、04-frontend（git yen@8863a36c）；[../00-registry.md](../00-registry.md) §2 穩定 ID 骨幹；brd 的 BR-*（[brd.md](brd.md)，尚未核准前為 TO-BE） |
| 本文件產出 | REQ-001～014（本檔以八步 Epic 敘述）；引用 FR/NFR-*、ACPT-001～016、SCN-001～010（定義在登錄簿，不在本檔重複） |
| 下游 | [srs.md](srs.md)、[../03_architecture/sad.md](../03_architecture/sad.md)、[../02_ux_ui/ui_spec-scene.md](../02_ux_ui/ui_spec-scene.md)、[../05_qa/test_plan.md](../05_qa/test_plan.md) 以 REQ/FR/SCN 引用 |
