# RoomPilot Definition of Done — 逐層驗收條件

v1.1(2026-07-21 文件清整)。回答一件事:**每一層「什麼叫完成」,以及「憑什麼證據」。**

制度母文件:`docs/04_契約與規格/IMPLEMENTATION_QUALITY_GUARDRAILS.md`(功能四要件:畫面/互動/資料/驗收;交付前 6 步固定檢查)。本檔是它的逐層具體化;通用原則不在此重複,先讀它。

---

## 0. 通用判準(所有層適用)

- **檔案存在 ≠ 完成;程式啟動 ≠ 結果正確;JSON 合法 ≠ 幾何與單位合理;GLB 產生 ≠ 能被 three.js 載入;測試通過 ≠ 符合使用者需求**(最後一條的血淋淋案例見 `FAILURE_LOG.md` #1:引擎 25 測試全過,但房間尺寸鏈未通,實際擺放全錯)。
- 宣稱完成必附證據,規則見 `.claude/rules/verification.md`;無法驗證只能寫「已修改,尚未驗證」。
- **單位與座標系是本專案第一大陷阱**:三套座標系並存(引擎=角落原點、payload=房間中心原點、floorplan 交接 JSON=左下原點 y 向上),`rotation_y_deg` 與引擎 rotation 方向相反,公尺/公分邊界只在特定檔案。正本是根目錄 `CLAUDE.md` 的 Architecture invariants 節——任何跨層修改前先重讀那一節。

## 0.1 文件可信度指引(先讀對的正本)

> 狀態數字以實跑對應驗證指令為準；文件、索引與歷史提交都不能取代程式輸出。2026-07-21 已把個人研究、舊狀態稽核與過時契約移出現行 repo。

| 文件 | 可信度 |
|---|---|
| `docs/01_專題進度/RoomPilot_現行版本總覽.md` | **最高(SSOT)**；仍須以 code、tests 與實跑結果交叉驗證 |
| `docs/資料夾功能總覽.md` | 現行 repo 地圖；只描述檔案用途，不宣稱功能完成 |
| `docs/04_契約與規格/IMPLEMENTATION_QUALITY_GUARDRAILS.md` | 現行品質與互動驗收原則 |
| `docs/01_專題進度/RoomPilot_ben-dev_功能整合來源報告_2026-07-19.md` | 整合來源與歸屬快照，不取代 SSOT |
| `docs/archive/` | 歷史證據；內容可過時、連結可失效，不當現況讀 |

---

## 1. floorplan(PNG → DXF)

| | 內容 |
|---|---|
| 輸入 | `testdata/png/`(PNG;JPG/BMP 成功率 ~50%,非 P0) |
| 輸出 | `testdata/dxf/`(WALL/WINDOW 兩圖層)、`testdata/dxf_scale/`(公分)、`testdata/json/`(前端交接,px+cm 雙座標+scale 信心度) |
| 驗證 | (皆在 **repo 根目錄**跑;腳本預設路徑是根目錄相對,`cd` 進去跑會找不到資料)① 窗:`uv run --extra vision python roompilot/floorplan/eval_windows.py` — **門檻:精準/召回 ≥90%/90%**(現基準 94/92)② 門過濾:`uv run --extra vision python roompilot/floorplan/eval_doors.py` — **門檻:≥95%**(現 19/19=100%;根目錄跑會提示找不到 config.ini 並改用內建預設值,基準數字就是這樣跑出來的,屬正常)③ 批次重跑:`uv run --extra vision python roompilot/floorplan/floorplan2dxf.py testdata/png testdata/dxf` 無例外 |
| 交下一層證據 | 評測輸出數字 + `testdata/chk/` 疊圖(人可目視抽查)+ 交接 JSON 的 scale 信心度欄位 |
| 已知缺口 | 評測**不在 pytest 內**,改完必須手動跑;動到偵測邏輯而沒貼評測數字 = 未驗證 |

## 2. upgrade3d / dxf_parser(DXF → 樓面 JSON)

| | 內容 |
|---|---|
| 輸入 | `testdata/dxf/*.dxf` |
| 輸出 | 樓面 JSON(牆體聯集、房間=孔洞、窗段聚類合併;**單位公尺**——公尺→公分的唯一邊界在 `engine/dxf_room.py`) |
| 驗證 | ① `uv run python roompilot/upgrade3d/eval_window_merge.py` — **門檻:precision/recall ≥90%/90%**(現基準 100/100,自帶 PASS/FAIL 退出碼)② 自檢:`uv run python roompilot/upgrade3d/dxf_parser.py`(逐檔斷言牆體與比例;需 uv 環境的 ezdxf,勿用裸 `python`)③ `uv run pytest tests/test_roompilot_quality_guardrails.py -v`(前端預覽契約) |
| 交下一層證據 | eval PASS + 樓面 JSON 中房間數/牆段數與 chk 疊圖一致 |
| 已知缺口 | 樓面 JSON **無欄位契約文件**(只有 code docstring);3D 窗戶顯示問題未解(SSOT §14) |

## 3. engine(家具擺位)

| | 內容 |
|---|---|
| 輸入 | `dxf_room.py` 轉出的 `Room`(**公分**)+ 家具清單(`style_db.py` 已把型錄 cm→引擎 cm) |
| 輸出 | 擺位座標(角落原點,`pos_y`=平面第二軸) |
| 驗證 | `uv run pytest tests/test_placement.py tests/test_clearance.py -v`(25 測試)——**通過只代表邏輯自洽**;結果正確還需尺寸鏈(F2a)已通,否則標「邏輯完成、結果待尺寸鏈」 |
| 交下一層證據 | pytest 輸出 + 實際樓面(floor21)擺位結果截圖,附三項檢核逐條回答:①無家具出房間邊界 ②無非法重疊 ③朝向合理(床頭靠牆、沙發面向空間)——AI session 自己檢核並列證據,存疑處標給人複核 |
| 已知缺口 | 合法重疊(電視上電視櫃/地毯墊底)、擋門、動線規則未做(SSOT §6.3);淨空語意只給收納類(`style_db.CLEARANCE_BY_TYPE`) |

## 4. scene_service(場景組裝)

| | 內容 |
|---|---|
| 輸入 | 樓面 JSON + 需求 + 型錄 |
| 輸出 | scene payload(`position_cm`/`size_cm`=公分;`wall/window/door segments`、`room_regions`=**公尺**;`rotation_y_deg` 與引擎反向)——契約正本=CLAUDE.md invariants |
| 驗證 | ① `uv run pytest tests/test_agent_layout_intent.py tests/test_agent_recovery.py tests/test_layout_api.py -v`② 端到端依 FastAPI OpenAPI／`project_models.py` 的現行欄位呼叫專案配置 API，人工抽查回應座標與單位 |
| 交下一層證據 | curl 回應存檔 + frontend3d 或 /scene 頁實際渲染截圖 |
| 已知缺口 | `generate_layout` 主流程與 `choose_furniture_items` 評分**無直接單元測試**;OpenRouter 呼叫與降級路徑無 mock 測試——動這兩處必須做端到端驗證,不能只跑 pytest |

## 5. server API

| | 內容 |
|---|---|
| 輸入/輸出 | 路由以 `roompilot/server/main.py`、Pydantic `project_models.py` 與 FastAPI OpenAPI 為準 |
| 驗證 | ① 在 **repo 根目錄**跑 `uv run --extra vision uvicorn roompilot.server.main:app --port 8002`② 跑受影響的 `tests/test_project_api.py`、`test_requirements_api.py`、`test_layout_api.py`③ 對上傳或瀏覽器流程仍以真實檔案端到端實測 |
| 交下一層證據 | curl 輸出(狀態碼+body 摘要) |
| 已知缺口 | TestClient 已覆蓋主要專案流程，但外部 OpenRouter、瀏覽器截圖與真實 GLB 載入仍需端到端驗證 |

## 6. frontend3d(R3F 顯示與手動微調)

| | 內容 |
|---|---|
| 輸入 | scene payload(經 proxy → :8002) |
| 輸出 | 3D 場景渲染 + 拖曳/吸附(`Furniture.jsx`、`snap.js`) |
| 驗證 | `cd frontend3d && npm test` 驗證資料與狀態 helper；`npm run build` 驗證建置；真正 UI 完成仍須在 `:8002/scene` 逐步操作並截圖存證 |
| 交下一層證據 | 操作截圖或錄影 + 瀏覽器 console 無紅字 |
| 已知缺口 | helper 測試不能證明 R3F 畫面、拖曳與門窗實物正確；互動與視覺仍是最高風險區 |

## 7. Git 分支整合

| | 內容 |
|---|---|
| 輸入 | 他人分支(注意:`ancai-dev`/`rule`/`kai-dev` 勿動;bella 搬資料不搬殼) |
| 驗證 | ① 合併前 `git log --oneline main..<branch>` + `git diff --stat` 看範圍 ② 合併後全套 `uv run pytest tests/ -v` + 受影響層的上述驗證 ③ 逐條檢查**入倉三規則**(正本=根目錄 CLAUDE.md Conventions 節,以該處為準) |
| 證據 | pytest 輸出 + `git status` clean |

---

## 8. 尚需持續驗證的介面縫隙

1. **scene payload → frontend3d**:混合單位與 rotation 反向仍由 CLAUDE.md invariants 約束，改動必須搭配 3D 實測。
2. **floorplan 交接 JSON → 校尺 UI**:第三套座標系，須同時驗證同牆吸附與公分換算。
3. **dxf_parser 樓面 JSON → engine**:公尺／公分邊界集中在 `dxf_room.py`，改動須跑升維與配置測試。
4. **外部服務**:OpenRouter 與未定案的照片級渲染供應商，必須保留明確降級與失敗回報。
