---
name: 02-bdd-scenario-spec
description: "BDD 可執行規格 (Gherkin) - 將家具檢索需求轉化為精確的業務語言場景"
stage: "Planning"
template_ref: "03_behavior_driven_development_guide.md"
---

# 指令 (你是 BDD 引導專家)

以 Gherkin 語法產出可執行規格,使用業務語彙而非技術實作細節。所有場景必須可觀測、可重現、可自動化驗證。

本樣式的所有場景範例一律取自 **RoomPilot 家具風格檢索系統**(自然語言需求 → 從 9,349 件家具檢索 Top-8)。

> ⚠️ **本專案尚未建置測試套件**。步驟定義骨架以 **pytest + pytest-bdd** (Python 3.11) 為預設建議,
> 執行方式一律 `.venv-rag/bin/python -m pytest`。在測試套件實際建立前,場景仍具規格價值:
> 可先以 `.venv-rag/bin/python rag_pipeline/retriever.py "<需求>"` 手動走一次驗收。

**業務語彙對照** (寫場景時只用左欄,不寫右欄):

| 業務語彙 (可寫進場景) | 對應實作 (不要寫進場景) |
|----------------------|------------------------|
| 「奶油風」 | `styles=["cream"]` |
| 「預算三萬內」 | `price_max=30000`、Chroma `where` 硬過濾 |
| 「客廳」 | `room_type="living_room"` |
| 「回傳 8 件候選」 | `FINAL_TOP_K=8` |
| 「風格相容」 | `taxonomy_v2.json` 的 6×6 `style_compat` 矩陣 |
| 「系統請使用者補充條件」 | `needs_clarification=true` + `clarify_options` |

## 交付結構

### 1. Feature 檔案結構

```gherkin
Feature: [功能名稱]
  作為 [用戶角色]
  我想要 [功能描述]
  以便 [達成目標]

  背景知識 (Background):
    這個功能的業務脈絡說明...
    關鍵業務規則:
    - 規則 1
    - 規則 2

  規則 (Rule): [業務規則名稱]

    場景 (Scenario): [正常流程場景]
      假設 (Given) [前置條件]
      當 (When) [觸發動作]
      則 (Then) [預期結果]
      而且 (And) [額外驗證]

    場景大綱 (Scenario Outline): [參數化場景]
      假設 (Given) [前置條件使用<參數>]
      當 (When) [觸發動作使用<參數>]
      則 (Then) [預期結果使用<參數>]

      範例 (Examples):
        | 參數1 | 參數2 | 預期結果 |
        | 值1   | 值2   | 結果1    |
        | 值3   | 值4   | 結果2    |
```

**RoomPilot 填實範例**:

```gherkin
Feature: 自然語言家具檢索
  作為 自住裝修者
  我想要 用一句話描述想要的風格與預算
  以便 不必知道商品分類與規格,也能拿到真的搭的候選家具

  背景知識 (Background):
    系統收錄 9,349 件家具,每件都標有主導風格、氛圍詞、價格與尺寸。
    關鍵業務規則:
    - 房型、類別、價格、尺寸是「硬條件」—— 不符合的物件一律不出現
    - 風格與氛圍是「軟條件」—— 不符合但相容的物件仍可出現,只是排後面
    - 顏色與材質只影響語意相似度,不作為篩選條件
    - 每次檢索最多回傳 8 件候選

  規則 (Rule): 預算是硬條件

    場景 (Scenario): 指定預算的單品檢索
      假設 (Given) 使用者輸入「奶油風沙發,預算三萬內」
      當 (When) 系統執行檢索
      則 (Then) 回傳 8 件候選家具
      而且 (And) 每一件的售價都不超過 30000 元
```

### 2. Gherkin 關鍵詞使用規範

#### Given (假設 / 前置條件)
- **目的**: 設定測試的初始狀態
- **業務語言**: 描述業務狀態,而非技術操作
- **範例**:
  ```gherkin
  # ✅ 好的寫法 (業務語彙)
  Given 家具庫中收錄 9,349 件家具
  Given 使用者輸入「奶油風沙發,預算三萬內」
  Given 客廳沙發的售價中位數為 18000 元

  # ❌ 不好的寫法 (技術細節)
  Given Chroma collection furniture_v3 已載入
  Given 呼叫 parse_query() 取得 styles=["cream"]
  Given HF_HUB_OFFLINE 環境變數已設為 1
  ```

