"""磁碟路徑的單一來源。

正式前端在磁碟上的位置只由這個模組決定。後端與測試一律 import，不要各自用
`parents[n]` 往上數再拼 `"backend" / "server" / "static"`。

之所以要收斂：這串路徑原本散在 80 幾處，其中三處寫成相對於工作目錄的
`Path("backend/server/static")`，只有從 repo 根目錄執行才會通過；其餘各自
往上數層數，目錄一搬就會靜默解析到不存在的路徑——那正是
`tests/test_floorplan2room_paths.py` 記載過的失效模式。

`STATIC_DIR` 之後會指向 repo 根目錄的 `frontend/`；那次搬家只需要改這裡一行。
掛載前綴 `/static` 與磁碟位置無關，不會跟著變，所以常數名稱不必再改。
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
SERVER_DIR = BACKEND_DIR / "server"

# 正式前端；由 backend/server/main.py 掛載到 /static。
STATIC_DIR = SERVER_DIR / "static"
