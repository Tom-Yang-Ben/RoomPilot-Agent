# 系統架構

```text
瀏覽器（HTML/CSS/JavaScript/Three.js）
  ↕ FastAPI
專案 SQLite ── workflow snapshot
  ├─ floorplan：PNG/JPG/DXF → layout_json
  ├─ agent：需求結構化、候選家具與說明
  ├─ catalog：portable fixture 或 full PostgreSQL
  ├─ engine：配置、碰撞、淨空與合法性唯一裁決
  └─ scene：layout_json + requirements + catalog → scene_json
```

## 主要邊界

- `backend/server/`：HTTP、專案保存、八步流程與唯一正式靜態前端。
- `backend/floorplan/`、`backend/upgrade3d/`：辨識與已確認格局的 3D 幾何。
- `backend/agent/`：需求、選件意圖、說明與可選外部模型協調。
- `backend/catalog/`：家具／材質資料 adapter；portable fixture 不冒充正式商品。
- `backend/engine/`：家具位置與合法性的唯一權威。
- `backend/spatial_data/`：空間關係、evaluation 與可選家具 RAG。

跨模組長度與座標用公分。舊相容欄位必須帶 `coordinate_unit: "cm"` 與 schema version。辨識證據保留在 `layout_json`；家具、材質、照明、視角與方案資料寫入 `scene_json`。

## Runtime profiles

`portable` 是預設、離線且可重現：SQLite、程序化家具、程序化色卡／材質。`full` 只切換 catalog infrastructure；目前專案 workflow 仍使用 SQLite，避免在未完成 migration 與權限模型前聲稱多人 production persistence。
