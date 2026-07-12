# External GLB Source Audit 2026-07-11

本文件整理 2026-07-11 針對 `external_furniture_import_index.json` 與使用者提供 zip 來源的 GLB 對應結果。

## 結論

- 目前外部家具索引共有 `7495` 筆。
- 已在使用者提供的 zip 來源中找到 `3395` 筆外部 GLB。
- 仍有 `4100` 筆外部 GLB 找不到對應 zip entry。
- 合併到 `/api/site-data` 後，目前是 `6349 / 10361` 筆家具有可用 GLB。
- 剩餘缺口不是前端問題，而是 `external_furniture_import_index.json` 指到的 ABO GLB entry 不在目前可讀 zip 裡。

## 已納入後端搜尋的 zip 類型

後端 `roompilot/server/main.py` 目前會在 `dataset/`、`style-rag/`、`C:/Users/user/Downloads/` 中搜尋以下 zip pattern：

- `downloaded-files*.zip`
- `補缺的GLB*.zip`
- `ikea抓取家具glb_中文命名版*.zip`
- `drive-download-202607*.zip`

若 zip 不在上述位置，可用環境變數 `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS` 補充搜尋資料夾，Windows 多路徑用 `;` 分隔。

## 使用者提供 zip 掃描結果

| 來源 | zip 數 | GLB 用途 |
|---|---:|---|
| `downloaded-files(furniture)-20260707T062410Z-3-*.zip` | 34 | 主要可匹配外部 ABO 家具 GLB，目前救回最多 |
| `downloaded-files(home apppliances)-20260706T164953Z-3-*.zip` | 3 | 可匹配部分家電 / Sketchfab / IKEA 家電 GLB |
| `補缺的GLB-20260708T125115Z-3-001.zip` | 1 | 有 804 個 GLB，但主要是補 IKEA / catalog 缺件，不是目前 4100 筆外部 ABO 缺口 |
| `ikea抓取家具glb_中文命名版-20260703T022419Z-3-001.zip` | 1 | 有 1517 個 GLB，屬舊 IKEA 來源，不直接補外部 ABO 缺口 |
| `drive-download-20260706*.zip`、`drive-download-20260708*.zip` | 4 | 本輪掃描沒有外部家具 GLB 命中，偏向材質、牆地板或其他資料 |
| `牆壁 JSON-20260708T082918Z-3-001.zip` | 1 | 牆面 JSON，不是家具 GLB 來源 |
| `尚未確認的 877237.crdownload` | 1 | 瀏覽器未完成下載檔，不應納入掃描 |

## 為什麼不是 10361 / 10361

style-rag / external JSON 的 `zip_entry` 多數長這樣：

```text
downloaded-files/ABO/ABO-rugs-and-mats/ABO-rugs/...
```

實際可讀 zip 內的 entry 多數長這樣：

```text
downloaded-files(furniture)/ABO/ABO-rugs-and-mats/ABO-rugs/...
```

後端已修正這種前綴差異，因此能找到的都會恢復 3D 展示。仍缺的 `4100` 筆，是因為目前所有可讀 zip 裡都沒有對應檔名或商品 ID。

## 仍缺最多的 ABO 來源

| 缺口來源 | 缺少筆數 |
|---|---:|
| `ABO-chairs-stools-and-benches/ABO-stools-benches` | 490 |
| `ABO-rugs-and-mats/ABO-rugs` | 453 |
| `ABO-sofas-and-armchairs/ABO-fabric-sofas` | 441 |
| `ABO-chairs-stools-and-benches/ABO-chairs` | 255 |
| `ABO-chairs-stools-and-benches/ABO-dining-chairs` | 231 |
| `ABO-tables-and-desks/ABO-tables` | 199 |
| `ABO-sofas-and-armchairs/ABO-sofa-beds` | 184 |
| `ABO-decor-and-small-storage/ABO-pillows-cushions` | 165 |
| `ABO-lighting/ABO-lamps` | 146 |
| `ABO-rugs-and-mats/ABO-large-medium-rugs` | 136 |
| `ABO-beds-and-mattresses/ABO-bed-frames` | 114 |
| `ABO-decor-and-small-storage/ABO-flower-pots-planters` | 96 |
| `ABO-rugs-and-mats/ABO-anti-slip-rug-underlays` | 92 |
| `ABO-sofas-and-armchairs/ABO-armchairs` | 92 |
| `ABO-mirrors/ABO-wall-mirrors` | 86 |

## 建議修正方向

1. 若要完全回到 `10361 / 10361`，需要補回上表缺口對應的 ABO GLB zip 或實檔。
2. 若手上沒有那些 GLB，建議重新用目前實際可讀的 zip 產生 external JSON，避免索引指向不存在的檔案。
3. 不建議把幾十 GB zip 直接放進 repo。比較安全的做法是保留 zip 在本機資料夾，並用 `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS` 指到該資料夾。
4. 若 demo 需要穩定，建議只讓前端顯示 `has_model = true` 的家具，缺 GLB 的外部家具先不進候選池。
