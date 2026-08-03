#!/usr/bin/env bash
# RoomPilot 資安自我稽核 (self-verify engine)
#
# 用途：對 backend/ 靜態掃描 RoomPilot 已知風險型態與新增回歸。
# 這是 roompilot-security skill 的「自我確認」層 —— 每次動到 backend/server、
# postgres_catalog、render/cloud service 或新增端點後執行。
#
# 設計原則：
#   - 只讀、零副作用；不改任何檔案。
#   - 對 RoomPilot 實際程式碼型態調校（非泛用 linter）。
#   - 輸出 PASS / WARN / FAIL；WARN 需人工判讀，FAIL 應阻擋提交。
#   - 退出碼：0=無 FAIL；1=有 FAIL。WARN 不改變退出碼。
#
# 用法：
#   bash .claude/skills/roompilot-security/audit.sh            # 掃描已追蹤 + 工作區
#   bash .claude/skills/roompilot-security/audit.sh --staged   # 只掃 git staged 差異

set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 2
BACKEND="backend"

STAGED_ONLY=0
[ "${1:-}" = "--staged" ] && STAGED_ONLY=1

FAIL=0
WARN=0

c_red=$'\033[31m'; c_yel=$'\033[33m'; c_grn=$'\033[32m'; c_dim=$'\033[2m'; c_off=$'\033[0m'

hdr()  { printf '\n%s── %s ──%s\n' "$c_dim" "$1" "$c_off"; }
pass() { printf '%s  PASS%s  %s\n' "$c_grn" "$c_off" "$1"; }
warn() { printf '%s  WARN%s  %s\n' "$c_yel" "$c_off" "$1"; WARN=$((WARN+1)); }
fail() { printf '%s  FAIL%s  %s\n' "$c_red" "$c_off" "$1"; FAIL=$((FAIL+1)); }

# grep helper：回傳命中的 file:line，排除測試與本腳本
scan() {
  # $1 = pattern (ERE)
  if [ "$STAGED_ONLY" -eq 1 ]; then
    git diff --cached --unified=0 -- "$BACKEND" 2>/dev/null \
      | grep -E '^\+' | grep -vE '^\+\+\+' | grep -nE "$1"
  else
    grep -rnE "$1" "$BACKEND" --include='*.py' 2>/dev/null \
      | grep -vE '/tests?/|_test\.py|test_'
  fi
}

echo "RoomPilot Security Self-Audit  (root: $ROOT)"
[ "$STAGED_ONLY" -eq 1 ] && echo "mode: staged diff only"

# ── A03 Injection：新增的 f-string / 字串拼接 SQL ──────────────────
# 已知基線：postgres_catalog.py 用 hardcoded view 名（安全）。任何把
# 請求參數帶進 f-string SQL 的新寫法都是回歸，必須 FAIL。
hdr "A03 · SQL 組裝"
sqli=$(scan 'execute\(\s*f["'"'"']' | grep -vE '_VIEW|furniture_catalog_current')
if [ -n "$sqli" ]; then
  fail "偵測到含變數插值的 f-string SQL（非 hardcoded view）："
  echo "$sqli" | sed 's/^/        /'
  echo "        → 改用參數化查詢 cursor.execute(sql, (params,))"
else
  pass "無新增的動態 f-string SQL（既有 _VIEW 為 hardcoded，安全）"
fi

# ── A10 SSRF：urllib/httpx/requests 對外抓取無 scheme 驗證 ─────────
# 已知基線：main.py:_remote_glb_response 用 urllib.urlopen(catalog url) 無
# allowlist；urllib 支援 file://、ftp:// 會造成 LFI/SSRF。
hdr "A10 · 外部抓取 (SSRF/LFI)"
ssrf=$(scan 'urllib\.request\.urlopen|requests\.(get|post)\(|client\.(get|post)\(')
if [ -n "$ssrf" ]; then
  warn "有外部抓取呼叫，逐一確認 URL 來源與 scheme allowlist（僅允許 https）："
  echo "$ssrf" | sed 's/^/        /'
  echo "        → 見 references/remediation.md「SSRF/LFI 防護」；urllib 會解析 file://"
else
  pass "無外部抓取呼叫"
fi

# ── 危險反序列化 / 程式碼執行 ─────────────────────────────────────
hdr "A08 · 反序列化 / 程式碼執行"
# 排除方法呼叫 .eval()/.exec()（如 PyTorch model.eval()）——那不是內建 eval/exec。
danger=$(scan '(pickle\.loads|yaml\.load\s*\(|(^|[^.[:alnum:]_])(eval|exec)\(|os\.system|subprocess\.(call|run|Popen)|__import__)' \
  | grep -vE '\.(eval|exec)\(')
if [ -n "$danger" ]; then
  fail "偵測到危險呼叫（RoomPilot 基線為零，任何命中皆須人工核可）："
  echo "$danger" | sed 's/^/        /'
else
  pass "無 pickle/eval/exec/os.system/subprocess（維持零基線）"
