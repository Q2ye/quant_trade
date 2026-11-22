<#
.SYNOPSIS
    实盘服务器看护脚本（2026-10-08 新增）—— 解决「09-28 类运行缺口」。

.DESCRIPTION
    背景（缺陷事实）：19:20 的「日终数据同步+策略驱动」与 21:00 的「日终结算」**同属一个进程**，
    进程不在则两者**静默消失**，系统侧零告警。2026-09-28（周一，交易日）实测：整日无进程
    → 无同步/无驱动/无结算（`strategy_daily_performance`/`account_daily_performance`/
    `account_statements` 各缺 1 行），直到 09-29 00:46 才被人工拉起。
    国庆期间（10-01~10-07）再次整假期无进程，仅因停机而"侥幸"未触发假日结算缺陷。

    本脚本做两件事（**只读日志 + 必要时拉起进程**，不改任何业务数据）：
      ① 进程存活：按端口探测；不在则拉起服务器（可选），并把事件追加到 `logs/watchdog.log`。
      ② 流水线完整性：若当日日志**已出现** `日终数据同步开始: <今日>` 但到
         `-PipelineDeadline`（默认 20:30）仍**没有** `日终流水线完成: <今日>` → 判定
         「启动了但没跑完」→ 记 WARNING（可接告警通道）。
         ⚠️ 该判定以"日志里有开始标记"为前提 —— 非交易日/进程未启动时**不会**误报。

.USAGE
    # 手动执行（只检查，不拉起）
    powershell -ExecutionPolicy Bypass -File scripts\ops\ensure_server_running.ps1 -NoStart

    # 注册为「开机自启 + 每 30 分钟检查」的计划任务（需管理员 PowerShell 执行一次）
    schtasks /Create /TN "QuantServerWatchdog" /SC MINUTE /MO 30 /RL HIGHEST /F ^
      /TR "powershell -ExecutionPolicy Bypass -File E:\QuantitativeTrading\quant_trade\quant_server\scripts\ops\ensure_server_running.ps1"

    # 仅打印计划任务注册命令（不执行）
    powershell -ExecutionPolicy Bypass -File scripts\ops\ensure_server_running.ps1 -PrintTaskCommand

.NOTES
    ⚠️ 启动命令以**你实际使用的那条**为准（本脚本默认取 CLAUDE.md 记载的形态）。
       若实际用法不同，请用 `-StartCommand` 覆盖，或直接改 `$DefaultStartCommand`。
#>
param(
    [string]$Root = "E:\QuantitativeTrading\quant_trade\quant_server",
    [int]$Port = 8080,
    [string]$StartCommand = "",
    [string]$LogFile = "",
    [datetime]$PipelineDeadline = (Get-Date -Hour 20 -Minute 30 -Second 0),
    [switch]$NoStart,
    [switch]$PrintTaskCommand,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$DefaultStartCommand = "python -m quant_server.main --config config.yaml --mode development --port $Port"

if ([string]::IsNullOrWhiteSpace($LogFile)) { $LogFile = Join-Path $Root "logs\watchdog.log" }
$ServerLog = Join-Path $Root "logs\quant_server.log"
$Today = (Get-Date).ToString("yyyy-MM-dd")

function Write-Watchdog {
    param([string]$Level, [string]$Message)
    $line = "{0} [{1}] {2}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $line
    if (-not $WhatIf) {
        $dir = Split-Path -Parent $LogFile
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Add-Content -Path $LogFile -Value $line -Encoding UTF8
    }
}

function Get-ServerAlive {
    <# 端口探测：服务器监听则不返回空 #>
    try {
        $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return [bool]$c
    } catch {
        # Get-NetTCPConnection 不可用时的兜底（老系统）
        $net = netstat -ano | Select-String ":$Port\s+.*LISTENING"
        return [bool]$net
    }
}

# ---------- ① 进程存活 ----------
$alive = Get-ServerAlive
if ($alive) {
    Write-Watchdog "INFO" "进程存活: 端口 $Port 正在监听"
} else {
    Write-Watchdog "WARN" "进程未运行: 端口 $Port 无监听（19:20 流水线与 21:00 结算将静默消失）"
    if ($NoStart) {
        Write-Watchdog "WARN" "-NoStart 指定，未拉起进程"
    } else {
        $cmd = if ([string]::IsNullOrWhiteSpace($StartCommand)) { $DefaultStartCommand } else { $StartCommand }
        # 允许 "python -m ..." 与 "\.venv\Scripts\python.exe -m ..." 两种写法
        $exe = Join-Path $Root ".venv\Scripts\python.exe"
        if (-not (Test-Path $exe)) { $exe = "python" }
        $argLine = $cmd -replace '^\s*python(\.exe)?\s*', ''
        Write-Watchdog "INFO" "尝试拉起: $exe $argLine"
        if (-not $WhatIf) {
            try {
                Start-Process -FilePath $exe -ArgumentList $argLine -WorkingDirectory $Root `
                    -WindowStyle Hidden `
                    -RedirectStandardOutput (Join-Path $Root "logs\watchdog_stdout.log") `
                    -RedirectStandardError  (Join-Path $Root "logs\watchdog_stderr.log")
                Start-Sleep -Seconds 15
                if (Get-ServerAlive) {
                    Write-Watchdog "INFO" "拉起成功: 端口 $Port 已监听"
                } else {
                    Write-Watchdog "ERROR" "拉起失败: 15 秒后端口仍无监听（请人工检查启动命令/依赖）"
                }
            } catch {
                Write-Watchdog "ERROR" "拉起异常: $($_.Exception.Message)"
            }
        }
    }
}

# ---------- ② 流水线完整性 ----------
if (Test-Path $ServerLog) {
    $startedMarker   = "日终数据同步开始: $Today"
    $finishedMarker  = "日终流水线完成: $Today"
    $tail = Get-Content -Path $ServerLog -Tail 4000 -ErrorAction SilentlyContinue
    $hasStart    = [bool]($tail | Select-String -SimpleMatch $startedMarker)
    $hasFinished = [bool]($tail | Select-String -SimpleMatch $finishedMarker)

    if ($hasStart -and -not $hasFinished) {
        if ((Get-Date) -ge $PipelineDeadline) {
            Write-Watchdog "ERROR" "流水线未完成: 已出现「$startedMarker」但超过 $($PipelineDeadline.ToString('HH:mm')) 仍无「$finishedMarker」（请查数据门/同步耗时）"
        } else {
            Write-Watchdog "INFO" "流水线进行中（尚未到 $($PipelineDeadline.ToString('HH:mm')) deadline）"
        }
    } elseif ($hasFinished) {
        Write-Watchdog "INFO" "当日流水线已完成"
    } else {
        Write-Watchdog "INFO" "当日尚无流水线记录（非交易日或尚未到 19:20）"
    }
} else {
    Write-Watchdog "WARN" "未找到日志文件: $ServerLog"
}

# ---------- ③ 打印计划任务注册命令 ----------
if ($PrintTaskCommand) {
    $self = $MyInvocation.MyCommand.Path
    $tr = "powershell -ExecutionPolicy Bypass -File `"$self`""
    Write-Host ""
    Write-Host "注册计划任务（管理员 PowerShell 执行一次）:" -ForegroundColor Cyan
    Write-Host "  schtasks /Create /TN `"QuantServerWatchdog`" /SC MINUTE /MO 30 /RL HIGHEST /F /TR `"$tr`""
    Write-Host "  # 开机自启（登录时也触发一次）:"
    Write-Host "  schtasks /Create /TN `"QuantServerBoot`" /SC ONSTART /RL HIGHEST /F /TR `"$tr`""
}