#### When (當 / 觸發動作)
- **目的**: 描述觸發的業務行為
- **單一職責**: 每個 When 應該只描述一個動作
- **範例**:
  ```gherkin
  # ✅ 好的寫法
  When 系統執行檢索
  When 使用者選擇追問選項「客廳」
  When 系統重新建立家具索引

  # ❌ 不好的寫法
  When 使用者點擊「檢索」按鈕並等待 Gradio 回填 HTML
  When retrieve() 被呼叫
  ```

#### Then (則 / 預期結果)
- **目的**: 驗證可觀測的業務結果
- **可驗證**: 必須是可以自動驗證的結果
- **範例**:
  ```gherkin
  # ✅ 好的寫法
  Then 回傳 8 件候選家具
  Then 每一件的售價都不超過 30000 元
  Then 至少 6 件的主導風格與「奶油風」相容度不低於 0.7

  # ❌ 不好的寫法
  Then 檢索結果正確
  Then 卡片看起來很搭
  Then 向量有被算出來
  ```

### 3. 場景類型覆蓋

#### 3.1 正常流程 (Happy Path)
```gherkin
Scenario: 使用者成功取得符合風格與預算的沙發
  Given 家具庫中收錄 9,349 件家具
    And 使用者輸入「奶油風沙發,預算三萬內」
    And 系統已備妥六種風格的相容度對照表
  When 系統執行檢索
  Then 回傳 8 件候選家具
    And 每一件的售價都不超過 30000 元
    And 每一件都屬於沙發類別
    And 至少 6 件的主導風格與「奶油風」相容度不低於 0.7
    And 每一件都附有正面渲染圖與售價
```

#### 3.2 邊界條件 (Edge Cases)
```gherkin
Scenario Outline: 驗證預算條件對候選數量的影響
  Given 使用者要找「奶油風客廳沙發」
    And 系統每次最多回傳 8 件候選
  When 使用者將預算設為 <預算> 元
  Then 系統顯示 <結果訊息>
    And 回傳的候選件數為 <候選件數> 件

  Examples:
    | 預算   | 結果訊息               | 候選件數 |
    | 30000  | 找到符合條件的家具     | 8        |
    | 8000   | 找到符合條件的家具     | 8        |
    | 3000   | 符合條件的家具較少     | 2        |
    | 500    | 沒有符合預算的家具     | 0        |
```

```gherkin
Scenario Outline: 驗證品項數量上限
  Given 使用者一次描述 <描述品項數> 個品項的需求
  When 系統解析需求
  Then 系統實際處理 <處理品項數> 個品項
    And 系統顯示 <結果訊息>

  Examples:
    | 描述品項數 | 處理品項數 | 結果訊息                 |
    | 1          | 1          | 單品檢索                 |
    | 4          | 4          | 整組配置                 |
    | 6          | 6          | 整組配置                 |
    | 9          | 6          | 品項過多,只處理前 6 項   |
```

#### 3.3 異常流程 (Exception Paths)
```gherkin
Scenario: 需求解析服務暫時無法使用
  Given 使用者輸入「奶油風沙發,預算三萬內」
    And 需求解析服務目前無法回應
  When 系統執行檢索
  Then 系統不回傳任何候選家具
    And 使用者看到「需求解析暫時無法使用,請稍後重試」訊息
    And 系統不顯示任何不符合條件的替代結果
    And 家具索引維持原狀,未被更動
```

```gherkin
Scenario: 條件過於嚴苛導致無結果
  Given 使用者輸入「工業風、預算兩千內、寬度不超過 40 公分的雙人沙發」
  When 系統執行檢索
  Then 系統回傳 0 件候選家具
    And 使用者看到「沒有同時符合預算與尺寸的家具」訊息
    And 系統建議放寬預算或尺寸
    And 系統不自動放寬硬條件
```

```gherkin
Scenario: 使用者描述過於模糊
  Given 使用者輸入「想找便宜一點的椅子」
  When 系統執行檢索
  Then 系統請使用者補充條件
    And 系統提供不超過 4 個追問選項
    And 追問選項包含房型或風格的具體選擇
```

