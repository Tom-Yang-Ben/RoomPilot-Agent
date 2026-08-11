# RoomPilot 一鍵安裝所有依賴（Windows / PowerShell）
#
# 用法（pip，預設）：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
# 用法（uv，較快）：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uv
#
# 選項（預設全裝）：
#   -Uv           用 uv 建 venv 並安裝（需先裝 uv）；不帶則用內建 pip
#   -SkipOCR      跳過 PaddleOCR（paddleocr/paddlepaddle 體積大且平台相依）
#   -SkipFrontend 跳過 frontend/ 的 npm 依賴（次要 React 原型，需已裝 Node）
#
# 涵蓋：requirements.txt（server/vision/catalog/RAG/tests）＋ OCR ＋ 交付 PDF
#      （playwright/pikepdf）＋ Playwright Chromium ＋ frontend npm。
# 不含：RAG 模型快取（約 9 GB，需要時另跑 scripts/rag/prefetch_models.py --download）。

param(
    [switch]$Uv,
    [switch]$SkipOCR,
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$py = ".\.venv\Scripts\python.exe"

# uv 與 pip 共用的安裝入口：uv pip install / python -m pip install
function Install-Reqs {
    param([string[]]$ReqArgs)
    if ($Uv) { & uv pip install --python $py @ReqArgs }
    else     { & $py -m pip install @ReqArgs }
}

# 0) -Uv 需要 uv 可用
if ($Uv -and -not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "找不到 uv，請先安裝（pip install uv）或拿掉 -Uv 改用內建 pip。"
}

# 1) 建立 venv（若不存在）
if (-not (Test-Path $py)) {
    if ($Uv) {
        Write-Host "==> uv 建立 .venv (Python 3.12)" -ForegroundColor Cyan
        & uv venv --python 3.12 .venv
    } else {
        Write-Host "==> 建立 .venv (Python 3.12)" -ForegroundColor Cyan
        py -3.12 -m venv .venv
        Write-Host "==> 升級 pip" -ForegroundColor Cyan
        & $py -m pip install --upgrade pip
    }
}

# 2) Python 依賴（requirements-ocr.txt 內含 -r requirements.txt）
if ($SkipOCR) {
    Write-Host "==> 安裝基線依賴（跳過 OCR）" -ForegroundColor Cyan
    Install-Reqs @('-r', 'requirements.txt')
} else {
    Write-Host "==> 安裝基線 + OCR 依賴" -ForegroundColor Cyan
    Install-Reqs @('-r', 'requirements-ocr.txt')
}

# 3) 交付提案 PDF 依賴 + Chromium 瀏覽器
Write-Host "==> 安裝交付 PDF 依賴（playwright / pikepdf）" -ForegroundColor Cyan
Install-Reqs @('-r', 'requirements-delivery.txt')
Write-Host "==> 下載 Playwright Chromium" -ForegroundColor Cyan
& .\.venv\Scripts\playwright.exe install chromium

# 4) 前端 npm 依賴（次要原型）
if (-not $SkipFrontend) {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host "==> 安裝 frontend/ npm 依賴" -ForegroundColor Cyan
        npm --prefix frontend install
    } else {
        Write-Host "!! 找不到 npm，跳過前端依賴（如需 3D 原型請先裝 Node.js）" -ForegroundColor Yellow
    }
}

Write-Host "`n完成。啟動後端：" -ForegroundColor Green
Write-Host "  $py -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload"
