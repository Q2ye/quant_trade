<#
.SYNOPSIS
    release 生产服务启动脚本（单端口：前端静态资源 + API + WebSocket）

.DESCRIPTION
    - 强制 ENVIRONMENT=production：数据库连接由进程环境变量决定（PROD_DB_* → quant_signals），
      仅传 --mode production 不会切换数据库，两者必须同时设置。
    - --mode production：关闭 /docs，并按 config.yaml 的 system.serve_frontend=null 自动托管 quant_web/dist。
    - 默认端口 8082，避免与 dev（后端 8080 / 前端 8081）冲突。

.EXAMPLE
    .\start_release.ps1
    .\start_release.ps1 -Port 8082 -Root E:\QuantitativeTrading\quant_trade_release\quant_server
#>
[CmdletBinding()]
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$Port = 8082,
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$LogDir = Join-Path $Root "logs"
$PidFile = Join-Path $LogDir "release_server.pid"
$ProjectRoot = Split-Path $Root -Parent

if (-not (Test-Path $Python)) {
    throw "未找到 release 虚拟环境：$Python（请先创建 venv 并执行 pip install -e .）"
}

$DistIndex = Join-Path $ProjectRoot "quant_web\dist\index.html"
if (-not (Test-Path $DistIndex)) {
    throw "未找到前端构建产物：$DistIndex（请先在 quant_web 下执行 pnpm build）"
}

$Existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($Existing) {
    throw "端口 $Port 已被 PID $($Existing.OwningProcess) 占用"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# 关键：--mode 决定日志/docs/前端托管；ENVIRONMENT 决定数据库（PROD_DB_* → quant_signals）
$env:ENVIRONMENT = "production"

# editable 安装只映射 api/core/modules/shared 等子包，不含 quant_server 包本身；
# 工作目录是 $Root（quant_server），需把项目根加入 PYTHONPATH 才能 `-m quant_server.main`
$env:PYTHONPATH = $ProjectRoot

$StdOut = Join-Path $LogDir "release_stdout.log"
$StdErr = Join-Path $LogDir "release_stderr.log"
$ArgumentList = @(
    "-m", "quant_server.main",
    "--config", "config.yaml",
    "--mode", "production",
    "--port", "$Port"
)

$Process = Start-Process -FilePath $Python -ArgumentList $ArgumentList `
    -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $StdOut -RedirectStandardError $StdErr

$Process.Id | Set-Content -Path $PidFile -Encoding ascii
Write-Host "release 服务启动中：PID=$($Process.Id) 端口=$Port"
Write-Host "标准输出：$StdOut"
Write-Host "标准错误：$StdErr"

if ($NoWait) { return }

$Deadline = (Get-Date).AddSeconds(90)
$Healthy = $false
while ((Get-Date) -lt $Deadline) {
    Start-Sleep -Seconds 2
    if ($Process.HasExited) {
        throw "进程已退出（exit=$($Process.ExitCode)），请查看 $StdErr"
    }
    try {
        $Response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health/live" `
            -UseBasicParsing -TimeoutSec 3
        if ($Response.StatusCode -eq 200) {
            $Healthy = $true
            break
        }
    } catch {
        # 启动期内连接失败属正常，继续等待
    }
}

if (-not $Healthy) {
    throw "90 秒内健康检查未通过（http://127.0.0.1:$Port/health/live），请查看 $StdErr"
}

Write-Host "健康检查通过：http://127.0.0.1:$Port/health/live"
Write-Host "前端入口：    http://127.0.0.1:$Port/"
