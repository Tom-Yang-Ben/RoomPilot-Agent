# 3D / GLB 管線狀態

最後更新：2026-07-06

## 目前目標

把既有 IKEA GLB 家具模型整理成可在網站中穩定載入、可被資料庫引用、可供 Three.js 顯示，並支援 `/library` 與 `/scene` 兩條流程。

## 目前狀態

1. 已補齊先前缺漏的 GLB。
2. 家具資料中的 `missing_model_count = 0`。
3. 網站目前以既有 GLB 模型展示為主。
4. `/library` 可單件檢視。
5. `/scene` 可多件同時載入。

## 模型相容性問題與處理

部分 IKEA 模型曾帶有下列格式特性，造成 Three.js 載入困難：

1. `KHR_draco_mesh_compression`
2. `EXT_texture_webp`
3. `KHR_texture_transform`

已做處理：

1. 使用 `scripts/decode_draco_models.mjs` 處理模型相容性。
2. 建立 `dataset/decoded_glb_cache/` 作為修復後模型快取。
3. 調整資料庫 JSON 的路徑欄位。
4. 調整前端與 API，讓資源改走相對路徑。
5. 前端已接上 Draco decoder，資源位於 `web_fastapi/static/vendor/draco/`。

## 缺失 GLB 補檔紀錄

1. 已使用 `missing_glb_furniture_2026-07-03_20260703-213652.zip` 補回原本缺失的 32 個 GLB。
2. 主要原因不是模型壞掉，而是檔名 `Children_s` 與舊路徑 `Children's` 不一致。
3. 已用 `scripts/repair_missing_glb_paths.py` 重新修正對應。
4. 目前重新檢查後 `missing_model_count = 0`。

## `/library` 目前 3D 顯示狀態

1. 點選家具時，右側 viewer 會同步載入該 GLB。
2. viewer 背景會依家具深淺切換，避免白色家具消失。
3. 家具卡縮圖已優先改成 GLB 即時預覽。

## `/scene` 目前 3D 管線狀態

1. `/scene` 會從家具資料庫挑選多件可用 GLB 家具。
2. 場景中每件家具會有：
   - `position_cm`
   - `rotation_y_deg`
   - `size_cm`
3. 前端不再覆寫後端正式計算出的場景座標。
4. `/api/scene/mutate` 已支援：
   - `replace`
   - `remove`
   - `add`
   - `reshuffle`

## furniture_engine 接入狀態

1. `furniture_engine/` 已正式接入 `/scene` 主流程。
2. 後端現在會做：
   - 房間邊界檢查
   - 家具 footprint 建立
   - 碰撞檢查
   - 重新配置
3. 這代表場景不再只靠前端簡化重排。

## DXF 轉 3D 狀態

1. `web_fastapi/dxf_floorplan.py` 已可解析：
   - `wall_segments`
   - `door_segments`
   - `window_segments`
   - `plan_segments`
2. 已驗證 `01-Home Plan Cad Block.dxf` 可解析為可視牆線資料。
3. 前端在 DXF 模式下會優先用 DXF 線段建立 3D 牆體。
4. 牆面會在擋住視角時自動淡出，不是永久消失。
5. 目前限制：
   - 尚未做到不規則房間 polygon 級避障
   - 尚未做到所有 CAD 圖層格式完全通吃

## OpenRouter 與 fallback

1. 專案根目錄支援 `.env` 與 `web_fastapi/.env`。
2. 可用 `.env.example` 建立設定。
3. 若有 `OPENROUTER_API_KEY` 與模型，優先走 OpenRouter。
4. 若無設定或失敗，會自動退回本地 fallback 規則。
5. 因此場景生成功能不會因沒有 API key 而整個中斷。

## 主要檔案

1. `web_fastapi/main.py`
2. `web_fastapi/scene_pipeline.py`
3. `web_fastapi/dxf_floorplan.py`
4. `web_fastapi/static/viewer.js`
5. `web_fastapi/static/scene_viewer.js`
6. `scripts/decode_draco_models.mjs`
7. `scripts/repair_missing_glb_paths.py`
