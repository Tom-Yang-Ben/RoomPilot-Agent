---
description: 全面品質評估 RoomPilot 檢索管線，根據 VibeCoding 模板進行分析並建議適合的 Agent。
---

# 品質評估

## 分析內容

針對當前專案或指定路徑執行品質檢查（一律 `PY=.venv-rag/bin/python`）：

1. **程式碼品質** -- 可讀性、複雜度、重複、命名、不可變性（不得就地改 `parsed` / `item`）
2. **架構合規** -- Advanced RAG 七段管線分層、`query_parser` → `retriever` → `app` 單向依賴、模組化
3. **測試覆蓋** -- 單元/整合/E2E 覆蓋率（**pytest 尚未建置**，現況以 `/verify` 冒煙代替，覆蓋率記 N/A）
4. **安全檢查** -- 硬編碼秘密（`.anthropic_key` 不得回顯或提交）、查詢輸入驗證、路徑組裝
5. **模板合規** -- 對照 VibeCoding 模板檢查點
6. **檢索正確性** -- 六個坑 + 硬過濾／軟加權界線（見下方檢核清單）
7. **索引健康度** -- Chroma `furniture_v3` count 對照 v3 `rag_indexable` 筆數（基準 9349/9349）

## 檢索正確性檢核清單

### 六個坑

- [ ] **坑 1** `rag_indexable` 未進 Chroma `where`（頂層欄位、不在 `chroma_metadata`，寫了命中 0 筆）
- [ ] **坑 2** rerank 分數未再套 sigmoid（`bge-reranker-v2-m3` 經 CrossEncoder 已輸出 0–1）
- [ ] **坑 3** 可為 null 的 enum 用 `anyOf`（直接寫 type 陣列會 400）
- [ ] **坑 4** `setdefault("HF_HUB_OFFLINE", "1")` 未被移除（HF Hub 限流會卡數分鐘）
- [ ] **坑 5** 尺寸為硬過濾，LLM 未用常識推測（猜錯直接濾掉正確結果）
- [ ] **坑 6** reranker 仍為 `BAAI/bge-reranker-v2-m3`，未換成 ms-marco MiniLM（中文會劣化）

### 硬過濾 / 軟加權界線

| 欄位類別 | 正確處理 | 越界後果 |
| :--- | :--- | :--- |
| 房型／類別／價格／尺寸 | **硬過濾**（Chroma `where`） | 條件過嚴 → 命中 0 筆 |
| 風格／氛圍 | **軟加權**（排序公式） | 誤寫進 `where` → 相容風格被整批濾掉 |
| 顏色／材質 | **只進 `semantic_query`** | 誤做過濾 → 召回嚴重壓縮 |

- [ ] 排序公式仍為 `final = 0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence`
- [ ] 漏斗 `VEC_TOP_K=50` → `RERANK_TOP_K=20`（配件 12）→ `FINAL_TOP_K=8` 完整
- [ ] 六風格值域來自 `taxonomy_v2.json`，未硬編碼

## 輸出格式

```
品質評估結果:
  程式碼品質:  [A/B/C/D]
  架構合規:    [通過/需改善]
  測試覆蓋:    [N/A — pytest 尚未建置]
  安全檢查:    [通過/有風險]
  模板合規:    [X]%
  六個坑:      [6/6 通過 / X 項違反]
  過濾界線:    [通過/有越界]
  索引健康度:  [9349/9349 = 100.00%]

建議的 Agent:
  [1] code-quality-specialist -- 深度程式碼審查
  [2] security-infrastructure-auditor -- 安全稽核（金鑰、輸入驗證）
  [3] test-automation-engineer -- 建立 pytest 骨架與測試補強
  [4] deployment-expert -- 本機執行 runbook 就緒檢查（無 CI／無 Docker）

請選擇 (1-4) 或輸入 N 跳過:
```

## 使用方式

```
/check-quality                          # 檢查整個專案
/check-quality rag_pipeline/            # 檢查檢索管線
/check-quality rag_pipeline/retriever.py  # 只檢查過濾與排序
/check-quality json_adjustment/         # 檢查資料建置與交付規格
```
