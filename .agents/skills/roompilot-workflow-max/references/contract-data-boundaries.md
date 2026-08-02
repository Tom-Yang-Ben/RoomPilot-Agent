# 契約與資料邊界

## 幾何與單位

- 跨模組長度與平面座標使用公分。
- 新長度與座標欄位以 `_cm` 結尾；面積以 `_m2` 結尾。
- 相容欄位 `width`、`depth`、`pos_x`、`pos_y` 必須搭配
  `coordinate_unit: "cm"` 與 schema version。
- 明示角度單位；不可混用畫布 pixel、meter 與 centimeter。
- 不確定的辨識證據保留 confidence/source，不得提升為已確認結構。

## `layout_json` 與 `scene_json`

`layout_json` 只描述格局：牆、門、窗、樑、柱、房間、尺度、confidence、issues
與校正需求。不得包含家具決策、最終風格、材質、渲染相機或 proposal copy。

`scene_json` 在 layout 與需求完成後描述方案：家具、GLB、尺寸、座標、表面、
天花、燈光、StylePack、渲染設定、planner/rule report 與 render context。

新增或改動任一欄位時，記錄 producer、consumer、schema version、default、舊資料
相容、保存/reload、錯誤行為與兩側測試。

## RAG、Agent 與 Engine

- Graph/Vector RAG 只檢索、排序並提供房間、家具、風格、材質與限制證據。
- Yen Agent 解析需求、挑選白名單候選並提出修復意圖；不輸出合法座標。
- Django evaluation 可提供可放置/不可放置理由；不直接改寫家具座標。
- `backend/engine/` 是碰撞、淨空、動線、門窗衝突、邊界與座標合法性的唯一
  裁決者。每次替換家具後重新呼叫 Engine。
- `placement_failed` 或 `escalate` 不得在 frontend 被偽裝成成功。

## Catalog、PostgreSQL 與資產

- Kai 擁有家具 ID、taxonomy、尺寸主檔、CloudFront URL、active/quarantine 與
  embedding 的正式邊界。
- 正式 API/RAG/scene 只接受 active 且通過正式資產與資料驗證的家具。
- inactive、unmatched、staging、external quarantine 不得先載入再由 frontend 隱藏。
- 正式 PostgreSQL 不可用時按契約回 503；JSON fallback 必須由明確 provider 設定。
- Catalog 管理刪除採 `is_active=false` 軟刪除，不套用泛用 hard DELETE 範本。
- `raw_data`、管理權限、audit 與 Bearer token 依現行契約處理。

## 家電、StylePack 與固定設備

- 冰箱、洗衣機等家電只保留在問卷與 `scene_json.render_context`，供第 8 步生圖；
  不進第 6 步正式家具 API、RAG 或自動配置。
- StylePack 可改牆地表面、未鎖定家具材質、燈光與渲染；不得改格局或合法座標。
- `model_locked`、`material_locked`、`styleLocked`、`user_specified` 等使用者鎖定
  必須優先於自動風格替換。
- 固定設備、牆門窗樑柱不屬於家具風格替換範圍。

## Frontend 與保存

- `backend/server/static/` 是 production frontend；不可讓 `frontend3d/` 形成第二套
  正式 workflow。
- Frontend 只呈現或提交結構化意圖，不自行計算合法座標、重做選件/評估演算法，
  或把 backend failure 改成 success。
- 每個狀態變更都要追查 project persistence、revision、cache key、reload、backward
  compatibility 與繁體中文錯誤提示。

## 安全與交付

- 不提交 `.env`、憑證、token、runtime、cache、模型權重或大型 3D/圖片包。
- 不複製 Claude OAuth、statusline、hooks、全域權限或未驗證二進位。
- 不把模板中的微服務、Kubernetes、OAuth、React/Storybook 或自動更新依賴寫成
  已存在的 RoomPilot 能力。
