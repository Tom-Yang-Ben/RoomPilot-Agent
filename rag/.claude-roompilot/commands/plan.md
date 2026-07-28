---
description: 重述 RoomPilot 檢索需求、評估風險、建立逐步實作計畫。等待使用者確認後才開始寫程式碼。
---

# 規劃指令

此指令呼叫 **planner** agent，在撰寫任何 Python 程式碼之前，
針對 RoomPilot 家具風格檢索系統（9,349 件家具、純檢索無生成端）建立全面的實作計畫。

## 功能說明

1. **重述需求** - 釐清要動的是管線哪一段（Query Understanding／Metadata Filtering／Vector Retrieval／Re-ranking／Budget Allocation／Set Composition／Result Presenter）
2. **識別風險** - 浮現潛在問題和阻礙，並逐項比對 `.claude-roompilot/PROJECT_BRIEF.md` 的「六個坑」
3. **建立步驟計畫** - 將實作拆解為階段，標明是否需要重建索引（`embed_v3.py`）
4. **等待確認** - 必須收到使用者批准才繼續

## 使用時機

- 開始新功能（例如新增一個檢索群組、新增追問按鈕）
- 進行重大架構變更（例如換 embedding 模型、改兩階段檢索為三階段）
- 處理複雜重構（`retriever.py` 的 `build_where` / `search_item` 拆分）
- 多個檔案/模組會受影響（`query_parser.py` + `retriever.py` + `app.py` 連動）
- 需求不明確或模糊（例如「結果不夠準」但沒說是召回問題還是排序問題）

## 運作方式

planner agent 會：

1. **分析請求**並以清晰用語重述需求
2. **拆解為階段**，包含具體可執行的步驟與可驗證的 `.venv-rag/bin/python` 指令
3. **識別依賴關係**（受控詞彙 → schema → 硬過濾 → 排序權重 → UI 卡片，單向）
4. **評估風險**和潛在阻礙（成本、索引重建時間、模型常駐記憶體 4.6 GB）
5. **預估複雜度**（高/中/低）
6. **呈現計畫**並等待你的明確確認

## RoomPilot 規劃必答題

計畫送出前，agent 必須明確回答：

| 問題 | 為什麼要問 |
| :--- | :--- |
| 這個欄位是**硬過濾**還是**軟加權**？ | 房型／類別／價格／尺寸 = 硬過濾；風格／氛圍 = 軟加權；顏色／材質只進 `semantic_query` |
| 需不需要重建索引？ | 全量約 27 分鐘；`--only-changed` 增量約 1.5 分鐘；`--limit 50` 冒煙 |
| 有沒有動到 SSOT 文件的契約？ | `docs/query_parser_spec.md`、`taxonomy_v2.json`、`category_groups.json` 衝突時**以文件為準** |
| 會不會燒 API 額度？ | 需求解析每次約 US$0.005；批次風格判定全量約 US$7 |

## 重要提醒

**關鍵**: planner agent **不會**在你明確確認計畫前撰寫任何程式碼。

如需修改，請回覆：
- "修改: [你的變更]"
- "不同方法: [替代方案]"
- "跳過階段 2 先做階段 3"

## 與其他指令的搭配

規劃完成後：
- 用 `/tdd` 以測試驅動開發方式實作（注意：pytest **尚未建置**，第一步要先建測試骨架）
- 如有匯入／型別／資料載入錯誤用 `/build-fix`
- 用 `/review-code` 審查完成的實作
- 用 `/verify` 跑解析冒煙、檢索冒煙、索引覆蓋率檢查
