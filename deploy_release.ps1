#Requires -Version 5.1
<#
.SYNOPSIS
    release 环境部署：依赖检查 → 前端打包 → 重启后端 → 健康校验（不拉取代码）。

.DESCRIPTION
    默认在 release 工作树（E:\QuantitativeTrading\quant_trade_release）上执行：
      0) 读取 sync_release.ps1 留下的 .release-sync-changes，判断本次同步改了什么
      1) lockfile / pyproject.toml 有变动时自动安装依赖
      2) pnpm run build:release 生成压缩后的前端 dist
      3) 停止并重新拉起后端（优先计划任务 QuantTradeRelease，其次直接调用 start_release.ps1）
      4) 轮询 /health/live 并打印首页加载的 JS 产物

    更新代码请单独运行 sync_release.ps1，本脚本不执行任何 git 命令。

.PARAMETER RepoRoot
    release 工作树根目录，默认脚本所在目录。

.PARAMETER Branch
    期望所在分支（仅校验用），默认 release_v1.0.0。

.PARAMETER Port
    后端端口，默认 8888。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File deploy_release.ps1

.EXAMPLE
    # 只重打包并重启（代码已由 sync_release.ps1 同步）
    powershell -NoProfile -ExecutionPolicy Bypass -File deploy_release.ps1
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Branch = "release_v1.0.0",
    [int]$Port = 8888,
    [switch]$SkipInstall,
    [switch]$SkipBuild,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$env:GIT_TERMINAL_PROMPT = "0"
$scriptPath = $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Split-Path -Parent $scriptPath)).Path
}
$RepoRoot = (Resolve-Path $RepoRoot).Path
$ServerDir = Join-Path $RepoRoot "quant_server"
$WebDir = Join-Path $RepoRoot "quant_web"
$Py = Join-Path $ServerDir ".venv\Scripts\python.exe"
$LogFile = Join-Path $ServerDir "logs\quant_server.log"

function Write-Step([string]$Message) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message) -ForegroundColor Cyan
}
function Write-Warn([string]$Message) {
    Write-Host ("[{0}] 警告: {1}" -f (Get-Date -Format "HH:mm:ss"), $Message) -ForegroundColor Yellow
}
function Fail([string]$Message) {
    Write-Host ("[{0}] 失败: {1}" -f (Get-Date -Format "HH:mm:ss"), $Message) -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $ServerDir)) { Fail "找不到 quant_server 目录: $ServerDir" }
if (-not (Test-Path $Py)) { Fail "找不到 release 虚拟环境: $Py" }

$Pnpm = "D:\apps\node\pnpm.cmd"
if (-not (Test-Path $Pnpm)) {
    $cmd = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    if (-not $cmd) { Fail "找不到 pnpm.cmd，请先安装 pnpm 或在脚本里指定路径" }
    $Pnpm = $cmd.Source
}

Write-Step "工作树: $RepoRoot"
$branchNow = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()
if ($branchNow -ne $Branch) {
    Write-Warn "当前分支为 $branchNow（期望 $Branch），继续执行，请自行确认"
}

$newHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
Write-Step ("当前提交: " + $newHead.Substring(0, 8) + "（代码同步请用 sync_release.ps1）")

# 变更清单由 sync_release.ps1 写入，部署脚本只消费不写 git
$marker = Join-Path $RepoRoot ".release-sync-changes"
$changed = @()
if (Test-Path $marker) {
    $changed = @(Get-Content $marker -Encoding utf8 | Where-Object { $_ -ne "" })
    Remove-Item $marker -Force
    Write-Step ("上次同步更新 {0} 个文件" -f $changed.Count)
}

# ---------------------------------------------------------------- 1. 依赖
if (-not $SkipInstall) {
    if ($changed -match "^quant_web/(pnpm-lock\.yaml|package\.json)$") {
        Write-Step "前端依赖有变动，执行 pnpm install --frozen-lockfile"
        Push-Location $WebDir
        & $Pnpm install --frozen-lockfile
        $code = $LASTEXITCODE
        Pop-Location
        if ($code -ne 0) { Fail "前端依赖安装失败" }
    }
    if ($changed -match "^quant_server/pyproject\.toml$") {
        Write-Step "后端依赖声明有变动，执行 pip install -e"
        & $Py -m pip install -e $ServerDir
        if ($LASTEXITCODE -ne 0) { Fail "后端依赖安装失败" }
    }
}

