# RoomPilot local development installer (Windows / PowerShell).
param(
    [switch]$Full,
    [switch]$WithRag,
    [switch]$WithOcr,
    [switch]$WithDelivery
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw '找不到 uv；請先安裝：https://docs.astral.sh/uv/'
}

$extras = @('--extra', 'portable')
if ($Full) { $extras += @('--extra', 'postgres') }
if ($WithRag) { $extras += @('--extra', 'rag') }
if ($WithOcr) { $extras += @('--extra', 'ocr') }
if ($WithDelivery) { $extras += @('--extra', 'delivery') }

& uv sync @extras --group dev
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }

if ($WithDelivery) {
    & uv run playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Playwright Chromium install failed' }
}

if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Write-Host "`n完成。預設 portable profile 啟動指令：" -ForegroundColor Green
Write-Host '  uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload'
if ($Full) {
    Write-Host '已安裝 full profile；請在 .env 設 ROOMPILOT_PROFILE=full 並提供自己的資料庫。'
}