fi

# ── A02 硬編碼秘密 ────────────────────────────────────────────────
hdr "A02 · 硬編碼秘密"
secrets=$(scan '(api[_-]?key|password|secret|token|bearer)\s*[=:]\s*["'"'"'][A-Za-z0-9_\-]{16,}' \
  | grep -viE 'getenv|environ|os\.getenv|value\(|\.get\(|default|example|Bearer \{|f"Bearer')
if [ -n "$secrets" ]; then
  fail "疑似硬編碼秘密（應改讀 os.getenv / .env）："
  echo "$secrets" | sed 's/^/        /'
else
  pass "未偵測到硬編碼秘密（憑證皆由 env / .env 讀取）"
fi

# ── A05 DB 傳輸加密：sslmode 預設 disable ─────────────────────────
hdr "A05 · DB 傳輸設定"
if grep -qE 'DB_SSLMODE".*"disable"' "$BACKEND/server/postgres_catalog.py" 2>/dev/null; then
  warn "postgres_catalog.py DB_SSLMODE 預設 'disable'（明文連線）。"
  echo "        → 生產環境 .env 應設 DB_SSLMODE=require；見 references/remediation.md"
else
  pass "DB_SSLMODE 未預設為 disable"
fi

# ── A01/A07 端點認證：新增 @app.<method> 是否掛授權依賴 ────────────
# 已知基線：所有 /api/projects/{project_id} 端點無 auth（CRITICAL）。
# 這裡偵測「新增端點」是否至少引入 Depends（授權骨架）。
hdr "A01/A07 · 端點授權"
routes=$(scan '@(app|router)\.(get|post|put|delete|patch)\(')
has_dep=$(scan 'Depends\(')
if [ -n "$routes" ]; then
  n=$(echo "$routes" | grep -c .)
  if [ -z "$has_dep" ]; then
    warn "偵測到 $n 個路由定義，但 backend 內無任何 Depends() 授權依賴。"
    echo "        → RoomPilot 目前全端點公開（IDOR）。新端點請掛 require_project_access 依賴。"
    echo "        → 見 references/remediation.md「端點授權與 IDOR」"
  else
    pass "路由存在且已使用 Depends()（逐一確認涵蓋敏感操作）"
  fi
else
  pass "本次無新增路由"
fi

# ── A09 資訊洩漏：把例外訊息 / traceback 直接回給 client ──────────
hdr "A09 · 錯誤資訊洩漏"
leak=$(scan 'detail\s*=\s*str\(|detail\s*=\s*f["'"'"'][^"'"'"']*\{(exc|err|error)|traceback\.format')
if [ -n "$leak" ]; then
  warn "端點 detail 可能夾帶原始例外文字，確認不洩漏內部路徑/堆疊："
  echo "$leak" | sed 's/^/        /'
else
  pass "未偵測到把原始例外/traceback 塞入回應 detail"
fi

# ── 秘密外洩到 git：.env 是否被 staged / 追蹤 ─────────────────────
hdr "秘密外洩防線"
tracked_env=$(git ls-files | grep -E '(^|/)\.env$' || true)
staged_env=$(git diff --cached --name-only 2>/dev/null | grep -E '(^|/)\.env$' || true)
if [ -n "$tracked_env" ] || [ -n "$staged_env" ]; then
  fail "偵測到 .env 被 git 追蹤/暫存：${tracked_env}${staged_env}"
  echo "        → git rm --cached；確認 .gitignore 覆蓋；輪換已暴露秘密"
else
  pass ".env 未被追蹤/暫存"
fi

# ── 死設定：宣告但未使用的敏感 env（如 admin token）───────────────
hdr "設定衛生"
if grep -q 'ROOMPILOT_CATALOG_ADMIN_TOKEN' .env.example 2>/dev/null \
   && [ -z "$(grep -rn 'ROOMPILOT_CATALOG_ADMIN_TOKEN' "$BACKEND" 2>/dev/null)" ]; then
  warn "ROOMPILOT_CATALOG_ADMIN_TOKEN 宣告於 .env.example 但 backend 未強制。"
  echo "        → 若為 admin 端點守門，確認實際有驗證；否則移除死設定避免誤導。"
else
  pass "無偵測到宣告即未使用的敏感 admin token"
fi

# ── 總結 ─────────────────────────────────────────────────────────
printf '\n%s────────────────────────────────────────%s\n' "$c_dim" "$c_off"
printf '結果： %sFAIL=%d%s  %sWARN=%d%s\n' \
  "$([ "$FAIL" -gt 0 ] && echo "$c_red" || echo "$c_grn")" "$FAIL" "$c_off" \
  "$([ "$WARN" -gt 0 ] && echo "$c_yel" || echo "$c_grn")" "$WARN" "$c_off"
echo "FAIL 應在提交前修復；WARN 逐項判讀後於 PR 說明處置。"

[ "$FAIL" -gt 0 ] && exit 1
exit 0
