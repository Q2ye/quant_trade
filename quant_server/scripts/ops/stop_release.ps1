<#
.SYNOPSIS
    停止 release 生产服务

.DESCRIPTION
    优先读取 logs\release_server.pid；PID 文件缺失或失效时按监听端口兜底查找。
    只终止路径匹配本目录 venv\Scripts\python.exe 的进程，避免误杀。

.EXAMPLE
    .\stop_release.ps1
    .\stop_release.ps1 -Port 8082 -Root E:\QuantitativeTrading\quant_trade_release\quant_server
#>
[CmdletBinding()]
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$Port = 8082
)

$ErrorActionPreference = "Stop"

$LogDir = Join-Path $Root "logs"
$PidFile = Join-Path $LogDir "release_server.pid"
$ExpectedPython = (Join-Path $Root ".venv\Scripts\python.exe").ToLower()

function Resolve-TargetProcess([int]$ProcessId) {
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $Process) { return $null }
    try {
        $Path = $Process.Path.ToLower()
    } catch {
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
        $Target = Resolve-TargetProcess ([int]$Raw)
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
        $Target = Resolve-TargetProcess ([int]$Connection.OwningProcess)
    }
}

if (-not $Target) {
    Write-Host "未发现运行中的 release 服务（端口 $Port）"
    return
}

Stop-Process -Id $Target.Id -Force
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
Write-Host "已停止 release 服务：PID=$($Target.Id) 端口=$Port"