#### 3.4 業務規則驗證 (Business Rules)
```gherkin
Rule: 風格相容度決定候選排序

  Background:
    Given 系統有以下六種風格的相容度規則
      | 使用者要的風格 | 物件的主導風格 | 相容度 |
      | 奶油風         | 奶油風         | 1.0    |
      | 奶油風         | 美式風         | 0.7    |
      | 日式風         | 北歐風         | 0.9    |
      | 工業風         | 奶油風         | 0.2    |

  Scenario Outline: 相容風格仍可入選但排在後面
    Given 使用者要找 <要的風格> 的沙發
      And 候選家具的主導風格為 <物件風格>
    When 系統執行檢索
    Then 該家具 <是否入選>
      And 其風格加分為 <風格加分>

    Examples:
      | 要的風格 | 物件風格 | 是否入選 | 風格加分 |
      | 奶油風   | 奶油風   | 入選     | 最高     |
      | 奶油風   | 美式風   | 入選     | 中等     |
      | 日式風   | 北歐風   | 入選     | 高       |
      | 工業風   | 奶油風   | 入選但墊底 | 極低   |
```

```gherkin
Rule: 硬條件與軟條件的界線

  Background:
    Given 系統對需求條件有以下處理規則
      | 條件類型 | 處理方式         | 不符合時的結果       |
      | 房型     | 硬過濾           | 完全不出現           |
      | 類別     | 硬過濾           | 完全不出現           |
      | 價格     | 硬過濾           | 完全不出現           |
      | 尺寸     | 硬過濾           | 完全不出現           |
      | 風格     | 軟加權           | 仍可出現,排序下降    |
      | 氛圍     | 軟加權           | 仍可出現,排序下降    |
      | 顏色     | 只影響語意相似度 | 仍可出現             |
      | 材質     | 只影響語意相似度 | 仍可出現             |

  Scenario Outline: 條件不符時的行為
    Given 使用者指定 <條件類型> 為 <指定值>
      And 某件家具的 <條件類型> 為 <實際值>
    When 系統執行檢索
    Then 該家具 <出現與否>

    Examples:
      | 條件類型 | 指定值   | 實際值   | 出現與否 |
      | 價格     | 三萬以內 | 45000 元 | 不出現   |
      | 尺寸     | 寬 200cm 以內 | 寬 240cm | 不出現 |
      | 風格     | 奶油風   | 美式風   | 出現     |
      | 氛圍     | 溫馨     | 俐落     | 出現     |
      | 顏色     | 米白     | 淺灰     | 出現     |
```

```gherkin
Rule: 尺寸未明說時不得臆測

  Scenario: 使用者未提及尺寸
    Given 使用者輸入「奶油風沙發,預算三萬內」
      And 使用者沒有提到任何尺寸限制
    When 系統解析需求
    Then 系統不設定任何尺寸條件
      And 尺寸較大的沙發仍然可以入選
```

### 4. 步驟定義骨架 (Step Definitions)

為每個 Feature 提供步驟定義的實作骨架。

> ⚠️ **本專案尚未建置測試套件**。以下為 **pytest + pytest-bdd** (Python 3.11) 的建議骨架,
> 建立後以 `.venv-rag/bin/python -m pytest tests/` 執行。
> 在建置完成前,可用 `.venv-rag/bin/python rag_pipeline/retriever.py "<需求>"` 手動驗收同一組場景。

