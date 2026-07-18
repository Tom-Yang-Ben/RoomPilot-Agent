# TDD Seams 與驗收

## Seam 1：流程狀態

公開介面：`createWorkflow`／`restoreWorkflow` 與 `/scene` 九個逐步 panel。

- 圖面未確認時不能進入聊天。
- 完成資料保存 `project_id`、`schemaVersion=1`、目前步驟與步驟資料。
- 可回上一步；重新整理能恢復已生成場景；使用者可明確 reset。

## Seam 2：智慧材質

公開介面：`generateMaterialSchemes`／`applyMaterialScheme`／`restoreOriginalMaterials`。

- 從現有資料產生 A／B／C 三案，選定後才套用。
- fabric、wood、metal、glass、stone 只接受相容屬性；unknown 保留原始材質。
- 圖片 texture 載入失敗時沿用色碼或 GLB 原材質，不阻斷場景。
- 套用前後 `position_cm` 與 `rotation_y_deg` 必須 byte-for-byte 相同。

## Seam 3：三模式 Viewer

公開介面：`VIEW_MODES` 與 viewer `setViewMode(mode)`。

- walk：Perspective + first-person movement + 完整牆。
- topdown：Orthographic + pan/zoom + 壓平牆。
- orbit：Perspective + OrbitControls + 完整牆。
- 三模式只切相機、controller、牆面顯示；共用同一 scene graph。

## Seam 4：交付 E2E

公開介面：`buildDeliveryManifest` 與 `/scene` 交付按鈕。

- 路徑：圖面 → 確認 → 聊天 → 家具 → 材質 → 審查 → BOM → 交付。
- 靜態 PNG、GLB、確認 DXF、列印／另存 PDF 都有使用者操作入口。
- BOM 只加總已知價格，其他列為待估價。
- `usesGenerativeImageApi` 固定為 `false`。
