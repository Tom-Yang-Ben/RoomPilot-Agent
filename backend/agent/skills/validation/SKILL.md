---
name: 驗證規則/需求
description: 雙軌驗證：硬規則呼叫 engine（違反即擋）；語意軟潛規則與需求滿足度 advisory（僅警告）。
agent: Validation Agent
tools: engine_validate, read_rules, read_layout
---

## 提示詞：summary

你是配置驗證報告撰寫者。根據硬違規、軟警告與需求缺口，
用兩三句繁體中文說明目前方案狀態與建議。不要發明清單以外的問題。

## 輸出 schema：summary

```json
{
  "type": "object",
  "properties": {"summary": {"type": "string"}},
  "required": ["summary"]
}
```

## 流程說明

1. 硬規則軌（deterministic、違反即擋）：`engine_validate` tool 把場景每件
   家具丟回 `backend.engine.clearance.check_placement_with_clearance` 重驗
   碰撞、淨空、超界；LLM 完全不參與。
2. 需求滿足度（deterministic）：每個硬需求對照場景 placed 條目
   （matched_requirements 或同 category），不足即列入 requirement_gaps，
   並帶上擺放失敗原因。
3. 語意軟潛規則（advisory、僅警告）：讀場景結構化摘要做 heuristic 檢查
   ——sofa_faces_tv（朝向內積）、bed_head_against_wall（床頭離牆
   ≤30cm）、rug_anchored（地毯壓在主家具下）。只描述 engine 已算出的
   結果，不做任何合法性判定。
4. 總結敘事：LLM 依「提示詞：summary」產出；不可用時用 deterministic
   模板句。
5. 輸出 `ValidationReportDoc`（passed＝無硬違規且無需求缺口；軟警告
   不擋）；修復建議供 Furniture Agent 的修復迴圈使用（次數由 Master 控制）。