```python
# tests/step_defs/test_furniture_retrieval.py
"""家具檢索 BDD 步驟定義骨架(pytest-bdd,尚未建置)。

執行:.venv-rag/bin/python -m pytest tests/step_defs/test_furniture_retrieval.py
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, when, then, parsers, scenarios

scenarios("../features/retrieval/single-item-search.feature")


@pytest.fixture
def ctx() -> dict:
    """場景間共享狀態;每個場景取得全新的 dict,確保場景互相獨立。"""
    return {}


# Given 步驟 —— 設定初始狀態
@given("家具庫中收錄 9,349 件家具")
def furniture_catalog_ready(ctx: dict) -> None:
    # 實作:確認索引已就緒(collection furniture_v3 的筆數符合預期)
    from rag_pipeline.retriever import load_collection

    ctx["catalog_size"] = load_collection().count()
    assert ctx["catalog_size"] == 9349


@given(parsers.parse("使用者輸入「{query}」"))
def user_query(ctx: dict, query: str) -> None:
    # 實作:記下原始需求語句,不在此步驟呼叫解析
    ctx["query"] = query


# When 步驟 —— 執行動作
@when("系統執行檢索")
def run_retrieval(ctx: dict) -> None:
    # 實作:走完整管線(需求解析 → 硬過濾 → 向量 → rerank → 加權 → 去重)
    from rag_pipeline.query_parser import parse_query
    from rag_pipeline.retriever import retrieve

    ctx["parsed"] = parse_query(ctx["query"])
    ctx["result"] = retrieve(ctx["parsed"])


# Then 步驟 —— 驗證結果
@then(parsers.parse("回傳 {count:d} 件候選家具"))
def assert_result_count(ctx: dict, count: int) -> None:
    # 實作:驗證候選件數(不可回傳超過 FINAL_TOP_K)
    items = [i for group in ctx["result"]["items"] for i in group["hits"]]
    assert len(items) == count


@then(parsers.parse("每一件的售價都不超過 {budget:d} 元"))
def assert_within_budget(ctx: dict, budget: int) -> None:
    # 實作:價格是硬條件,任一件超出即失敗
    items = [i for group in ctx["result"]["items"] for i in group["hits"]]
    over = [i["id"] for i in items if i["price_twd"] > budget]
    assert not over, f"超出預算的家具:{over}"


@then("系統請使用者補充條件")
def assert_clarification_requested(ctx: dict) -> None:
    # 實作:條件不足時必須追問,且選項數不超過 4 個
    assert ctx["parsed"]["needs_clarification"] is True
    assert 0 < len(ctx["parsed"]["clarify_options"]) <= 4
```

### 5. 資料驅動測試 (Data-Driven Testing)

```gherkin
Scenario Outline: 多種風格需求的檢索結果
  Given 使用者要配置以下品項
    | 品項     | 件數 | 重要性   |
    | 主沙發   | 1    | 必要     |
    | 邊几     | 2    | 加分     |
  When 使用者指定 <風格描述> 與預算 <預算> 元
  Then 系統判定風格為 <主導風格>
    And 回傳的候選件數為 <候選件數> 件
    And 主沙發分配到的預算約為 <主沙發預算> 元

  Examples: 成功場景
    | 風格描述           | 預算   | 主導風格 | 候選件數 | 主沙發預算 |
    | 奶油風溫馨的客廳   | 100000 | 奶油風   | 8        | 60000      |
    | 日式侘寂感的客廳   | 60000  | 日式風   | 8        | 36000      |
    | loft 那種調調      | 80000  | 工業風   | 8        | 48000      |
    | 北歐風溫馨的客廳   | 100000 | 北歐風   | 8        | 60000      |

  Examples: 失敗場景
    | 風格描述           | 預算   | 主導風格 | 候選件數 | 主沙發預算 |
    | 奶油風的客廳       | 3000   | 奶油風   | 0        | 無         |
    | 沒有提到風格       | 100000 | 待澄清   | 0        | 無         |
```

```gherkin
Scenario Outline: 需求解析的欄位落點
  Given 使用者輸入 <需求語句>
  When 系統解析需求
  Then 房型為 <房型>
    And 風格為 <風格>
    And 預算上限為 <預算上限>
    And 是否需要追問為 <需要追問>

  Examples: 條件充分
    | 需求語句                             | 房型 | 風格   | 預算上限 | 需要追問 |
    | 奶油風沙發,預算三萬內                | 客廳 | 奶油風 | 30000    | 否       |
    | 臥室想弄成 loft 那種調調,牆面深色水泥 | 臥室 | 工業風 | 未指定   | 否       |
    | 餐廳要一張餐桌配四張餐椅,中古世紀現代風 | 餐廳 | 現代簡約 | 未指定 | 否       |

  Examples: 條件不足
    | 需求語句           | 房型   | 風格   | 預算上限 | 需要追問 |
    | 想找便宜一點的椅子 | 未指定 | 未指定 | 未指定   | 是       |
```

## 蘇格拉底檢核

每個場景撰寫完成後,驗證:

