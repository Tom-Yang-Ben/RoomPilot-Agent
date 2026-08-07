# Runbook - 家具 GLB 缺檔：替代方塊與軟裝角色被略過

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 活躍
> **Owner:** Kai（型錄／CloudFront 資產）、Bella（Three.js viewer）
> **語域:** L3（工程）
> **定位:** 3D 場景出現替代方塊、或自動軟裝（燈／地毯／植栽／布簾）沒出現時的診斷與處置；資料庫整體失聯另見 [runbook-postgres-catalog-unavailable.md](runbook-postgres-catalog-unavailable.md)。
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

- 3D 場景中某件家具顯示為**半透明琥珀色方塊＋深色外框**（`createFallbackFurnitureProxy`，`frontend/scene_viewer.js:4205-4257`；顏色 `0xd97706`）。舊文件寫「白色替代物」已過時。
- 場景狀態列顯示「場景已生成，但部分家具未載入：…」（`frontend/scene_viewer.js:4374-4375`）。
- 自動軟裝少了燈／地毯／植栽／布簾：配置回應的 `decor_summary.skipped` 列出被略過的角色與原因（`backend/server/scene_api.py:601-651`）。

**歷史行為對照（讀舊文件時注意）**：舊版軟裝缺 GLB 會回 409 `decor_model_missing`；現行程式已改為「該角色略過、其餘照常配置」，**不再回 409**（`backend/server/main.py:1491-1494` 註解、`scene_api.py:642-650`）。布簾曾固定指向不存在的 `/static/models/roompilot-curtain.glb` 造成保證 404；現在該檔已入版控（`frontend/models/roompilot-curtain.glb` 存在），且缺檔時改列 `skipped` 而非硬塞壞品項（`scene_api.py:245-264`）。

## 2. Impact（影響）

| 項目 | 內容 |
| :--- | :--- |
| **受影響功能** | 視覺不完整；替代方塊保留正確位置與尺寸（`size_cm`），幾何與碰撞判定不受影響 |
| **不阻擋的事** | 場景照常生成與編輯；軟裝單角色缺檔不會讓整間房軟裝中止 |
| **嚴重程度判定** | 單件家具缺模型＝低（換一件即可）；大面積替代方塊（多數家具都載不出）＝視同 CloudFront／資料層事故，升級處理 |

## 3. Possible Causes（可能原因）

按發生機率排序：

1. **CloudFront GLB 抓不到**：`model_url` 指向 CloudFront 但回 404／逾時（網路、資產缺漏）。前端 catch 後以替代方塊顯示，理由「GLB 載入失敗」（`scene_viewer.js:4328-4336`）。
2. **該件家具本來就沒有 GLB**：`model_url` 為空，理由「資料庫尚未提供 GLB」（`scene_viewer.js:4287-4290`）。
3. **軟裝角色在型錄裡沒有可用 GLB**：候選過濾要求 `has_model` 且有 `model_url`（`backend/server/main.py:1470-1477`）；燈具走獨立表 `roompilot.lighting_assets_current`（637 筆可用／793 筆總數，`backend/catalog/data/README.md:29-30`），未匯入時燈具角色會落空。
4. **離線 JSON 模式**下燈具只剩殘留的舊 `lamp` 型別頂著，選擇面窄（`backend/server/main.py:1433-1435`）。
5. **誤用本機拆解端點**：cloudfront 模式下 `/api/furniture/{id}/model.gltf`、`buffer.bin`、`images/*` 固定回 410，屬設計行為不是故障（`backend/server/main.py:1527-1553`）。

## 4. Diagnosis（診斷步驟）

```powershell
# 1. 型錄資產健康度：manifest_ready 應為 true，verified_model_count 應等於型錄筆數
curl.exe -s http://127.0.0.1:8002/api/catalog/status

# 2. 燈具表是否有貨（軟裝燈角色的來源）
psql -U postgres -d roompilot_db -c "SELECT COUNT(*) FROM roompilot.lighting_assets_current;"
```

瀏覽器側（F12）：

1. Network 面板過濾 `.glb` → 找出 404／失敗的確切 URL；CloudFront base 是 `https://ddgsm1yg3xikc.cloudfront.net`（`backend/server/services/cloud_models.py`）。
2. Console 有對應的載入錯誤（`scene_viewer.js:4329` 會 `console.error`）。
3. 配置回應（`decorate` API）的 `decor_summary.skipped[].reason` 直接寫明每個被略過角色的原因。

## 5. Mitigation（短期緩解）

1. **單件家具載不出** → 第 6 步換選同型別另一件（替代方塊本身就是設計好的降級：位置尺寸不失真、流程不中斷）。
2. **軟裝角色被略過** → 看 `skipped[].reason`：型錄沒貨找 Kai 補資產或匯入燈具表（`docs/NEW_MACHINE_SETUP.md` §6 的 `import_lighting_assets_to_postgres.py`）；不影響展示時可接受略過。
3. **大面積載不出** → 先確認本機對 CloudFront 的連通性（防火牆、離線環境）；離線展示需求走 `ROOMPILOT_MODEL_DELIVERY_MODE=local` 與離線 GLB 備援流程（`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`；README「IKEA 地端 GLB 備援」段標明**尚未完成**，啟用前先與 Kai／Django 確認）。

## 6. Recovery（恢復確認）

- 重新載入場景後狀態列回到「場景已生成：拖曳家具可移動…」（無 failures 清單）。
- viewer 診斷值 `fallbackFurnitureCount` 為 0、`failedFurniture` 為空（`scene_viewer.js:4367-4370`，可在 console 檢視）。
- `decor_summary.skipped` 為空，或剩餘項目為已知並接受的缺貨角色。

## 7. Escalation（升級路徑）

| 情況 | 找誰 | 管道 |
| :--- | :--- | :--- |
| CloudFront 資產缺漏／燈具表資料 | Kai | 團隊群組（現況無書面 on-call 制度，未查證到正式約定） |
| 替代方塊行為、載入診斷、viewer 顯示 | Bella | 同上 |
| 軟裝候選規則（哪些型別可自動配置） | Bella＋Yen（選件邊界） | 同上 |

事故結束後 48 小時內完成覆盤紀錄（正式覆盤文件依需增建）。

## 8. 追溯

| 項目 | ID |
| :--- | :--- |
| 對應告警 | 現況：無告警系統（[deployment_and_operations.md](deployment_and_operations.md) 監控段） |
| 對應 NFR | NFR-可用性-01（`../01_requirements/srs.md` §2：降級韌性） |
| 相關契約 | `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`（GLB 交付與 410 行為） |
| 事故紀錄 | 無（postmortem 文件依需增建） |
