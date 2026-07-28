---
description: 以 CLI 端到端檢索 + Gradio 冒煙驗證 RoomPilot 完整旅程。無瀏覽器自動化。
---

# E2E 指令

此指令呼叫 **e2e-validation-specialist** agent 來生成、維護和執行端到端驗證。

> ⚠️ **本專案無 Playwright、無瀏覽器自動化、無 CI**。
> RoomPilot 的 E2E ＝ **CLI 端到端檢索**（`query_parser.py` → `retriever.py` 全鏈路真跑）
> ＋ **Gradio 冒煙**（`app.py` 可 build、可 launch、卡片 HTML 有內容）。
> 一律 `PY=.venv-rag/bin/python`，服務位址 `http://127.0.0.1:7860`。

## 功能說明

1. **生成測試旅程** - 為典型檢索需求建立可重放的查詢清單（風格 × 房型 × 預算）
2. **執行 E2E 檢索** - 真打 Haiku 解析 + 真查 Chroma + 真跑 reranker
3. **擷取成品** - 失敗時保存解析 JSON、`where` 條件、命中筆數、分數分佈
4. **產出報告** - 每條旅程的通過/失敗與主導風格是否符合預期
5. **識別不穩定案例** - 隔離每次結果都跳動的查詢（通常是加權接近的邊界案例）

## 使用時機

- 測試關鍵使用者旅程（單品檢索、整室搭配、預算分配、追問收斂）
- 驗證多步驟流程端到端運作（解析 → 硬過濾 → 向量 → rerank → 加權 → 去重 → 卡片）
- 測試 Gradio UI 互動（送出查詢、追問按鈕）
- 驗證解析端與檢索端的欄位契約一致（受控詞彙 ↔ `chroma_metadata`）
- 交付前（`rag_export/` 四個交付檔產出後）做最終確認

## 運作方式

e2e-validation-specialist agent 會：

1. **分析使用者流程**並識別測試場景（六風格 × 9 房型 × 有/無預算）
2. **生成 CLI 旅程腳本**，每條旅程 = 一句自然語言需求 + 預期斷言
3. **依序執行旅程**（單一環境，無跨瀏覽器概念；device 走 MPS 退 CPU）
4. **擷取失敗**的解析輸出、`where` dict、Chroma 回傳筆數
5. **生成報告**含每條旅程的結果與耗時（reranker 是延遲主因，每 50 筆約 10 秒）
6. **識別不穩定案例**並建議修復（調權重前先確認不是 rerank 分數本身抖動）

## 快速指令

```bash
PY=.venv-rag/bin/python

# 旅程 1：單品檢索（北歐風客廳沙發）
$PY rag_pipeline/retriever.py "北歐風客廳想找一張淺色布沙發，預算三萬"

# 旅程 2：整室搭配 + 預算分配（日式臥室）
$PY rag_pipeline/retriever.py "日式侘寂風臥室全套，木質調，總預算八萬"

# 旅程 3：只驗需求解析（不查庫，最省時）
$PY rag_pipeline/query_parser.py "工業風餐廳，深色金屬，要耐用"

# 旅程 4：奶油風 × 美式（相容矩陣 cream↔american 0.7）
$PY rag_pipeline/retriever.py "奶油色系客廳，帶點美式復古"

# 旅程 5：極簡 × 尺寸硬過濾（尺寸必須來自查詢，不可推測）
$PY rag_pipeline/retriever.py "現代極簡書房，書桌寬度不超過 120 公分"

# Gradio 冒煙：只建版面不啟服務（最快，可放進迴圈）
$PY -c "import rag_pipeline.app as a; ui=a.build_ui(); print('UI OK', type(ui).__name__)"

# Gradio 冒煙：實際啟動並確認埠有回應（Ctrl-C 結束）
$PY rag_pipeline/app.py    # → http://127.0.0.1:7860

# 空查詢冒煙：不打 API、不查庫，只確認 search() 的防呆分支不炸
$PY -c "
import rag_pipeline.app as a
out = a.search('   ')
print('empty-query OK, fields =', len(out))"

# 卡片 HTML 冒煙：search() 回傳 tuple，最後一個元素是 results_html
$PY -c "
import rag_pipeline.app as a
html = a.search('北歐風客廳沙發')[-1]
print('html chars :', len(html))
print('has card   :', 'data:image' in html)"
```

## 旅程斷言表

| 旅程 | 主要斷言 |
| :--- | :--- |
| 單品檢索 | 回傳 `FINAL_TOP_K=8` 筆以內、主導風格為 `scandinavian`、無重複 `id` |
| 整室搭配 | 每個檢索群組至少 1 筆、預算分配總和不超過使用者上限 |
| 只驗解析 | 輸出符合 `docs/query_parser_spec.md` schema、受控詞彙不出現自創值 |
| 相容矩陣 | 次要風格命中時 `style_compat` 分量 > 0，不被硬過濾掉 |
| 尺寸硬過濾 | `where` 含尺寸上界；查詢未提尺寸時**不得**出現尺寸條件（坑 5） |
| Gradio 冒煙 | `build_ui()` 不拋例外、`launch()` 綁 `127.0.0.1:7860`、卡片 HTML 非空 |

## 最佳實踐

**應該做:**
- 把旅程寫成可重放的 shell 或 pytest 腳本，避免每次手打查詢
- 斷言**行為**（主導風格、筆數、預算上限），不是逐字比對商品名
- 等模型真正載入完再計時，別把 4.6 GB 預熱算進檢索延遲
- 測試關鍵使用者旅程端到端
- 交付 `rag_export/` 前執行整組旅程
- 失敗時把解析 JSON 與 `where` dict 一起貼出來

**不應該做:**
- 對同一句查詢斷言固定的商品 ID（rerank 有浮動，會變成不穩定測試）
- 測試實作細節（呼叫次數、內部變數）
- 在 E2E 中大量呼叫 Haiku（每次約 US$0.005，旅程控制在個位數）
- 忽略不穩定案例
- 用 E2E 測每個邊界情況（純函式交給 `/tdd` 的 pytest）
- 同時跑批次工作與 UI（16 GB 機器會被 4.6 GB 常駐模型擠爆）

## 與其他指令的搭配

- 用 `/plan` 識別要測試的關鍵旅程
- 用 `/tdd` 做單元測試（更快、更細粒度；pytest 尚未建置）
- 用 `/e2e` 做整合和使用者旅程測試
- 用 `/verify` 先確認索引覆蓋率與資料檔完整性，再跑 E2E
- 用 `/review-code` 驗證測試品質
