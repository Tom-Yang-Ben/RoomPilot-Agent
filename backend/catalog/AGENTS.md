# Catalog 與材質資料

Owner：Kai。開始前閱讀 `docs/owners/KAI.md` 與
`docs/contracts/LIGHTING_CEILING_CATALOG_CONTRACT.md`。

- 正式 ID、尺寸、模型 URL 與圖片 URL 只能來自已驗證 catalog 與 manifest。
- 舊風格／RAG JSON 僅供 enrichment，不可覆蓋正式資料。
- 模糊、壞檔、尺寸不合理或授權不明的項目一律留在 quarantine。
- 燈具必須完成 GLB 載入、尺寸、純物件縮圖、類型與授權驗證，才可標示為 `verified`。
- 大型 GLB、原始下載檔與供應商 manifest 不進 Git；full-profile operator 將資產放在自行管理的 object store/CDN，並透過 `.env` 指定含 URL、checksum、授權與分類的外部 manifest。
- `backend/server/static/pbr_assets/` 的已清洗 PBR 紋理是執行期資產，必須提交 Git；不可提交憑證。
- Bella 負責 API／前端呈現；Yen 負責推薦排序；兩者不得直接改寫 catalog。

最低驗證：cloud catalog、delivery、quarantine、material 與 SQL contract 測試。
