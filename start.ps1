# =============================================================================
# 智扫通 · 一键启动（Windows PowerShell）
# -----------------------------------------------------------------------------
# 用法：
#   .\start.ps1            启动后端(8010) + 前端(5173)，并自动打开浏览器
#   .\start.ps1 -Backend   只启动后端
#   .\start.ps1 -Frontend  只启动前端
#   .\start.ps1 -Stop      停止两个服务
#
# 说明：
#   - 后端运行在 127.0.0.1:8010（FastAPI 适配层，只读调用原有 Agent）
#   - 前端运行在 127.0.0.1:5173（Vite dev server，已代理 /api 到后端）
#   - 两个服务各自在独立窗口中运行，关闭窗口即停止
# =============================================================================

[CmdletBinding()]
param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$WebDir = Join-Path $Root 'web'
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'

$BackendPort = 8010
$FrontendPort = 5173

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "    $msg" -ForegroundColor Yellow }

# ---------------------------------------------------------------------------
# 停止服务
# ---------------------------------------------------------------------------
function Stop-Services {
    foreach ($port in @($BackendPort, $FrontendPort)) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            try {
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop
                Write-Ok "已停止端口 $port 上的进程 (PID $($c.OwningProcess))"
            } catch {
                Write-Warn2 "无法停止端口 $port 上的进程：$($_.Exception.Message)"
            }
        }
    }
}

if ($Stop) {
    Write-Step '停止服务'
    Stop-Services
    exit 0
}

# ---------------------------------------------------------------------------
# 环境检查
# ---------------------------------------------------------------------------
Write-Step '检查运行环境'

if (-not (Test-Path $VenvPython)) {
    Write-Host "找不到 Python 虚拟环境：$VenvPython" -ForegroundColor Red
    Write-Host '请先执行：' -ForegroundColor Yellow
    Write-Host '  uv venv --python 3.13 .venv' -ForegroundColor Yellow
    Write-Host '  uv pip install --python .venv\Scripts\python.exe -r requirements-api.txt' -ForegroundColor Yellow
    exit 1
}
Write-Ok "Python: $VenvPython"

if (-not (Test-Path (Join-Path $WebDir 'node_modules'))) {
    Write-Host '前端依赖未安装，请先执行：' -ForegroundColor Red
    Write-Host '  cd web; npm install' -ForegroundColor Yellow
    exit 1
}
Write-Ok '前端依赖已就绪'

# 端口占用提示
foreach ($port in @($BackendPort, $FrontendPort)) {
    $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
        Write-Warn2 "端口 $port 已被占用 (PID $($busy[0].OwningProcess))，将先尝试复用/释放"
    }
}

$runBackend = $Backend -or (-not $Frontend)
$runFrontend = $Frontend -or (-not $Backend)

# ---------------------------------------------------------------------------
# 启动后端
# ---------------------------------------------------------------------------
if ($runBackend) {
    Write-Step "启动后端 (127.0.0.1:$BackendPort)"
    Start-Process -FilePath $VenvPython `
        -ArgumentList @('-m', 'uvicorn', 'zsapi.app:app', '--host', '127.0.0.1', '--port', "$BackendPort") `
        -WorkingDirectory $Root `
        -WindowStyle Minimized
    Write-Ok '后端已启动（首次构建 Agent 约需 10-15 秒）'
}

# ---------------------------------------------------------------------------
# 启动前端
# ---------------------------------------------------------------------------
if ($runFrontend) {
    Write-Step "启动前端 (127.0.0.1:$FrontendPort)"
    Start-Process -FilePath 'cmd.exe' `
        -ArgumentList @('/c', 'npm run dev') `
        -WorkingDirectory $WebDir `
        -WindowStyle Minimized
    Write-Ok '前端已启动'
}

# ---------------------------------------------------------------------------
# 等待就绪
# ---------------------------------------------------------------------------
if ($runBackend) {
    Write-Step '等待后端就绪'
    $ready = $false
    for ($i = 1; $i -le 40; $i++) {
        Start-Sleep -Seconds 1
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 5
            if ($r.ok) {
                Write-Ok "后端就绪 (agent=$($r.agent.ok), ollama=$($r.ollama.ok), chroma=$($r.chroma.ok))"
                $ready = $true
                break
            }
            Write-Warn2 "依赖未全部就绪 (agent=$($r.agent.ok), ollama=$($r.ollama.ok), chroma=$($r.chroma.ok))"
        } catch {
            Write-Host "    等待中… ($i/40)" -ForegroundColor DarkGray
        }
    }
    if (-not $ready) {
        Write-Warn2 '后端未在 40 秒内就绪，请查看 logs/ 目录下的日志'
    }
}

if ($runFrontend) {
    Write-Step '等待前端就绪'
    $ready = $false
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            $null = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/" -TimeoutSec 3 -UseBasicParsing
            Write-Ok '前端就绪'
            $ready = $true
            break
        } catch {
            Write-Host "    等待中… ($i/30)" -ForegroundColor DarkGray
        }
    }
    if (-not $ready) { Write-Warn2 '前端未在 30 秒内就绪' }
}

# ---------------------------------------------------------------------------
# 打开浏览器
# ---------------------------------------------------------------------------
if ($runFrontend) {
    Write-Step '打开浏览器'
    Start-Process "http://127.0.0.1:$FrontendPort/"
    Write-Ok "http://127.0.0.1:$FrontendPort/"
}

Write-Host ''
Write-Host '智扫通已启动' -ForegroundColor Green
Write-Host "  前端  http://127.0.0.1:$FrontendPort/" -ForegroundColor Gray
Write-Host "  后端  http://127.0.0.1:$BackendPort/docs" -ForegroundColor Gray
Write-Host "  停止  .\start.ps1 -Stop" -ForegroundColor Gray
