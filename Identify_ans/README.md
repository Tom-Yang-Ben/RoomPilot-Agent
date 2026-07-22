# Identify_ans/ — 人工答案總目錄

所有「人工畫的標準答案」集中在此（進版控）。考卷＝原始 .png 圖；訓練產物（打包件、微調模型、快取）在 `training/`（不進版控、不 push）。

| 子目錄 | 內容 | 用途 |
|---|---|---|
| `pngans/gray/` | `*_ans.png` 像素級答案（21 張灰階） | 灰階管線牆／窗評分（eval_windows.py、score_compare.py） |
| `pngans/color/` | `*_ans.png` 像素級答案（28 張彩色） | 彩色管線牆／窗評分（eval_color_walls.py、eval_cc_masks.py） |
| `own_dataset/` | floor01~54 共 26 題 model.svg 標注（人工審定） | **微調訓練用**＋門位評分 GT（eval_door_match.py）；train/val 清單在其中 |
| `own_eval/` | floor55~79 共 12 題 model.svg 標注 | own 風格房型**保留評分集**，清單見 `own_eval/eval_list.txt` |
| `own_wip/` | floor17/24/30/34/46 共 5 題**未完成**標注 | 上輪審定暫緩的題目（沒改完，非淘汰）；改完一題搬進 `own_dataset/` 並更新 train/val 清單 |

## 鐵律

`own_eval/` 的 12 題**永不進訓練**——模型「讀書」只准用 `own_dataset/` 的 26 題；
考過的題目（own_eval）分數才可信。打包訓練資料（pack_finetune_data.py）只讀 `own_dataset/`。
