# 03 BDD 驗收規格：［功能名稱］

## 追溯資料

| 項目 | 內容 |
|---|---|
| 主要 owner／協作 owner | ［owner］／［owner］ |
| PRD／Story | ［文件與 ID］ |
| 正式契約 | ［`docs/contracts/...`］ |
| 影響輸入／輸出 | ［資料格式、schema version、單位］ |

## 行為邊界

- 前置狀態：［project、layout、questionnaire、catalog、scene 狀態］
- 使用者動作：［用業務語言描述，不綁 CSS selector］
- 可觀察結果：［API、保存狀態、UI、reason code］
- 不可發生：［owner 越界、靜默 fallback、資料遺失］

## Feature

```gherkin
Feature: ［功能名稱］
  Background:
    Given ［共用專案狀態］

  @happy-path
  Scenario: ［正常流程］
    Given ［輸入與版本］
    When ［觸發行為］
    Then ［可觀察輸出］
    And ［保存或 UI 結果］

  @sad-path
  Scenario: ［領域或外部依賴失敗］
    Given ［失敗條件］
    When ［觸發行為］
    Then ［明確錯誤／reason code／HTTP 狀態］
    And ［舊資料保持方式］

  @edge-case @reload
  Scenario Outline: ［邊界與專案恢復］
    Given ［schema／revision／單位］為 "<input>"
    When ［操作或 reload］
    Then ［結果］為 "<result>"

    Examples:
      | input | result |
      | ［值］ | ［預期］ |
```

## 契約與保存 Gate

- [ ] `layout_json` 與 `scene_json` 沒有混用。
- [ ] `_cm`／`_m2`、`coordinate_unit: "cm"` 與 schema version 已在情境中覆蓋。
- [ ] RAG 建議不能推翻 Engine 的碰撞／淨空／合法性結果。
- [ ] PostgreSQL 503、revision 409、inactive/quarantine 排除等適用失敗行為已有情境。
- [ ] reload 後逐房選擇、延後家具與既有方案的預期狀態已定義。

## 測試對照

| Scenario | 測試層級 | Producer／Consumer | 測試檔／指令 |
|---|---|---|---|
| ［名稱］ | ［unit/API/contract/browser］ | ［owner］ | ［命令］ |

