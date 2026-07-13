# Git 安全規則

**目的**:保護七人共用 repo——`main` 受保護、`ben` 是整合分支、多條個人分支並行(`ancai-dev`/`rule`/`kai-dev` 勿動;bella 搬資料不搬殼,正本見 `docs/01_專題進度/` SSOT 與 CLAUDE.md)。

**觸發條件**:任何 git 寫入操作(add/commit/merge/switch/stash…)之前。

**具體行為**:
1. 動手前先 `git status` + `git branch --show-current`,確認在預期分支、看清楚未提交的修改是誰的。
2. 使用者未提交的修改一律視為要保留:需要切分支先問或 stash,不得讓它消失。
3. commit 前逐檔確認 staged 清單;`git add` 用明確路徑,不用 `git add .`(除非剛看過完整 status)。
4. 合併他人分支:先 `git log target..source` 與 `diff --stat` 盤點並回報,再動手;衝突涉及他人模組時列出選項讓人裁決。
5. 逐條檢查**入倉三規則**(正本=根目錄 CLAUDE.md 的 Conventions 節,以該處為準,此處不複述);另不提交 `.DS_Store`、`.pyc`、未經組長同意的大檔。

**禁止行為(未經使用者明確要求,一律不得執行;使用者貼上 `TASK_TEMPLATES.md` 範本 4 的分支整合交辦,即視為對該次 merge 的明確要求——但 push 仍需另外指示)**:
- `git push`(任何形式,含 `-u`)
- `git merge` / `git rebase` 進共用分支
- `git reset --hard`、`git clean`(任何參數)
- `git checkout -- .` / `git restore .` 等會丟棄工作區修改的指令
- 改寫歷史(`commit --amend` 已推送的提交、`filter-branch`)
- 刪除分支

**驗收證據**:每次 git 寫入操作前的訊息裡看得到 status/branch 確認;commit 訊息如實描述內容;敏感操作有使用者的明確指示可回溯。
