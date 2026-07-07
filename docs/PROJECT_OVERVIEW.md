# 專題總覽

最後更新：2026-07-06

## 專題一句話

把使用者提供的平面圖、需求文字、風格條件與牆地偏好，對應到既有 IKEA GLB 家具資料庫，自動產生可瀏覽的 3D 室內場景。

## 目前主線

1. 平面圖輸入與空間資訊整理
2. 12 種風格規則系統
3. 家具資料庫與風格分類
4. LLM / fallback 規則整理使用者需求
5. FastAPI + Three.js 網頁展示
6. `/scene` 的單房間家具配置與 3D 場景生成

## 明確不是目前主線的事

1. 不是直接生成全新 3D 家具 mesh
2. 不是先訓練一個大型生成模型再開始做網站
3. TripoSR 不是既定解法，只是試過但品質不夠的方案

## 現在的網站骨架

1. `/` 首頁：RoomPilot 風格入口與流程說明
2. `/styles`：12 種風格、主圖、標註、牆地推薦
3. `/library`：家具資料卡、篩選、3D viewer
4. `/scene`：固定風格生成家具、DXF / 房間尺寸輸入、3D 場景展示

## 核心資料與程式

1. `sf3d/metadata/ikea_furniture_style_database.json`
2. `web_fastapi/main.py`
3. `web_fastapi/scene_pipeline.py`
4. `web_fastapi/static/`
5. `furniture_engine/`

## 目前最重要的交付

1. 12 種風格規則與風格展示
2. 可查詢的家具資料庫 JSON
3. 可載入的 GLB 模型資產
4. 問卷 / DXF / 房間資訊到 3D 場景的網站流程

## 建議閱讀順序

1. `PROJECT_CONTEXT.md`
2. `docs/WEB_UI_STATUS.md`
3. `docs/STYLE_DATA_STATUS.md`
4. `docs/SCENE_SYSTEM_STATUS.md`
5. `docs/MODEL_PIPELINE_STATUS.md`
