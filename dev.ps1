# 本機開發伺服器一鍵啟動：.\dev.ps1
# 換 port：.\dev.ps1 8023
param([int]$Port = 8002)
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn backend.server.main:app --host 127.0.0.1 --port $Port --reload
