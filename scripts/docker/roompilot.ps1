<#
.SYNOPSIS
RoomPilot 容器操作的單一入口。包一層是因為「自足模式」要疊兩個 compose 檔，
每次手打 -f docker-compose.yml -f docker-compose.full-stack.yml 很容易漏。

.EXAMPLE
  # 預設模式：容器跑 app，資料庫連本機那套
  .\scripts\docker\roompilot.ps1 up

.EXAMPLE
  # 自足模式：連資料庫也在容器裡（第一次要先 seed-db 灌資料）
  .\scripts\docker\roompilot.ps1 up -FullStack
  .\scripts\docker\roompilot.ps1 seed-db

.EXAMPLE
  # 把本機 .runtime/ 的上傳圖與登入金鑰搬進容器
  .\scripts\docker\roompilot.ps1 seed-runtime

.EXAMPLE
  # 在容器內跑團隊測試套件
  .\scripts\docker\roompilot.ps1 test
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('up', 'down', 'build', 'logs', 'status', 'shell', 'smoke',
                 'seed-runtime', 'seed-db', 'test')]
    [string]$Command,

    # 疊上 docker-compose.full-stack.yml：連 PostgreSQL 也放進容器。
    [switch]$FullStack,

    # build/up：建出不含家具 RAG 的精簡映像（少約 6GB）。
    [switch]$NoRag,

    # build：不使用 layer 快取。
    [switch]$NoCache,

    # down：連 volume 一起刪。⚠ 專案、帳號、上傳檔全沒。
    [switch]$Volumes
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ProjectName = 'roompilot'
$RuntimeVolume = "${ProjectName}_roompilot-runtime"
$Network = "${ProjectName}_default"
$PgImage = 'pgvector/pgvector:pg17'

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Write-Warn($message) { Write-Host "!!  $message" -ForegroundColor Yellow }

# Docker Desktop 吃得下 Windows 路徑，但反斜線在某些 shell 轉義下會出事，
# 統一換成正斜線最省心。
function To-DockerPath($path) { return ($path -replace '\\', '/') }

function Get-ComposeArgs {
    $files = @('-f', (Join-Path $RepoRoot 'docker-compose.yml'))
    if ($FullStack) {
        $files += @('-f', (Join-Path $RepoRoot 'docker-compose.full-stack.yml'))
    }
    return $files
}