1. **是業務語言還是技術實作?**
   - ✅ 業務人員能看懂嗎?
   - ❌ 是否包含"點擊按鈕"、"API調用"等技術細節?
   - ❌ 是否寫了 `where` 條件、`FINAL_TOP_K`、`style_compat` 等實作名詞?

2. **結果是否可觀測、可驗證?**
   - ✅ 能明確判斷成功或失敗嗎?
   - ❌ 是否使用"系統正常"等模糊描述?
   - ❌ 是否寫了「結果看起來很搭」這種無法自動判定的敘述?

3. **場景是否獨立、可重複執行?**
   - ✅ 不依賴其他場景的執行順序?
   - ✅ 可以重複執行N次結果一致?
   - ⚠️ 注意:需求解析由 LLM 產生,同一句話可能有輕微差異 —— 斷言寫「範圍」而非「精確值」

4. **是否涵蓋關鍵邊界與異常?**
   - ✅ 有測試數量為0的情況?
   - ✅ 有測試網路失敗、超時等異常?
   - ✅ 有測試條件過嚴導致命中 0 筆、以及需求過於模糊需追問的情況?

5. **參數化是否充分?**
   - ✅ 使用 Scenario Outline 減少重複?
   - ✅ Examples 覆蓋正常值、邊界值、異常值?
   - ✅ 六種風格是否都至少出現在一組 Examples 中?

## 輸出格式

- 所有 Feature 檔案使用 `.feature` 副檔名
- 檔案命名: `功能模組名稱.feature` (kebab-case)
- 使用中文或英文保持一致,不要混用
- 縮排使用 2 個空格
- 步驟定義一律 Python 3.11 (pytest-bdd),執行方式 `.venv-rag/bin/python -m pytest`
- 涉及風格/房型/類別時,只用中文業務語彙,不寫 `cream` / `living_room` 等內部代碼

## Feature 文件結構範例

```
features/
├── query_parsing/
│   ├── style-extraction.feature
│   ├── budget-and-size.feature
│   └── clarification.feature
├── retrieval/
│   ├── single-item-search.feature
│   ├── room-set-composition.feature
│   └── ranking-and-dedup.feature
├── indexing/
│   ├── full-rebuild.feature
│   └── incremental-update.feature
└── step_defs/
    ├── test_query_parsing.py
    ├── test_furniture_retrieval.py
    └── conftest.py
```

> ⚠️ 上述目錄**尚未建置**;建立時放在專案根的 `tests/` 之下,
> 以 `.venv-rag/bin/python -m pytest tests/` 執行。**本專案無 CI**,測試由開發者本機手動執行。

## 審查清單

- [ ] 所有場景使用業務語彙,無技術實作細節
- [ ] 每個 Then 步驟都可自動驗證
- [ ] 場景涵蓋正常流程、邊界條件、異常流程
- [ ] 使用 Scenario Outline 減少重複場景
- [ ] 提供對應的步驟定義骨架
- [ ] 業務規則清晰且可追溯到 PRD
- [ ] 所有場景可獨立執行,無依賴順序
- [ ] 參數化範例涵蓋典型值、邊界值、無效值
- [ ] 硬條件 (房型/類別/價格/尺寸) 與軟條件 (風格/氛圍) 的差異有專屬場景驗證
- [ ] 有場景驗證「使用者未提尺寸時系統不得臆測尺寸」
- [ ] 步驟定義為 Python 3.11,無 `.venv/`、無其他直譯器或套件管理器
- [ ] 已標明測試套件尚未建置,並提供 CLI 手動驗收替代方案

## 關聯文件

- **需求來源**: 02_project_brief_and_prd.md (PRD) → 本專案對應 `01-prd-product-spec.md`
- **實作依據**: 07_module_specification_and_tests.md (模組規格)
- **測試策略**: 13_security_and_readiness_checklists.md (測試完整性)
- **受控詞彙與 schema**: `docs/query_parser_spec.md`、`vlm_annotation/taxonomy_v2.json`
- **檢索行為規格**: `docs/RAG檢索系統說明.md`、`rag_pipeline/README.md`

---

**記住**: BDD 規格是業務與技術的橋樑,是可執行的文檔,是自動化測試的基礎。好的 BDD 規格讓團隊對"完成"有共同理解。
