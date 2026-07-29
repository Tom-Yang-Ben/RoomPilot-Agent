# TODO：Asset 家具模板證據（第 4 層擴充）——換機交接

> 2026-07-28 深夜於 cody 機實作到一半，23:51 主機當機中斷（0x154 藍屏，
> 詳見下方「當機對照實驗」）。2026-07-29 打包交接，**在新機上接續**。
>
> 目標：`testdata/Asset/` 的 10 類 DWG 切割線稿家具 PNG（1576 張，已在版控）
> 灌入符號模板庫，補足「有家具符號但非 CubiCasa 畫風」的樓層。與 OCR 文字層
> （TODO_ROOM_OCR.md，已完成）互補：有字用字、有家具用家具。

## 斷點狀態（2026-07-28 23:56 中斷當下）

- [x] **階段 A 腳本**：`training/scripts/extract_asset_lib.py` 已寫好——
      10 類 Asset PNG → 48×48 模板，近重複去重後併入 `training/symbol_lib.npz`
      （保留 CubiCasa 系模板）。實體尺寸閘門 wh 依家具物理常識鋪range。
- [x] **單元測試**：`training/tests/test_asset_symbols.py` 5/5 通過（7/29 13:3x 於 cody 機複驗仍綠）。
- [x] **階段 B 計分整合**：`backend/floorplan/floorplan2room.py` `classify_rooms_cc`
      層 4 已加 10 類 kind 的存在制計分（權重表見該檔，含兩項使用者裁決：
      dtable→kitchen、chair(單人沙發)→living；廚房系沿用 `open_living` 防呆）。
      **本次交接 commit 內含，尚未經評測驗證。**
- [ ] **階段 A 尚未實跑**：`training/symbol_lib.npz` 仍是純 CubiCasa 內容
      （sinkicon 2110 / stove 1402 / tubrect 2 / shower 1 / oval 1，mtime 7/16 佐證）。
- [ ] **評測驗證未做**（收工條件見下）。

## 新機執行順序

1. **環境**：`git clone` 後——pyenv 裝 Python 3.12.10 → `python -m venv .venv` →
   `pip install -r requirements.txt`（含 `rapidocr-onnxruntime`，OCR 層必要）。
   評測**不需要**微調模型 pkl：房型語意快取 `cubicasa/room/*_mask.npz` 已在版控，
   其餘管線是純 CV。只有「快取失效需重推語意」或重訓才要搬大檔（見下方材料清單）。
2. **環境驗證**：`.venv/bin/python -m pytest training/tests/ -q` 應全綠。
3. **基準複驗（兼當機釐清的對照組）**：先跑一次現狀評測，確認與 cody 機分數一致：
   ```
   python training/scripts/eval_rooms_cc.py --own-dir testdata/Identify_ans/own_dataset --gt-seg
   python training/scripts/eval_rooms_cc.py --own-dir testdata/Identify_ans/own_dataset
   ```
   cody 機基準（報告已入版控 `training/json/eval_rooms/`）：
   gt-seg 具名 **117/164 = 71.3%**；端對端切割 68.3% / IoU 0.893、配對房型 65.7%；
   窗 P98/R96、門 84/86。
4. **階段 A 實跑**：`python training/scripts/extract_asset_lib.py`
   （預設 `--out training/symbol_lib.npz`；npz 已入版控，改壞可 `git restore` 回退）。
5. **評測驗證**：重跑步驟 3 兩條指令＋窗/門基準。
6. **權重迭代**：如有倒退，調 `classify_rooms_cc` 層 4 Asset 段權重
   （設計原則：存在制不疊加、寧漏勿誤——模板與考卷畫風有落差）。

## 收工條件

- [ ] own_dataset 25 層 gt-seg 具名 ≥ 71.3% **零倒退**（有 Asset 家具的樓層應提升）
- [ ] 端對端切割前後一致（切割不受計分影響，逐字節比對 json）
- [ ] 窗 P98/R96、門 84/86 不動
- [ ] `training/symbol_lib.npz` 合併後版本 commit 回版控

## 當機對照實驗（換機動機）

cody 機（ROG Flow X16, 16GB）7/28-29 連環當機；7/29 12:34 首次真藍屏
**0x154 UNEXPECTED_STORE_EXCEPTION**（醒著執行中直接 bugcheck，與先前三次
睡眠/快速啟動死不同種）。WSL user-mode 腳本不可能直接 bugcheck host——腳本是
觸發器不是病因。頭號嫌犯：cody 機 `.wslconfig` 的 **`autoMemoryReclaim=gradual`**
（實驗性功能，動的正是 0x154 所在的 memory store 路徑，也吻合「批次跑完後
閒置 9~15 分鐘死」的時間窗）。

- **新機**：`.wslconfig` **不要設** `autoMemoryReclaim`。同樣批次照跑——若新機
  穩定，舊機問題實錘（環境/硬體），與本 feature 無關。
- **舊機**：移除該行 + `wsl --shutdown` 後復測；若 0x154 再現依序查
  memtest86+ / `chkdsk C: /scan` / 移除 McAfee。診斷全文在舊機
  Claude memory `host-crash-diagnosis-2026-07`。

## 換機材料清單

| 材料 | 管道 |
| :--- | :--- |
| 程式碼、測試、`training/scripts`＋`tests`＋`json`、`symbol_lib.npz`/`door_lib.npz`、testdata（含 Asset 1576 張）、語意快取 `cubicasa/room/*.npz` | **git clone 即得**（本次交接已入版控） |
| 微調模型 `model_finetuned_v4.pkl`（200MB）、官方權重 `model_best_val_loss_var.pkl`（199MB） | 僅語意快取失效/重推需要——Drive/隨身碟 |
| `training/CubiCasa5k`（6.6G）、`finetune_data*`（830MB）、`eval_rooms/`（192MB）、`room_crops/` | 僅重訓/重建 GT 需要——不急可不搬 |

## 相關檔案速查

| 用途 | 路徑 |
| :--- | :--- |
| 計分整合（層 4 Asset 段） | `backend/floorplan/floorplan2room.py`（`classify_rooms_cc`） |
| 模板灌庫（階段 A） | `training/scripts/extract_asset_lib.py` |
| 符號匹配 | `backend/floorplan/symbol_match.py`（`match_symbols` P5~P95 尺寸閘門） |
| 評測入口 | `training/scripts/eval_rooms_cc.py` |
| 基準報告 | `training/json/eval_rooms/report_own_*.json` |
| 素材 | `testdata/Asset/{bathroom,kitchen,bedroom,livingroom}/…` |
