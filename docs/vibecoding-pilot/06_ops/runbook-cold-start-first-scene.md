# Runbook - 第 6 步首次載入 3D 約 33 秒（已知特性，非缺陷）

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 活躍
> **Owner:** Bella（Three.js viewer／PBR 材質為產品決定）
> **語域:** L3（工程）
> **定位:** 冷啟慢的歸因、判別方式與「不要再試的死路」；家具載不出來（替代方塊）另見 [runbook-furniture-glb-missing.md](runbook-furniture-glb-missing.md)。
> **實例:** 每故障症狀一份（`runbook-<symptom>.md`）
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/06_ops/runbook.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. Symptoms（症狀）](#1-symptoms症狀)
- [2. Impact（影響）](#2-impact影響)
- [3. Possible Causes（可能原因）](#3-possible-causes可能原因)
- [4. Diagnosis（診斷步驟）](#4-diagnosis診斷步驟)
- [5. Mitigation（短期緩解）](#5-mitigation短期緩解)
- [6. Recovery（恢復確認）](#6-recovery恢復確認)
- [7. Escalation（升級路徑）](#7-escalation升級路徑)
- [8. 追溯](#8-追溯)

## 1. Symptoms（症狀）

- 第 6 步**首次**進入 3D 場景，畫面停在載入狀態約 33 秒（2026-08-01 團隊 QA 實測：headed Edge、Intel UHD 620／ANGLE D3D11、14 件家具場景；紀錄未入版控，數字隨 GPU 環境而異）。
- 暖機後同 session 的後續操作約 0.2 秒——**只有第一次慢**。若每次都慢，就不是本症狀，另查。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 僅首次載入的等待體驗；幾何、材質、配置正確性完全不受影響 |
| **嚴重程度判定** | 已知特性，非缺陷，不開缺陷單；唯一要管理的是 demo 現場的第一印象（見第 5 節） |

## 3. Possible Causes（可能原因）

實測歸因（CDP profiler，2026-08-01 QA 紀錄，未入版控）：

1. **首次 shader program 連結佔約 70%**（`getProgramInfoLog` 23.3s／70.5%）。45 支 program、每支約 0.5 秒——是單支 shader 太複雜，不是數量太多。源頭在程式碼可查證：`physicalMaterialFrom()` 把家具材質轉成 `MeshPhysicalMaterial`（`frontend/scene_viewer.js:3560`），`furniturePbrProfile`（`frontend/scene_pbr_contracts.js`）對 wood／metal 開 clearcoat、fabric 開 sheen、glass 開 transmission。
2. 貼圖上傳（`texSubImage2D`）約 10.5%。
3. 房間幾何 `createRoom()` 僅約 1.4 秒，不是主因。

**不要混淆**：後端 bge-m3 embedding 模型在 CPU 上首次載入也約 34 秒，但那是**伺服器啟動時的背景預載**，未就緒時檢索退成純結構化過濾，不會卡住 3D 載入（`backend/server/main.py:292-294`）。兩個「30 幾秒」是不同層的事。

## 4. Diagnosis（診斷步驟）

1. **先確認是不是冷啟**：重整頁面後首次進 3D 慢、同 session 第二次快 → 是本症狀，到此為止，不用修。
2. 每次都慢才需要 profile：DevTools Performance 錄一次載入，若大頭不在 shader 連結（`getProgramInfoLog`）而在網路或 API，走 [runbook-furniture-glb-missing.md](runbook-furniture-glb-missing.md) 或後端診斷。
3. 參考錨點：`createSceneViewer` 開頭刻意把 `createImageBitmap` 設為 `undefined`（`frontend/scene_viewer.js:298-300`），這是既有設計，不是意外遺留。

## 5. Mitigation（短期緩解）

1. **Demo 前先暖機**：開場前先進一次第 6 步 3D 場景讓 shader 編譯完，正式展示時就是 0.2 秒級的體驗。
2. **不要再試的三條死路**（2026-08-01 已實測排除，QA 紀錄未入版控）：
   - 重壓 GLB 資產：132.7MB 壓到 13.0MB 只讓冷啟 32.3s → 24.8s，資產不是瓶頸。
   - 還原 `createImageBitmap`：34.1s vs 31.5s，無改善。
   - `renderer.compileAsync()`＋載入期間暫停繪製：此環境 `KHR_parallel_shader_compile` 為 true 但 ANGLE/D3D11 實際沒平行化，31.5s vs 33.1s，無改善。
3. **降 shader 複雜度會改變外觀**，且有 `tests/test_scene_pbr_realism.py` 鎖著——屬 Bella 的產品決定，不是 runbook 層級可以動的旋鈕。

## 6. Recovery（恢復確認）

- 本症狀無「恢復」動作：暖機後同 session 操作回到亞秒級即為正常。
- 若做了暖機仍每次 30 秒級，代表不是本症狀，回第 4 節第 2 步重新歸因。

## 7. Escalation（升級路徑）

| 情況 | 找誰 | 管道 |
| :--- | :--- | :--- |
| 想改 PBR 材質複雜度換冷啟速度 | Bella（產品決定） | 團隊群組（現況無書面 on-call 制度，未查證到正式約定） |
| 冷啟時間顯著劣化（例如 33 秒變 90 秒） | Bella | 同上，附 profiler 紀錄 |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

## 8. 追溯

| 項目 | ID |
| :--- | :--- |
| 對應告警 | 現況：無告警系統（[deployment_and_operations.md](deployment_and_operations.md) 監控段） |
| 對應 NFR | NFR-效能-02（`../01_requirements/srs.md` §2：3D 首次載入；門檻仍 TO-BE） |
| 鎖定測試 | `tests/test_scene_pbr_realism.py`（PBR 外觀契約） |
| 事故紀錄 | 2026-08-01 QA 實測歸因（團隊工作紀錄，未入版控；postmortem 文件依需增建） |
