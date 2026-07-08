# Schema 速查

每個檔案的完整欄位定義在 `schemas/*.json`(JSON Schema draft-07),範例在 `examples/*.json`。
下表為速查與資料流關係。

| 檔案 | Schema | 範例 | 產生者 → 消費者 |
|------|--------|------|----------------|
| requirement.json | `schemas/requirement.schema.json` | `examples/requirement.json` | Agent 1 → Agent 2, validate |
| architecture.json | `schemas/architecture.schema.json` | `examples/architecture.json` | parse_dxf.py → Agent 3, validate, build_glb |
| rule.json | `schemas/rule.schema.json` | `examples/rule.json` | 人工 → Agent 2, validate |
| furniture_candidates.json | `schemas/furniture_candidates.schema.json` | `examples/furniture_candidates.json` | Agent 2 → Agent 3 |
| furniture.json | `schemas/furniture.schema.json` | `examples/furniture.json` | Agent 3 → validate, build_glb |
| validation_report.json | `schemas/validation_report.schema.json` | — | validate_layout.py → Agent 4 |

## 全管線共通約定(再次強調)
- 單位:公分 (cm)。
- 座標:X 右、Y 上,原點左下;`position` 為物件中心(牆為中心線中點)。
- `rotation`:逆時針度,0 時家具正面朝 +Y。
- 家具 `dimensions`:width=本地 X、depth=本地 Y、height=Z。
- 這套約定由 `scripts/geometry.py` 統一實作(footprint 計算),agent 與腳本共用,不得各自解讀。

## 用 schema 驗證 agent 輸出(建議)
```python
import json, jsonschema
schema = json.load(open("schemas/furniture.schema.json"))
data   = json.load(open("furniture.json"))
jsonschema.validate(data, schema)   # 失敗即重試該 agent
```
