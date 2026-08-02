# 最大平行執行

最大模式以環境實際 concurrency 為上限；目前常見為 root integrator 加最多三個
subagents。平行的目標是縮短獨立工作，不是增加同檔衝突或繞過 owner。

## Wave 0：Root preflight

- 主 agent 親自讀完所有適用的 skill/AGENTS/owner/contracts。
- 執行 `git status --short` 並列出禁止碰觸的 dirty files。
- 鎖定問題、輸入、輸出、單位、schema、保存邊界、producer/consumer、測試。
- 建立 packet，標記 read-only 或 writer，以及 shared-file owner。

## Wave 1：平行唯讀分析

依任務拆成最多三條互補路徑，例如：

1. Domain/owner/current implementation。
2. API/data contract/persistence/producer-consumer。
3. Tests/frontend/deployment/security/documentation。

每個代理回報來源檔案、行為證據、風險、建議範圍與未解問題。唯讀 wave 不得
搶先寫 contract 或改 code。

## Wave 2A：穩定共享契約

- Root 或指定 contract owner 單一寫入 ADR/schema/contract。
- 明定欄位、型別、單位、版本、default、錯誤、保存與 migration。
- Producer/consumer 都確認後才進入寫入 wave。
- 無法穩定時停止並向使用者或 owner 要求決策。

## Wave 2B：平行實作

可行 packets：

- Producer domain + 該 owner tests。
- Consumer adapter/API + API/contract tests。
- Frontend/docs/QA + 不重疊的 browser/static checks。

不可平行：

- 兩個代理修改同一檔案或同一 shared fixture。
- Producer/consumer 同時猜測未定 schema。
- 多代理修改 `AGENTS.md`、README、同一 `docs/contracts/*` 或本 skill 核心。
- 子代理 commit/push、修改 `.env`/certs/runtime/cache/模型/大資產。
- 代理跨 owner 臨時重寫不屬於 packet 的演算法。

## Work packet 格式

```text
Packet ID：
主要 owner／協作 owner：
目標與非目標：
允許修改的精確檔案：
禁止碰觸的檔案：
輸入／輸出：
契約、schema、單位、保存邊界：
上游／下游依賴：
最低驗證：
完成回報：changed files、tests、contract impact、risks
```

每個寫入 packet 必須有唯一檔案集合。若代理發現需要 shared 或未授權檔案，先停下
回報，不可自行擴張。

## Wave 3：平行驗證

可分成：

1. Domain/producer tests。
2. API/contract/consumer/integration tests。
3. Static frontend/browser/docs/security checks。

把失敗路由回原 packet owner。不要因整合失敗就在另一 owner 目錄加入 workaround。

## Wave 4：Root integration

- 讀取完整 diff，而不是只信 agent 摘要。
- 檢查 owner、contract、fallback、秘密、runtime、大資產與 unrelated changes。
- 跑必要的跨模組與完整測試、`git diff --check`、`git status --short`。
- 交付 changed、verified、not verified、existing failures、remaining risk。

## 衝突處理

- 同檔需求：改為 root single-writer 或串行。
- Contract 衝突：停止實作，回 Wave 2A。
- Dirty worktree 衝突：保留使用者內容；能繞過就縮小 patch，不能繞過就詢問。
- 權限/approval/credentials：視為明確 stop condition，不嘗試繞過。
