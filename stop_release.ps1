#Requires -Version 5.1
<#
.SYNOPSIS
    停止 release 生产服务（与 deploy_release.ps1 配套，放在 release 工作树根目录）。

.DESCRIPTION
    默认停止 8888 端口上的 release 后端进程：
      1) 优先读取 quant_server\logs\release_server.pid
      2) PID 失效时按监听端口查找
      3) 只终止 quant_server\.venv\Scripts\python.exe 启动的进程，避免误杀开发环境（8080）

    停止后等待端口释放，并清理失效的 PID 文件。

.PARAMETER RepoRoot
    release 工作树根目录，默认脚本所在目录。

.PARAMETER Port
    后端端口，默认 8888。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File stop_release.ps1

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File stop_release.ps1 -Port 8888 -RepoRoot E:\QuantitativeTrading\quant_trade_release
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,
    [int]$Port = 8888
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    if ($PSScriptRoot) { $RepoRoot = $PSScriptRoot }
    else { $RepoRoot = (Get-Location).Path }
}
$RepoRoot = (Resolve-Path $RepoRoot).Path.TrimEnd('\')

$ProjectRoot = Join-Path $RepoRoot "quant_server"
$LogDir = Join-Path $ProjectRoot "logs"
$PidFile = Join-Path $LogDir "release_server.pid"
$ExpectedPython = (Join-Path $ProjectRoot ".venv\Scripts\python.exe").ToLower()

function Get-ReleaseProcess {
    param([int]$ProcessId)

    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $Process) { return $null }
    try {
        $Path = $Process.Path.ToLower()
    }
    catch {
        return $null
    }
    if ($Path -ne $ExpectedPython) {
        Write-Warning "PID $ProcessId 的可执行文件不是 $ExpectedPython，已跳过"
        return $null
    }
    return $Process
}

$Target = $null

if (Test-Path $PidFile) {
    $Raw = (Get-Content $PidFile -Raw).Trim()
    if ($Raw -match '^\d+$') {
        $Target = Get-ReleaseProcess ([int]$Raw)
    }
    if (-not $Target) {
        Write-Warning "PID 文件失效：$PidFile"
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

if (-not $Target) {
    $Connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($Connection) {
        $Target = Get-ReleaseProcess ([int]$Connection.OwningProcess)
    }
}

if (-not $Target) {
    Write-Host "未发现运行中的 release 服务（端口 $Port）"
    exit 0
}

$ProcessId = $Target.Id
Stop-Process -Id $ProcessId -Force
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue

$Deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $Deadline) {
    $Still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $Still) { break }
    Start-Sleep -Milliseconds 300
}

$Left = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($Left) {
    Write-Warning "端口 $Port 仍被占用（PID=$($Left.OwningProcess)），请手动检查"
    exit 1
}

Write-Host "已停止 release 服务：PID=$ProcessId 端口=$Port"
exit 0
