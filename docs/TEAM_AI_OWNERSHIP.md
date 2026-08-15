# RoomPilot 模組責任與公開資料邊界

本文件只描述目前公開 repository 的責任切分。歷史分支、私有 catalog 筆數與未附帶的資產不構成公開契約。

| 路徑 | 主要責任 | 公開邊界 |
|---|---|---|
| `backend/server/` | Bella：FastAPI、SQLite 專案保存、八步流程調度 | 僅支援 loopback 本機開發 |
| `backend/server/static/` | Bella：唯一正式 HTML/CSS/JS/Three.js 前端 | 不建立第二套 React production app |
| `backend/floorplan/`、`backend/upgrade3d/` | Cody：圖面辨識、確認與 3D 結構轉換 | 權重與來源不明測資不進 Git；缺件須誠實降級 |
| `backend/spatial_data/` | Django：空間 evaluation、家具檢索與排序 | 不決定碰撞、淨空或幾何合法性 |
| `backend/catalog/`、`scripts/sql/` | Kai：catalog schema、fixture 與資料庫讀取契約 | portable 只用自製 fixture；full 只讀開發者提供的授權資料 |
| `backend/agent/` | Yen：需求結構化、選件與說明 | 不輸出家具合法座標 |
| `backend/engine/` | Ancai：擺放、碰撞、淨空、移動與合法性 | 幾何合法位置的唯一裁決者 |
| `tests/` | 對應模組 owner；Bella 維護整合門檻 | 公開 fixture 必須匿名、可重建且有 provenance |
| `docs/contracts/` | 受影響 owner 共同維護 | 先看 [契約索引](contracts/README.md) 的現行／歷史標記 |

## 資料流

```text
PNG/JPG/DXF
  -> 辨識與人工確認
  -> layout_json（cm）
  -> 需求結構化與家具候選
  -> backend/engine 幾何驗證
  -> scene_json（cm）
  -> 正式 2D/3D UI
  -> 可選的外部 AI / delivery；未設定時 unavailable
```

## Profile 邊界

- `portable`：預設。SQLite、自製程序化家具、自製平面圖 fixture；不需資料庫、模型或 API 金鑰。
- `full`：明確 opt-in。PostgreSQL/pgvector 連線失敗時回 unavailable／503，不得回退成另一批資料。
- 模型、GLB、商品圖、使用者圖、資料庫 dump、embedding 與私有評測資料都留在 ignored runtime 或外部儲存。

跨模組修改必須同時測 producer 與 consumer，並記錄欄位、單位、保存邊界和 fallback 行為。

## Owner profiles

- [Bella](owners/BELLA.md)
- [Cody](owners/CODY.md)
- [Django](owners/DJANGO.md)
- [Kai](owners/KAI.md)
- [Yen](owners/YEN.md)
- [Ancai](owners/ANCAI.md)
- [Ben](owners/BEN.md)
