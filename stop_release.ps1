#Requires -Version 5.1
<#
.SYNOPSIS
    停止 release 生产服务（与 deploy_release.ps1 配套，放在 release 工作树根目录）。

.DESCRIPTION
    默认停止 8888 端口上的 release 后端进程。

    注意：Windows 下 venv 的 python.exe 是启动器，会再拉起一个基础解释器子进程，
    真正监听端口的是子进程。因此不能只杀 PID 文件里的那一个，必须按
    「命令行包含 quant_server.main + 端口匹配 + 进程链锚定本目录 venv」整组终止。

    查找顺序：
      1) release_server.pid（若仍有效则作为候选之一）
      2) 所有命令行含 `quant_server.main` 且 `--port 8888` 的 python 进程，
         且自身或父进程是本目录 .venv\Scripts\python.exe

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
$VenvPython = (Join-Path $ProjectRoot ".venv\Scripts\python.exe").ToLower()

function Get-ExecutablePath {
    param([int]$ProcessId)
    try {
        return (Get-Process -Id $ProcessId -ErrorAction Stop).Path
    }
    catch {
        return $null
    }
}

function Test-ReleaseCommandLine {
    param([string]$CommandLine)
    if (-not $CommandLine) { return $false }
    if ($CommandLine -notmatch 'quant_server\.main') { return $false }
    if ($CommandLine -notmatch ("--port\s+" + [regex]::Escape([string]$Port) + "(\s|$)")) { return $false }
    return $true
}

$Candidates = @()

# 1) PID 文件作为候选（保持对旧启动方式的兼容）
if (Test-Path $PidFile) {
    $Raw = (Get-Content $PidFile -Raw).Trim()
    if ($Raw -match '^\d+$') {
        $PidFromFile = [int]$Raw
        $Cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$PidFromFile" -ErrorAction SilentlyContinue).CommandLine
        if (Test-ReleaseCommandLine $Cl) {
            $Candidates += [pscustomobject]@{ ProcessId = $PidFromFile; ParentProcessId = 0 }
        }
    }
}

# 2) 全量扫描 python 进程，锚定本目录 venv
$PythonProcesses = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
if ($PythonProcesses) {
    foreach ($Proc in $PythonProcesses) {
        if (-not (Test-ReleaseCommandLine $Proc.CommandLine)) { continue }
        $SelfPath = Get-ExecutablePath $Proc.ProcessId
        $ParentPath = Get-ExecutablePath $Proc.ParentProcessId
        $IsVenv = $SelfPath -and $SelfPath.ToLower() -eq $VenvPython
        $ChildOfVenv = $ParentPath -and $ParentPath.ToLower() -eq $VenvPython
        if ($IsVenv -or $ChildOfVenv) {
            $Candidates += [pscustomobject]@{ ProcessId = $Proc.ProcessId; ParentProcessId = $Proc.ParentProcessId }
        }
    }
}

$TargetIds = $Candidates | ForEach-Object { $_.ProcessId } | Sort-Object -Unique

if (-not $TargetIds) {
    Write-Host "未发现运行中的 release 服务（端口 $Port）"
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    exit 0
}

foreach ($TargetId in $TargetIds) {
    $Proc = Get-Process -Id $TargetId -ErrorAction SilentlyContinue
    if ($Proc) {
        Stop-Process -Id $TargetId -Force -ErrorAction SilentlyContinue
        Write-Host "已终止进程：PID=$TargetId"
    }
}
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

Write-Host "已停止 release 服务：端口=$Port 进程数=$($TargetIds.Count)"
exit 0
