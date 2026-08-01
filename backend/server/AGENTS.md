# Server and Production UI

Owner: Bella. Read `docs/owners/BELLA.md`.

- This is the only production FastAPI app and web frontend.
- Adapt owner modules; do not copy their algorithms into `main.py` or JS.
- Persist backward-compatible project state and version schema changes.
- `layout_json` is recognition output; `scene_json` is proposal output.
- Any static JS/CSS change requires focused tests, content-hash updates, and
  real browser verification.
- Cross-folder changes must name the producer owner and test both boundaries.

## 家具擺放合法性：不要在這裡新增規則（2026-08-01 Ancai 與 Bella 邊界）

「這個位置合不合法」的定義**只能有一份**，在 `backend/engine/`。
本目錄目前仍持有四條引擎看不到的合法性規則，是歷史遺留，**正在逐步收回**：

| 位置 | 規則 | 狀態 |
|---|---|---|
| `scene_service.py` `window_clearance_zones` | 窗前 70cm 禁放帶 | 待引擎「落地窗留距」完成後移除 |
| `scene_service.py` `_OVERLAY_TYPES` | 地毯可壓在其他家具上 | 待引擎「堆疊層」完成後移除 |
| `scene_service.py` `_IGNORE_COLLISION_TYPES` | 壁架完全跳過碰撞 | 同上 |
| `scene_service.py` `_shrunk_boundary` | 全房內縮 8cm | 保留；引擎以 `margin_cm` 參數接收，數字仍由本層決定 |

**新增任何一條「某某情況下不准擺／可以重疊／要留幾公分」之前，先問 Ancai。**
規則若留在本層，引擎會回報「合法」而畫面卻擋下來，兩邊永遠對不起來，
而且引擎那側的測試抓不到——這正是先前多次「改了引擎卻沒效果」的原因。

擺放策略層（貼牆、朝向、成組）已於 2026-08-01 接線：
`generate_layout()` 先問 `backend/engine/layout_strategy.py`，失敗才走本檔既有的
`_placement_candidates`。環境變數 `ROOMPILOT_LAYOUT_STRATEGY=0` 可整個關掉。
完整分層地圖見 `backend/engine/notes/engine參考手冊.md` §9。

Minimum tests: API/contract tests for the feature plus full `pytest -q`.

