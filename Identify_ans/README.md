# Identify_ans/ — 人工答案總目錄

所有「人工畫的標準答案」集中在此（進版控）。考卷＝原始 .png 圖；訓練產物（打包件、微調模型、快取）在 `training/`（不進版控、不 push）。

| 子目錄 | 內容 | 用途 |
|---|---|---|
| `pngans/gray/` | `*_ans.png` 像素級答案（38 張灰階） | 灰階管線牆／窗評分（eval_windows.py、score_compare.py） |
| `pngans/color/` | `*_ans.png` 像素級答案（28 張彩色） | 彩色管線牆／窗評分（eval_color_walls.py、eval_cc_masks.py） |
| `own_dataset/` | floor01~54 共 26 題 model.svg 標注（人工審定） | **微調訓練用**＋門位評分 GT（eval_door_match.py）；train/val 清單在其中 |
| `own_eval/` | floor55~79 共 12 題 model.svg 標注（人工審定） | own 風格房型**保留評分集**，清單見 `own_eval/eval_list.txt` |

## 鐵律

`own_eval/` 的 12 題**永不進訓練**——模型「讀書」只准用 `own_dataset/` 的 26 題；
考過的題目（own_eval）分數才可信。打包訓練資料（pack_finetune_data.py）只讀 `own_dataset/`。

> 註（2026-07-22）：
> - 原 `own_wip/`（floor17/24/30/34/46 共 5 題未完成標注）淘汰刪除，對應的 `pngans/gray/` 答案圖一併移除（gray 41→38 張）。
> - `own_eval/` 12 題的 model.svg 已從 v2.13 草稿人工審定完成，但**維持保留評分集身分、不併入訓練**。
