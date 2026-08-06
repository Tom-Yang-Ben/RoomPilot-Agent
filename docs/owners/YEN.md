# Yen AI 責任與交接說明

文件版本：2026-08-06。Yen 擁有 `backend/agent/` 的需求專業化、RAG 選件語意、驗證說明、生圖／修圖 prompt 與報告內容語意；Bella 將這些能力接入正式八步 UI 與 API。

## AI 快速結論

Yen 負責「理解與表達」，不負責幾何座標。Yen 必須把問卷整理成專業室內設計語言並保留來源，再交給 RAG、配置與生圖；不得因文字要求而改變第 4 步結構、第 6 步固定家具或第 7 步鎖定視角。

## Agent 模組架構與接線狀態

```text
問卷／逐房需求／全屋需求
  -> RequirementSkill：專業室內設計語言 + deterministic fallback（模組已實作，正式 Step 5 待接）
  -> Furniture sub-agent：RAG 候選、允許候選集選件與原因（Master 流程待接）
  -> Validation sub-agent：讀取 Ancai 結果並提出修復意圖
  -> GenPic sub-agent：鎖定結構／家具／材質／逐房視角後生圖或修圖（正式 Step 8 已接）
  -> Report sub-agent：設計說明與工程／預算內容節點（正式成果包待接）
```

`backend/agent/master.py` 可以編排 Furniture、Validation、GenPic、Report 四個 sub-agent；`skills/` 提供 prompt／schema，`tools/` 是確定性工具層，`documents.py` 是可保存的 blackboard。但正式 `backend/server/` 目前沒有呼叫 `build_master()`：Master 的 A/B 測試流程不是現行八步 UI。現行只有 `ai_render_service.py` 直接使用 `GenPicAgent`；`RequirementSkill` 與 `ReportAgent` 仍需 Bella adapter。

## 八步流程中的位置

- 第 5 步：目標是把全屋與逐房問卷分成必要功能、偏好、可選建議與家電上下文並保留來源；目前家具 RAG jobs 已接線，`RequirementSkill` 專業化尚未接入正式 API。
- 第 6 步：輸出家具候選、說明與修復意圖；座標和合法性一律交給 Ancai。
- 第 7 步：使用鎖定的第 6 步場景，讓 Bella／Three.js 提供每房三個綁定 `room_id` 的全室構圖；Yen 負責視角語意與 prompt 契約，不改家具或座標。
- 第 8 步：確認大致生圖詞彙並提醒不可修改空間；全屋初稿完成後，每張房間初稿最多一次成功修圖。
- 最終交付：Report Agent 目標提供逐房設計摘要與設計師方法論參照，但尚未接入。現行由 Bella deterministic builder 組稿並做敏感欄位 denylist 移除。

## 生圖與修圖不可變規則

- Prompt 必須包含整體風格、逐房／全屋問卷、已選材質、鎖定家具、第 7 步相機與固定結構限制。
- 送出前提醒不能修改空間大小、房間邊界、牆、門窗、樑柱、固定家具位置或視角。
- 每房初稿圖片只有一次成功修圖額度；失敗請求不得錯誤消耗額度。現行正式保護在 Bella 後端專案狀態，不能宣稱 Master 也在 runtime 執行。
- OpenRouter 未設定或回傳 402／其他錯誤時要顯示真實原因，不得用 placeholder 假裝正式 AI 圖。
- 主模型預設 `google/gemini-3.1-flash-image`，fallback 為 `google/gemini-2.5-flash-image`；部署可用環境變數覆蓋。

## 設計師參照與報告

- 可以寫「參照某設計師的方法論」，但必須附上不代表本人參與或背書的說明。
- 不捏造設計師原話、工程安全結論或價格。
- 價格只讀 Kai 的來源欄位；缺價一律待報價。
- 工程數量與合法性讀取 Cody／Django／Ancai／Bella 保存快照，不自行重算幾何。

## 跨 owner 邊界

- Kai 擁有 catalog truth、價格與檢索欄位。
- Django 提供空間關係、layout evaluation 與 RAG evidence。
- Ancai 擁有配置、碰撞與淨空結果。
- Bella 擁有可見問卷、專案保存、API、目前的 denylist 資安基線與成果包 UI。

## 禁止事項

- 不恢復公開 A/B 方案；Agent 內部候選策略不能變成第 6 步 A/B 使用者流程。
- 不直接輸出或修改家具座標。
- 不把 token、cookie、密碼、連線字串或原始個資寫入 prompt、log 或成果包。
- 不把 `backend/agent/IMPLEMENTATION_REPORT.md` 的歷史「尚未整合」敘述當成現況。

## 最低驗證

```powershell
.\.venv\Scripts\python.exe -m pytest -q backend/agent/tests
.\.venv\Scripts\python.exe -m pytest -q tests/test_agent_knowledge.py tests/test_agent_select.py tests/test_agent_place.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_render_openrouter.py tests/test_scene_room_requirements.py tests/test_scene_delivery.py
```
