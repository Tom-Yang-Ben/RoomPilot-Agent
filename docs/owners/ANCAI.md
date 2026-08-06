# Ancai AI 責任與交接說明

文件版本：2026-08-06。現行產品為 Bella 正式八步流程；本文件描述 Ancai 在目前 runtime 的責任，不代表 `origin/ancai-dev` 原型可直接併入正式產品。

## AI 快速結論

Ancai 是「家具幾何合法性」的唯一裁決者。LLM、RAG、前端與其他 owner 可以提出家具意圖或候選，但不能自行產生合法座標、略過碰撞或改寫淨空規則。

## 主要責任

- 維護 `backend/engine/` 的確定性配置、移動、旋轉、碰撞、邊界、靠牆與淨空規則。
- 接收已確認的房間、牆、門窗、樑柱與家具真實尺寸，輸出合法配置或結構化失敗原因。
- 第 6 步家具新增、替換、拖曳或重新配置後，提供最終合法性判定。
- 保持所有幾何計算可重現，不依賴 LLM 文句或隨機補位。

## 輸入與輸出

```text
layout_json 確認幾何 + catalog 尺寸 + 家具語意意圖
  -> 候選配置
  -> 邊界／牆面／重疊／門窗／動線／淨空檢查
  -> 合法 scene object，或 reason code + 可讀細節
```

- 長度與座標一律使用公分；旋轉單位必須明示。
- 合法家具要保留 catalog ID、尺寸、位置、旋轉與來源追溯。
- 失敗不能以「盡量放入」取代，必須回傳可處理原因。

## 八步流程中的位置

- 第 4 步：只消費 Cody／Django 與使用者確認後的結構，不把低信心辨識當成牆。
- 第 6 步：負責家具配置與每次編輯後的合法性；不負責風格或色卡選擇。
- 第 6 步逐房牆面／地面由 Bella scene adapter 依 `room_id` 保存；Ancai 不改材質。所有家具位置仍使用確認版房間的全域公分座標，不得因切換房間預覽而重置中心。
- 第 7、8 步：已鎖定配置只能被讀取。Ancai 不產生 Yen 視角、不改生圖提示、不改最終圖片。

## 跨 owner 邊界

- Yen 可解釋失敗與提出修復意圖，但不能改變合法性結果。
- Bella 負責 API、保存與 UI；不得在 JavaScript 複製另一套配置規則。
- Cody／Django 提供結構與空間證據；Ancai 只使用已確認或有明確信心度的資料。
- Kai 提供家具真實尺寸與資產身分；Ancai 不改 catalog 主檔。

## 禁止事項

- 不把 `origin/ancai-dev` 的 scene-lab 當成第二套正式前端。
- 不讓 LLM 直接回傳座標後跳過 engine 驗證。
- 不因第 8 步生圖需求而移動牆、門窗、房間邊界或固定家具。

## 最低驗證

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_placement.py tests/test_clearance.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_agent_place.py tests/test_furniture_engine_room_requirements_contract.py
```
