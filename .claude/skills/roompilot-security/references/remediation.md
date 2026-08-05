# RoomPilot 修補範式

本技術棧（FastAPI + urllib/httpx + psycopg2 + Three.js static）的可貼上安全程式碼。
每段對應 SKILL.md「已知風險基線」的 R#。修補時取最小差異，改完跑 `audit.sh` + 對應 pytest。

> 尊重 owner：`backend/server/` 屬 Bella，`postgres_catalog`/SQL 屬 Kai。跨 owner 依 AGENTS.md 記錄。

---

## R1 · 端點授權與 IDOR 防護（A01/A07，CRITICAL）

現況：`/api/projects/{project_id}/*` 全公開，任何人帶別人的 UUID 即可讀寫。UUID 不可枚舉只是「難猜」，不是授權。

漸進式導入（不破壞現有 demo）：先建可插拔的授權依賴，預設從 env 開關，逐端點掛上。

```python
# backend/server/security.py（新檔，Bella owner）
import hmac, os
from fastapi import Depends, Header, HTTPException, status

def _auth_enabled() -> bool:
    return os.getenv("ROOMPILOT_AUTH_ENABLED", "0") == "1"

async def require_api_token(authorization: str = Header(default="")) -> None:
    """最小 bearer token 閘門。生產啟用；demo 預設關閉以免破壞流程。"""
    if not _auth_enabled():
        return
    expected = os.getenv("ROOMPILOT_API_TOKEN", "")
    prefix = "Bearer "
    got = authorization[len(prefix):] if authorization.startswith(prefix) else ""
    # 定時比較，避免 timing side-channel
    if not expected or not hmac.compare_digest(got, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少或無效的授權憑證。")

async def require_project_access(
    project_id: str,
    _: None = Depends(require_api_token),
) -> str:
    """授權骨架：token 通過後再驗證此 caller 對 project_id 的存取權。
    RoomPilot 目前無使用者模型；接上後在此比對 owner，關掉 IDOR。"""
    return project_id
```

掛到端點（main.py）：

```python
from backend.server.security import require_project_access

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str = Depends(require_project_access)):
    ...
```

測試（A01/A07）：

```python
def test_project_requires_token(monkeypatch, client):
    monkeypatch.setenv("ROOMPILOT_AUTH_ENABLED", "1")
    monkeypatch.setenv("ROOMPILOT_API_TOKEN", "secret")
    assert client.get("/api/projects/abc").status_code == 401
    ok = client.get("/api/projects/abc", headers={"Authorization": "Bearer secret"})
    assert ok.status_code in (200, 404)  # 授權過，非 401
```

---

## R2 · SSRF / LFI 防護（A10，HIGH）

現況：`_remote_glb_response`（main.py:1019）`urllib.request.urlopen(model_url)`，URL 來自 catalog，**無 scheme 驗證**。`urllib` 會解析 `file://` → 讀本機檔（LFI）、`http://169.254.169.254` → 雲端 metadata（SSRF）。

在抓取前加守門，只允許 https 且解析後非內網位址：

```python
# backend/server/net_guard.py（新檔）
import ipaddress, socket
from urllib.parse import urlparse
from fastapi import HTTPException

_ALLOWED_SCHEMES = {"https"}

def assert_safe_fetch_url(url: str) -> str:
    """擋掉 file/ftp、內網與保留位址。抓取外部 GLB/圖片前呼叫。"""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(400, "只允許 https 來源。")
    host = parsed.hostname
    if not host:
        raise HTTPException(400, "URL 缺少主機。")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise HTTPException(502, "無法解析遠端主機。")
    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(400, "拒絕存取內網/保留位址。")
    return url
```

修補 `_remote_glb_response`：

```python
def _remote_glb_response(url: str) -> Response:
    assert_safe_fetch_url(url)          # ← 新增
    request = urllib.request.Request(url, headers={...})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read(MAX_REMOTE_GLB_BYTES + 1)   # ← 加讀取上限
    if len(payload) > MAX_REMOTE_GLB_BYTES:
        raise HTTPException(502, "遠端模型過大。")
    ...
```

同樣守門套用到 `intake_service.py:143`（OpenRouter 為固定 host，可白名單 host）與任何未來新增的抓取。注意 DNS rebinding：對高風險路徑可在解析後直接用 IP 連線。

---

## R3 · DB sslmode 與憑證衛生（A02/A05，HIGH，Kai owner）

