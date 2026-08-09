# React 3D Prototype

> ⚠️ **次要原型，非正式產品。請勿在這裡實作或移植第 5–8 步。**
>
> - 正式八步流程由 FastAPI `GET /scene` 回傳 `backend/server/static/scene.html`，
>   載入 `backend/server/static/scene_v2.js`（香草 JS + Three.js）。**這份 `frontend/`
>   永遠不會被 `/scene` 服務**（`vite build` 產物落在 `backend/server/static/frontend3d/`，
>   只在你手動開 `/static/frontend3d/index.html` 或跑 `npm run dev` 時才會載到）。
> - 本原型只涵蓋約第 1–6 步，**沒有第 7 步視角鎖定與第 8 步生圖／成果包**。
>   第 5–8 步的權威實作只有 `backend/server/static/scene_v2.js` 一份。
> - 尚未移入 `deprecated/`：依 `YEN_BELLA_INTEGRATION_GUIDE.md` §0.5／§7，端對端
>   （含三房手測）驗收通過前不得搬移或刪除重複前端；清理須另開 PR。

Owner: Bella. Prototype collaborator: Ancai. Read `docs/owners/BELLA.md` and
`docs/owners/ANCAI.md`.

This is a secondary React/R3F prototype. The production workflow is
`backend/server/static/`.

- Do not implement a competing project workflow or persistence layer.
- Share contracts, not copied business logic.
- Keep `package-lock.json` synchronized with `package.json`.
- A production migration requires an explicit plan and Bella approval.

Verification: `npm ci` followed by `npm run build`.

