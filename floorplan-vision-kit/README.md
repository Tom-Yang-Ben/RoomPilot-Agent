# RoomPilot Floorplan Vision Kit

這個資料夾是 Godzilla／Claude Code 的功能與使用入口；可執行程式位於
`roompilot/floorplan/vision/`，自動載入的 agent、skill 與 commands 位於根目錄 `.claude/`。

## 已提供功能

- `630 cm` 等尺寸文字與尺寸線端點配對，在 API 邊界立即轉成 `m_per_px`。
- 像素 → 左下角原點 → Python 公尺座標。
- OpenCV 牆、門、窗基線偵測；人工確認資料可覆蓋自動結果。
- 客廳、廚房、浴廁、臥室等繁中房名標準化。
- 水、電、排水、瓦斯、排風需求推導，保留來源、信心與需確認狀態。
- PNG/JPG analyze API、confirm API、毫米 DXF 與既有 3D／家具引擎串接。
- 單元、HTTP integration 與 analyze→confirm→scene E2E 測試。

## Godzilla 使用方式

在 Claude Code 的 RoomPilot 專案根目錄執行：

```text
/floorplan-vision-plan
/floorplan-vision-tdd
/floorplan-vision-e2e
/floorplan-vision-review
```

也可直接要求：

```text
使用 floorplan-vision-specialist 完成下一張工作票。
```

## 安裝

RoomPilot runtime：

```powershell
$env:UV_CACHE_DIR = (Resolve-Path .uv-cache).Path
.\.venv\Scripts\uv.exe sync --extra server --extra vision
```

需要自動辨識 `630` 與繁中房名時加裝 OCR extra：

```powershell
.\.venv\Scripts\uv.exe sync --extra server --extra vision --extra ocr
```

PaddleOCR 未安裝時 API 仍接受 OCR observations 或人工尺寸確認。
不要複製 Godzilla 上游的寬鬆 `settings.json`；本 kit 只新增 agent、skill 與 commands。

## API

### `POST /api/floorplan/analyze`

`multipart/form-data`：

- `file`：PNG／JPG／WEBP。
- `calibration_json`：可選，`distance_cm`、`start_px`、`end_px`。
- `ocr_json`：可選 OCR observation 陣列，供測試、人工校正或外部 OCR adapter。
- `geometry_json`：可選，已確認的 wall／door／window 像素端點。
- `observed_utilities_json`：可選，圖面設備觀察，來源標記為 `floorplan_observation`。
- `brief_json`：可選，使用者已確認設備需求，來源標記為 `user_confirmation`。

回傳 `analysis`、`requirements` 與 OCR provider。只要尺度或牆未確認，
`requires_confirmation` 就不允許正式進入方案生成。
自動來源 `opencv_geometry` 必須在 confirm 時明確提交修正後的 walls／doors／windows，
不能用空 corrections 繞過。

### `POST /api/floorplan/confirm`

```json
{
  "analysis": {},
  "corrections": {
    "scale": {},
    "walls": [],
    "doors": [],
    "windows": [],
    "rooms": []
  }
}
```

回傳確認 analysis、需求、DXF 文字與既有引擎 floorplan payload。

## 測試

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_floorplan_vision.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_floorplan_vision_api.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
```

## 安全界線

- OCR／OpenCV 自動結果是「候選」，不是施工圖。
- 瓦斯永遠是條件式需求，須確認能源類型、設備與通風。
- 水電瓦斯施工前須由合格建築、機電與瓦斯專業人員確認。
- 影像缺尺度、牆未閉合或門窗信心不足時，UI 必須要求人工確認。

詳細契約見 [SPEC.md](SPEC.md)，工作順序見 [tickets](tickets/README.md)。