現況：`postgres_catalog.py:96` `"sslmode": value("DB_SSLMODE", "disable")` → 預設明文。

- 生產 `.env` 設 `DB_SSLMODE=require`（或 `verify-full` + CA）。
- 本機 dev 可留 `disable`，但**預設值**改為安全側，讓遺漏設定時 fail-safe：

```python
# 與 Kai 確認後：預設改 require，dev 顯式覆寫
"sslmode": value("DB_SSLMODE", "require"),
```

- `f"SELECT ... FROM {_VIEW}"`（line 215）目前 `_VIEW` 為 hardcoded，安全。**鐵律**：任何 WHERE/欄位若未來需帶請求參數，一律 `cursor.execute(sql, (param,))`，絕不 f-string 拼接。`audit.sh` 會抓這個回歸。

---

## R4 · Rate limiting 與安全標頭（A04，MEDIUM）

上傳、OCR、LLM、RAG 端點昂貴且無限流。用 slowapi（需加入 requirements）：

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def _rl(request, exc):
    return JSONResponse({"detail": "請求過於頻繁。"}, status_code=429)

@app.post("/api/floorplan/analyze")
@limiter.limit("10/minute")            # 昂貴的 OCR/影像
async def analyze(...): ...
```

安全回應標頭（middleware）：

```python
@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp
```

CORS：目前無 CORSMiddleware（同源，安全）。若前後端分離部署，明確列 origin，**不要** `allow_origins=["*"]` 搭 credentials。

---

## R5 · 安全錯誤處理（A09，MEDIUM）

現況：main.py:1031 `detail=f"遠端 GLB 讀取失敗：{exc}"` 把原始例外回給 client，可能洩漏內部 URL/路徑。

```python
import logging
log = logging.getLogger("roompilot")

except (urllib.error.URLError, TimeoutError, OSError) as exc:
    log.warning("remote glb fetch failed: %s", exc)       # 詳記在 server
    raise HTTPException(502, "遠端模型讀取失敗。") from exc  # generic 給 client
```

原則：client 拿到分類訊息，內部細節（例外、堆疊、SQL、路徑）只進 server log。全域補一個 handler 兜底未預期例外，回 500 generic。

---

## R6 · 生產環境關閉 API 文件（A05，MEDIUM）

無 auth 下 `/docs`、`/openapi.json` 把 49 條端點攤開給攻擊者。用 env 控制：

```python
_PROD = os.getenv("ROOMPILOT_ENV", "dev") == "prod"
app = FastAPI(
    title="AI 室內風格與家具配置展示系統",
    docs_url=None if _PROD else "/docs",
    redoc_url=None if _PROD else "/redoc",
    openapi_url=None if _PROD else "/openapi.json",
)
```

---

## R7 · 死設定 / admin token（A05，待確認）

`ROOMPILOT_CATALOG_ADMIN_TOKEN` 在 `.env.example` 宣告，但 `backend/` 無讀取點。二擇一：
- 若確實有 catalog 管理端點（可能在 `scripts/` 或 Kai 的 catalog 模組），確認有實際比對 token 才放行。
- 若無人使用，移除該 env 宣告，避免給人「已有防護」的錯覺。

---

## 信任邊界⑤ · LLM prompt injection 與輸出信任

`intake_service`、`scene_service` 把使用者需求送 OpenRouter/OpenAI。守則：

- **輸出不可信**：LLM 回傳的 JSON 一律 schema 驗證後才用；**絕不**把回傳當程式碼 eval/exec，也不拿去組路徑或 SQL。
- **幾何合法性只由 `backend/engine/` 判定**（AGENTS.md 鐵律）——LLM 不決定碰撞/淨空，天然縮小 injection 影響面。
- 送出 payload 前確認未夾帶秘密；OpenRouter host 固定，可 host allowlist。
- 家電（冰箱/洗衣機）僅為問卷與生圖上下文，不得因 LLM 輸出就進入 2D/3D 自動配置或家具 API。

---

## 修補後驗證

```bash
bash .claude/skills/roompilot-security/audit.sh   # 目標 FAIL=0，處理過的 WARN 消失
python -m pytest -q                                # 對應模組 + 新增授權/驗證測試綠燈
git diff --check
```

新依賴（slowapi 等）記得寫入 `requirements.txt` 並提交 lock（`uv.lock`），跑一次相依安全檢查。