# .env 只在這支腳本裡讀，用來取 DB 連線資訊餵給 pg_dump/pg_restore。
# 不回顯、不寫檔。
function Get-DotEnv {
    $path = Join-Path $RepoRoot '.env'
    if (-not (Test-Path $path)) {
        throw ".env 不存在。先執行：Copy-Item .env.example .env 並填入 DB_PASSWORD"
    }
    $values = @{}
    foreach ($line in Get-Content $path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ($trimmed -eq '' -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) { continue }
        $parts = $trimmed.Split('=', 2)
        $values[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
    }
    return $values
}

function Invoke-Compose {
    param([string[]]$Arguments)
    Push-Location $RepoRoot
    try {
        & docker compose @(Get-ComposeArgs) @Arguments
        if ($LASTEXITCODE -ne 0) { throw "docker compose 失敗（exit $LASTEXITCODE）" }
    } finally {
        Pop-Location
    }
}

switch ($Command) {

    'build' {
        $buildArgs = @('build')
        if ($NoCache) { $buildArgs += '--no-cache' }
        $buildArgs += 'app'
        if ($NoRag) { $env:ROOMPILOT_CONTAINER_WITH_RAG = '0' }
        Write-Step "建置映像（RAG: $(if ($NoRag) { '不含' } else { '含權重' })）"
        Write-Warn "含 RAG 權重的首次建置要下載約 4.5GB 模型，10-30 分鐘不等。"
        Invoke-Compose $buildArgs
    }

    'up' {
        if ($NoRag) { $env:ROOMPILOT_CONTAINER_WITH_RAG = '0' }
        Write-Step "啟動（$(if ($FullStack) { '自足模式：容器內 PostgreSQL' } else { '預設模式：連本機 PostgreSQL' })）"
        Invoke-Compose @('up', '-d', '--build')
        Write-Host ''
        Write-Step '等容器 healthy（RAG 預載要讀 4.5GB 權重，首次約 1-3 分鐘）'
        Write-Host '  查看進度：  .\scripts\docker\roompilot.ps1 status'
        Write-Host '  查看日誌：  .\scripts\docker\roompilot.ps1 logs'
        Write-Host '  開網站：    http://127.0.0.1:8002'
        if ($FullStack) {
            Write-Host ''
            Write-Warn '自足模式第一次啟動時容器資料庫是空的，/api/health 會回 503。'
            Write-Warn '灌資料：  .\scripts\docker\roompilot.ps1 seed-db -FullStack'
        }
    }

    'down' {
        $downArgs = @('down')
        if ($Volumes) {
            Write-Warn 'Volume 一起刪：容器內的專案、帳號、上傳檔與容器資料庫全部消失。'
            $confirm = Read-Host '確定請輸入 DELETE'
            if ($confirm -ne 'DELETE') { Write-Host '已取消。'; break }
            $downArgs += '-v'
        }
        Invoke-Compose $downArgs
    }

    'logs' { Invoke-Compose @('logs', '-f', '--tail', '200', 'app') }

    'shell' { Invoke-Compose @('exec', 'app', 'bash') }

    'status' {
        Write-Step '容器狀態'
        Invoke-Compose @('ps')
        Write-Host ''
        Write-Step '/api/health'
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8002/api/health' -TimeoutSec 10
            $health | ConvertTo-Json -Depth 6
        } catch {
            Write-Warn "健康檢查取不到：$($_.Exception.Message)"
            Write-Warn '容器可能還在載 RAG 權重，或資料庫連不上。看日誌確認。'
        }
    }

    'smoke' {
        # 四個不需要登入的端點，涵蓋「容器到底通到哪一層」。
        # 每一項都印出判讀方式，不要只給 JSON 讓人自己猜。
        $base = 'http://127.0.0.1:8002'
        $failures = 0

        function Probe($name, $path, $explain) {
            Write-Host ''
            Write-Step "$name  ($path)"
            try {
                $r = Invoke-RestMethod -Uri "$base$path" -TimeoutSec 20
                $r | ConvertTo-Json -Depth 5 -Compress | Write-Host
                Write-Host "    判讀：$explain" -ForegroundColor DarkGray
                return $r
            } catch {
                Write-Warn "失敗：$($_.Exception.Message)"
                $script:failures++
                return $null
            }
        }

        $health = Probe '整體健康' '/api/health' `
            'ready=true 且 formal=true 才算正式組態；status=offline 代表退成 JSON/SQLite 了'
        if ($health -and $health.ready -ne $true) {
            Write-Warn 'ready 不是 true —— 資料庫連不上，或 schema 沒匯入。'
            $failures++
        }

        Probe '型錄' '/api/catalog/status' `
            '看 count 是不是 7,958（第 6 步實際可選的有效家具數）' | Out-Null

        $embed = Probe 'RAG 權重預載' '/api/rag/embedding-status' `
            'status=ready 代表 BGE-M3 與 reranker 真的載進記憶體了；loading 是還在載；disabled 是沒開；failed 要看日誌'
        if ($embed -and $embed.status -eq 'failed') {
            Write-Warn "RAG 預載失敗：$($embed.error)"
            $failures++
        }

        Probe '工程報告（第 9 步）' '/api/v1/engineering/health' `
            'xlsx.module_path_configured=true 才會產出 estimate_and_schedule.xlsx' | Out-Null

        Write-Host ''
        if ($failures -eq 0) {
            Write-Host '==> 煙霧測試全過。' -ForegroundColor Green
        } else {
            Write-Warn "$failures 項未過。看日誌：.\scripts\docker\roompilot.ps1 logs"
        }
    }

    'seed-runtime' {
        # 本機 .runtime/ 裡有 auth_secret.key（沒搬過去的話容器會自己生一把，
        # 現有登入全部失效）與 uploads/renders（沒搬的話舊專案的平面圖與成果
        # 圖在容器裡是 404）。專案本體在 PostgreSQL，不在這裡。
        $source = Join-Path $RepoRoot '.runtime'
        if (-not (Test-Path $source)) { throw ".runtime/ 不存在，沒有東西可搬。" }
        Write-Step "把 .runtime/ 複製進 volume $RuntimeVolume"
        Write-Warn '同名檔案會被本機這份覆蓋（包含 auth_secret.key）。'
        $src = To-DockerPath $source
        & docker run --rm `
            -v "${RuntimeVolume}:/dst" `
            -v "${src}:/src:ro" `
            alpine:3 sh -c "cp -a /src/. /dst/ && chown -R 10001:10001 /dst && du -sh /dst"
        if ($LASTEXITCODE -ne 0) { throw "複製失敗（exit $LASTEXITCODE）" }
        Write-Step '完成。重啟容器讓它讀到新的 auth_secret.key：'
        Write-Host '  .\scripts\docker\roompilot.ps1 up'
    }

    'seed-db' {
        # 只有自足模式需要。做兩件事：
        #   1. 用 pgvector 映像連本機 5432 做 pg_dump（不用 host 的 psql，
        #      版本一定對得上，也不必管 PATH）
        #   2. 把 dump 灌進容器裡的 db 服務
        if (-not $FullStack) {
            Write-Warn '未加 -FullStack。seed-db 是給容器內資料庫用的，'
            Write-Warn '預設模式本來就直接讀本機那套，不需要灌。'
            Write-Warn '若你確實要灌容器 DB，請改跑：roompilot.ps1 seed-db -FullStack'
            break
        }
        $envValues = Get-DotEnv
        $dbName = $envValues['DB_NAME']; if (-not $dbName) { $dbName = 'roompilot_db' }
        $dbUser = $envValues['DB_USER']; if (-not $dbUser) { $dbUser = 'postgres' }
        $dbPass = $envValues['DB_PASSWORD']
        if (-not $dbPass) { throw '.env 沒有 DB_PASSWORD。' }

        $exportDir = Join-Path $RepoRoot '.runtime\db-export'
        if (-not (Test-Path $exportDir)) { New-Item -ItemType Directory -Path $exportDir | Out-Null }
        $exportPath = To-DockerPath $exportDir

        Write-Step "從本機 PostgreSQL 匯出 $dbName（約 470MB，壓縮後小得多）"
        # --create 刻意不加：本機 DB 的 collation 是 Windows 專有的
        # 「Chinese (Traditional)_Taiwan.950」，寫進 CREATE DATABASE 會讓
        # Linux 容器 restore 直接失敗。詳見 docker-compose.full-stack.yml。
        & docker run --rm `
            --add-host host.docker.internal:host-gateway `
            -e "PGPASSWORD=$dbPass" `
            -v "${exportPath}:/seed" `
            $PgImage `
            pg_dump -h host.docker.internal -p 5432 -U $dbUser -d $dbName `
                    -Fc --no-owner --no-privileges -f /seed/roompilot_db.dump
        if ($LASTEXITCODE -ne 0) { throw "pg_dump 失敗（exit $LASTEXITCODE）。本機 PostgreSQL 有在跑嗎？" }

        $dumpFile = Join-Path $exportDir 'roompilot_db.dump'
        $sizeMb = [math]::Round((Get-Item $dumpFile).Length / 1MB, 1)
        Write-Step "匯出完成：$dumpFile（$sizeMb MB）"

        Write-Step '確認容器資料庫已啟動'
        Invoke-Compose @('up', '-d', 'db')
        Start-Sleep -Seconds 5

        Write-Step '灌進容器資料庫'
        # --clean --if-exists：可重複執行，第二次跑會先砍掉舊物件再灌。
        & docker run --rm `
            --network $Network `
            -e "PGPASSWORD=$dbPass" `
            -v "${exportPath}:/seed:ro" `
            $PgImage `
            pg_restore -h db -p 5432 -U $dbUser -d $dbName `
                       --clean --if-exists --no-owner --no-privileges -j 4 /seed/roompilot_db.dump
        # pg_restore 對「DROP ... IF EXISTS 找不到東西」會回非零但無害，
        # 所以這裡不 throw，改成把結果交給下一步的實際筆數檢查。
        Write-Step '核對筆數'
        & docker run --rm --network $Network -e "PGPASSWORD=$dbPass" $PgImage `
            psql -h db -U $dbUser -d $dbName -c `
            "select 'furniture_items' t, count(*) from roompilot.furniture_items union all select 'active', count(*) from roompilot.furniture_items where is_active union all select 'embeddings', count(*) from roompilot.furniture_embeddings union all select 'projects', count(*) from roompilot.projects;"
        Write-Step '完成。重啟 app 讓連線池重新連上：'
        Write-Host '  .\scripts\docker\roompilot.ps1 up -FullStack'
    }

    'test' {
        # test stage 多帶 tests/ 與 scripts/，不進正式 runtime 映像。
        Write-Step '建置 test 映像'
        Push-Location $RepoRoot
        try {
            & docker build --target test -t roompilot-app:test .
            if ($LASTEXITCODE -ne 0) { throw "docker build 失敗（exit $LASTEXITCODE）" }
            Write-Step '在容器內跑 pytest'
            $dbHost = if ($FullStack) { 'db' } else { 'host.docker.internal' }
            $networkArgs = if ($FullStack) { @('--network', $Network) } else { @() }
            # 走唯讀掛載、不進映像的大宗資料，測試都要用，這裡要一一補掛：
            #   JSON/          conftest.py:16 把型錄 provider 壓成 json，
            #                  json provider 讀 main.py:150 與 :158 那兩個大檔。
            #   surface_assets test_surface_material_processing 會斷言
            #                  _processed/ 底下 239 個材質貼圖真的存在，
            #                  並實際 GET /static/... 要 200。
            #   style_cards    test_wall_material_candidates 逐張風格卡驗貼圖。
            # 少掛任何一個，紅的會是「素材不存在」而不是真的邏輯錯誤。
            $jsonDir = To-DockerPath (Join-Path $RepoRoot 'JSON')
            $surfaceDir = To-DockerPath (Join-Path $RepoRoot 'frontend\surface_assets')
            $cardsDir = To-DockerPath (Join-Path $RepoRoot 'frontend\style_cards')
            $imagesDir = To-DockerPath (Join-Path $RepoRoot 'frontend\style_images')
            # ROOMPILOT_RUNTIME_DIR 刻意不傳：test stage 已經把它清空，
            # 傳了會讓 test_worktree_uses_the_main_repository_runtime_directory 紅。
            # -p no:cacheprovider：/app 是 root 擁有的，pytest 寫不了 .pytest_cache，
            # 不關掉每次都會多一則 Permission denied 警告。
            & docker run --rm `
                --add-host host.docker.internal:host-gateway `
                @networkArgs `
                --env-file (Join-Path $RepoRoot '.env') `
                -e "DB_HOST=$dbHost" `
                -e 'ROOMPILOT_ARTIFACT_TOOL_MODULES=/opt/artifact-tool' `
                -e 'ROOMPILOT_RAG_MODEL_CACHE=/opt/rag-models' `
                -e 'HF_HUB_CACHE=/opt/rag-models' `
                -v "${jsonDir}:/app/JSON:ro" `
                -v "${surfaceDir}:/app/frontend/surface_assets:ro" `
                -v "${cardsDir}:/app/frontend/style_cards:ro" `
                -v "${imagesDir}:/app/frontend/style_images:ro" `
                roompilot-app:test pytest -q -p no:cacheprovider
        } finally {
            Pop-Location
        }
    }
}
