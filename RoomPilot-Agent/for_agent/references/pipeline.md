# 管線編排細節

補充 SKILL.md 未展開的部分:驗證迴圈控制、兩種執行方式、錯誤處理。

## 驗證迴圈(Agent 3 ↔ Agent 4)的控制邏輯

```
iteration = 0
MAX_ITER = 5
loop:
    report = run validate_layout.py(furniture, architecture, rules, requirement)
    report.iteration = iteration
    if report.passed:
        break  →  進入 build_glb_scene.py
    if iteration >= MAX_ITER:
        report.escalate = true
        停止，把剩餘違規回報使用者          # 絕不無限迴圈
        break
    # 渲一張套疊違規的俯視圖給 Agent 4 做空間定位(多模態才需要;純文字可略過)
    plan_png    = run render_plan.py(architecture, furniture, report)   # 違規物件紅框標示
    instructions = Agent 4(report, plan_png, furniture, architecture, rules, requirement)
    furniture   = Agent 3(furniture, instructions, plan_png)   # 只動被點名物件
    iteration  += 1
```

### 防止震盪 / 死迴圈
- **卡住偵測**:若「同一 `object_id` + 同一 `rule_id`」連續兩輪出現,代表在此空間放不下。
  Agent 4 應把該物件指令從 `move` 升級為 `replace`(換更小候選)或 `remove`,而非再叫原地微移。
- **留餘裕**:Agent 3 執行 `move` 時位移量要 > `min_delta_cm`(建議 1.5–2 倍),避免剛好壓線又被退。
- **只改點名物件**:Agent 3 重排時保持其餘家具不動,防止「修好一個、弄壞三個」的連鎖。
- **升級出口**:達 `MAX_ITER` 仍失敗 → 標 `escalate: true`,交使用者決定放寬規則 / 換家具 /
  接受部分 warning。error 級不可接受,warning 級可視情況放行(由使用者拍板)。

## 兩種執行方式

這個 skill 的內容(4 個 agent 提示 + schema + 腳本)與框架無關,可用兩種方式落地。

### A. 當成 Claude Agent Skill(Claude Code / Agent SDK)
把整個資料夾當技能載入。Claude 讀 SKILL.md 後依步驟:自己扮演各 agent(讀對應
`agents/*.md` 當系統提示)、用 bash 跑 `scripts/*.py`、把中間 JSON 存檔再傳給下一步。
資料庫查詢工具以 MCP 或函式工具形式提供給 Agent 2。適合快速原型與互動式設計。

### B. 拆進你自己的後端(任何框架)
把 `agents/*.md` 當成 4 個獨立 LLM 呼叫的 system prompt,`schemas/*.json` 當輸出格式約束
(或用 structured output / function calling 綁定),`scripts/*.py` 當後端服務。前後端負責:
- 上傳 DXF、呼叫 `parse_dxf.py`;
- 依序呼叫四個 agent,中間狀態存 DB 或物件儲存;
- 驗證迴圈在後端用一個 while 迴圈控制(如上 pseudo-code);
- 最後呼叫 `build_glb_scene.py` 產生 `scene.glb` 回傳前端 three.js / model-viewer 顯示。
每個 agent 呼叫務必**只帶該步需要的輸入**,避免 context 膨脹、也讓各步可獨立重跑。

## 錯誤處理與冪等
- 每個中間產物都落檔(`requirement.json`、`architecture.json`…),任一步失敗可從該步重跑,
  不必從頭跑整條管線。
- 腳本都吃檔案路徑、吐檔案路徑,無隱藏狀態,天然冪等。
- Agent 輸出務必先用對應 schema 驗證(`jsonschema`)再往下傳;格式錯就重試該 agent,
  不要讓壞 JSON 汙染後續步驟。
- `glb_path` 在布置階段只是字串;到 `build_glb_scene.py` 才會實際讀檔。若某 GLB 缺檔,
  腳本會以佔位方塊(依 dimensions)替代並在 log 警告,不中斷整體輸出。

## 規則與需求的分工提醒
- `rule.json` = **空間/物理硬規則**(重疊、走道、牆界、門開合),與風格無關,通常整站共用一份。
- `requirement.json` 的 constraints = **本次使用者的偏好**(要/不要哪類家具)。
- 兩者都由 `validate_layout.py` 檢查,但違規報告用 `type` 區分(`rule` / `requirement`),
  讓 Agent 4 用不同策略處理:硬規則多半靠移位/旋轉解;需求違規靠移除/新增品項解。
