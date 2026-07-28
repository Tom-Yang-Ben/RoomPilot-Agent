---
description: 協調 Agent 委派執行 RoomPilot 檢索系統任務，分析任務特性並建議最適合的 Agent。
---

# Agent 委派

## 功能

分析任務需求，建議最適合的專業 Agent，經你確認後委派執行。

## 流程

1. **任務分析** -- 解析任務複雜度、所需技能、風險等級
2. **Agent 匹配** -- 從 13 個 Agent 中選擇最適合的
3. **人類確認** -- 呈現建議，等待你的決定
4. **執行追蹤** -- Agent 執行完畢後回報結果
5. **Context 持久化** -- 依 `.claude-roompilot/rules/subagent-context.md`
   把最終結論寫入 `.claude-roompilot/context/` 對應子目錄

## 輸出格式

```
任務分析:
  任務: [任務描述]
  複雜度: [高/中/低]
  需求技能: [列表]
  管線位置: [Query Understanding / Metadata Filtering / Vector Retrieval /
             Re-ranking / Set Composition / Result Presenter / 資料建置 / 交付]

Agent 建議:
  最佳: [agent-name] (適合度 95%)
  替代: [agent-name] (適合度 80%)

請選擇:
  [1] 啟動建議的 Agent
  [2] 選擇替代 Agent
  [3] 指定其他 Agent
  [N] 取消
```

## 使用方式

```
/hub-delegate                                        # 自動分析當前任務
/hub-delegate security                               # 指定安全稽核（金鑰、輸入驗證）
/hub-delegate --task="調整 retriever.py 排序加權"    # 指定任務描述
```

## 可用 Agent

以下 13 個 Agent 與 `.claude-roompilot/agents/` 實際檔案一一對應。

| Agent | 專長 | RoomPilot 典型任務 |
| :--- | :--- | :--- |
| planner | 功能規劃（opus） | 規劃「擴充六風格詞表 → 重建索引 → 驗收」的迭代路徑 |
| architect | 架構設計（opus） | 調整 Advanced RAG 八段管線的職責切分、排序公式結構 |
| code-quality-specialist | 程式碼審查 | 審查 `retriever.py`／`query_parser.py` 的可讀性與不可變性 |
| security-infrastructure-auditor | 安全稽核 | 稽核 `.anthropic_key` 使用、使用者查詢輸入驗證 |
| test-automation-engineer | 測試自動化 | 建立 pytest 測試套件（**尚未建置**）與檢索回歸集 |
| tdd-guide | TDD 引導 | 以 RED→GREEN→REFACTOR 導入 `query_parser` 契約測試 |
| e2e-validation-specialist | 端到端驗證 | 走完整流程：CLI 檢索 → Gradio UI 卡片目視驗收（無瀏覽器自動化框架） |
| build-error-resolver | 執行錯誤修復 | 修 import／模型載入／Chroma 連線錯誤（**本專案無建置步驟**） |
| refactor-cleaner | 死碼清理 | 清掉 v1/v2 遺留路徑、已捨棄的 statusline 腳本引用 |
| documentation-specialist | 文檔生成 | 同步 `docs/RAG檢索系統說明.md`、`docs/query_parser_spec.md` |
| deployment-expert | 本機執行運維 | 撰寫本機 runbook、環境重建步驟（**本專案無 CI、無 Docker**） |
| workflow-template-manager | 模板管理 | 對接 `VibeCoding_Workflow_Templates/`（19 份 .md，見 `INDEX.md`） |
| general-purpose | 通用任務 | 跨檔案搜尋、資料盤點、`rag_export/` 交付檔比對 |

## 委派前檢查

- 會動到索引或資料的任務，先確認是否要跑 `embed_v3.py --limit 50` 冒煙
- 會呼叫批次 LLM 的任務，先估額度（六風格全量判定約 US$7）
- 同時 2+ 支互不相干的腳本才考慮平行委派（載入 sunnydata-parallel-agents）
- 16 GB 機器：UI 常駐約 4.6 GB，勿在跑 UI 時同時委派批次任務