# ---------------------------------------------------------------- 2. 打包
if (-not $SkipBuild) {
    Write-Step "打包前端（vite build --target esnext --minify terser）"
    Push-Location $WebDir
    & $Pnpm run build:release
    $buildCode = $LASTEXITCODE
    Pop-Location
    if ($buildCode -ne 0) { Fail "前端打包失败" }
    if (-not (Test-Path (Join-Path $WebDir "dist\index.html"))) { Fail "打包完成但 dist\index.html 不存在" }
}
else {
    Write-Step "已指定 -SkipBuild，跳过打包"
}

if ($NoStart) {
    Write-Step "已指定 -NoStart，部署完成（未重启服务）"
    exit 0
}

# ---------------------------------------------------------------- 3. 重启
$stopScript = Join-Path $RepoRoot "stop_release.ps1"
$startScript = Join-Path $ServerDir "scripts\ops\start_release.ps1"
if (Test-Path $stopScript) {
    Write-Step "停止现有后端"
    # venv 的 python.exe 是启动器，真正的监听进程是其子进程；必须用根目录的按进程树停止脚本
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stopScript -RepoRoot $RepoRoot -Port $Port | Out-Null
}

Write-Step "启动后端（端口 $Port）"
$taskName = "QuantTradeRelease"
schtasks /Query /TN $taskName 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    # 上一实例若仍处于 Running，/Run 会被静默忽略；先 End 再等状态回落
    schtasks /End /TN $taskName 2>$null | Out-Null
    for ($i = 0; $i -lt 20; $i++) {
        $state = (schtasks /Query /TN $taskName /FO CSV /NH 2>$null) -join " "
        if ($state -notmatch "Running|正在运行") { break }
        Start-Sleep -Milliseconds 500
    }
    schtasks /Run /TN $taskName | Out-Null

    # 确认进程真的起来了（venv 启动器与子进程都会命中），否则回退为直接启动
    $started = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        $proc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -match 'quant_server\.main' -and
                $_.CommandLine -match ("--port\s+" + $Port + "(\s|$)")
            } |
            Select-Object -First 1
        if ($proc) { $started = $true; break }
    }
    if (-not $started) {
        Write-Warning "计划任务未拉起进程，回退为直接启动"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $startScript -Root $ServerDir -NoWait | Out-Null
    }
}
elseif (Test-Path $startScript) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $startScript -Root $ServerDir -NoWait | Out-Null
}
else {
    Fail "既没有计划任务 $taskName，也没有 start_release.ps1"
}

# ---------------------------------------------------------------- 4. 校验
Write-Step "等待健康检查"
$healthy = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        $resp = Invoke-WebRequest "http://127.0.0.1:$Port/health/live" -UseBasicParsing -TimeoutSec 3
        if ($resp.StatusCode -eq 200) { $healthy = $true; break }
    }
    catch { }
    Start-Sleep -Seconds 2
}
if (-not $healthy) { Fail "90 秒内 /health/live 未返回 200，请查看 $LogFile" }

$rootResp = Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 10
$asset = ""
$m = [regex]::Match($rootResp.Content, "assets/index-[^`"]+\.js")
if ($m.Success) { $asset = $m.Value }

Write-Step "健康检查通过: /health/live = 200, / = $($rootResp.StatusCode), 资源 = $asset"
if (Test-Path $LogFile) {
    $dbLine = Get-Content $LogFile -Encoding utf8 -Tail 400 | Select-String "使用.*数据库配置" | Select-Object -Last 1
    if ($dbLine) { Write-Step ("数据库: " + $dbLine.Line.Trim()) }
}
Write-Step "部署完成。访问 http://127.0.0.1:$Port"
exit 0
