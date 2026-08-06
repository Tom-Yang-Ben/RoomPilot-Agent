# @oai/artifact-tool 本機相容層

真品 `@oai/artifact-tool` 是私有套件（公開 npm 404，所有遠端分支皆無），
只存在部分成員機器上。這個目錄提供一個以 [exceljs] 實作的本機相容層，
覆蓋 `backend/server/engineering/workbook_builder.mjs` 實際使用的 API 子集，
builder 本體一行不改。`tests/test_engineering_documents_api.py` 的 XLSX
斷言已明示接受兩種 writer（內容契約不綁序列化實作）。

## 新機器安裝

```powershell
cd tools\artifact_tool_local
npm ci   # 只裝 exceljs
```

`.env` 加上（或填實）：

```text
ROOMPILOT_ARTIFACT_TOOL_MODULES=<repo 絕對路徑>\tools\artifact_tool_local
ROOMPILOT_ARTIFACT_NODE=node
```

重啟 FastAPI 後 `/api/v1/engineering/health` 的
`xlsx.module_path_configured` 應為 `true`，工程文件生成即含
`estimate_and_schedule.xlsx`（四張表：工程估價、初步排程、家具採購、設計語彙）。

## 驗證

```powershell
$env:ROOMPILOT_ARTIFACT_TOOL_MODULES="<repo 絕對路徑>\tools\artifact_tool_local"
.\.venv\Scripts\python.exe -m pytest -q tests\test_engineering_documents_api.py
```

`test_demo_e2e_generates_html_json_and_four_sheet_artifact_xlsx` 不再 skip
且通過，即代表相容層可用。

## 已知限制

- `workbook.render()`（表格 PNG 預覽）與 `workbook.inspect()` 未實作，會明話
  拋錯——這兩個 API 只在 `--preview-dir` / `--inspect-path` 旗標下使用，
  DocumentService 的正式生成路徑不會碰到。要用預覽功能請安裝真品。
- 只實作 builder 用到的 format 屬性；builder 新增用法時相容層會拋
  `unsupported format key`，不會無聲吞掉。

[exceljs]: https://www.npmjs.com/package/exceljs
