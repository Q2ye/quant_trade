#Requires -Version 5.1
<#
.SYNOPSIS
    把 dev 的提交同步到 release 工作树（只做 git 合并，不打包、不重启）。

.DESCRIPTION
    与 deploy_release.ps1 职责分离：部署脚本不再碰 git，避免每次部署都把 dev 的提交带进 release。
    需要更新生产代码时单独运行本脚本：
      1) 校验 release 工作树位于目标分支；有改动先自动提交（-NoAutoCommit 可关闭）
      2) git fetch（可用 -NoFetch 跳过）
      3) git merge --ff-only <SourceBranch>（只允许快进，分叉直接报错）
      4) 把本次变更文件写入 .release-sync-changes，供 deploy_release.ps1 判断是否需要安装依赖

.PARAMETER RepoRoot
    release 工作树根目录，默认脚本所在目录。

.PARAMETER SourceBranch
    源分支，默认 dev。

.PARAMETER TargetBranch
    目标分支，默认 release_v1.0.0。当前分支不符会直接失败。

.PARAMETER Remote
    远程名，默认 origin。

.PARAMETER NoFetch
    跳过 git fetch，只使用本地分支。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File sync_release.ps1

.EXAMPLE
    # 只合并本地 dev，不去连远程
    powershell -NoProfile -ExecutionPolicy Bypass -File sync_release.ps1 -NoFetch
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$SourceBranch = "dev",
    [string]$TargetBranch = "release_v1.0.0",
    [string]$Remote = "origin",
    [switch]$NoFetch,
    [switch]$NoAutoCommit
)

$ErrorActionPreference = "Stop"
$env:GIT_TERMINAL_PROMPT = "0"
$scriptPath = $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Split-Path -Parent $scriptPath)).Path
}
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Marker = Join-Path $RepoRoot ".release-sync-changes"

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

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    Fail "不是 git 工作树: $RepoRoot"
}

$branchNow = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()
if ($branchNow -ne $TargetBranch) {
    Fail "当前分支为 $branchNow，期望 $TargetBranch；请确认 RepoRoot 指向 release 工作树"
}

# 工作树有改动时先自动提交，再合并；-NoAutoCommit 则保持旧的“直接失败”行为
$dirty = @(& git -C $RepoRoot status --porcelain --untracked-files=no)
if ($dirty.Count -gt 0) {
    if ($NoAutoCommit) {
        $dirty | ForEach-Object { Write-Host "    $_" }
        Fail "工作树有未提交改动（已指定 -NoAutoCommit），请先提交或清理后再同步"
    }
    Write-Step ("工作树有 {0} 处改动，先自动提交" -f $dirty.Count)
    $dirty | ForEach-Object { Write-Host "    $_" }
    & git -C $RepoRoot add -u
    if ($LASTEXITCODE -ne 0) { Fail "git add 失败，请手动检查工作树" }
    $autoMsg = "chore(release): 同步前自动提交本机改动 " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    & git -C $RepoRoot commit -m $autoMsg | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "自动提交失败，请手动检查工作树" }
    Write-Step ("已提交: " + $autoMsg)
}

Write-Step "工作树: $RepoRoot（$TargetBranch）"

# ---------------------------------------------------------------- 1. fetch
$fetchOk = $false
if (-not $NoFetch) {
    Write-Step "拉取远程 $Remote"
    $fetchOk = $true
    try {
        # git 把进度写到 stderr；$ErrorActionPreference=Stop 下必须接住，否则会当成异常
        & git -C $RepoRoot fetch $Remote --prune 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { $fetchOk = $false }
    }
    catch { $fetchOk = $false }

    if (-not $fetchOk) { Write-Warn "无法连接远程 $Remote，继续使用本地分支" }
}

# ---------------------------------------------------------------- 2. 源分支
$sourceRef = "refs/heads/$SourceBranch"
& git -C $RepoRoot rev-parse --verify --quiet $sourceRef | Out-Null
if ($LASTEXITCODE -ne 0) {
    $sourceRef = "refs/remotes/$Remote/$SourceBranch"
    & git -C $RepoRoot rev-parse --verify --quiet $sourceRef | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "找不到源分支 $SourceBranch（本地与 $Remote 均不存在）"
    }
    Write-Warn "本地无 $SourceBranch，改用 $Remote/$SourceBranch"
}

# ---------------------------------------------------------------- 3. 合并
$oldHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
& git -C $RepoRoot merge-base --is-ancestor $sourceRef HEAD
if ($LASTEXITCODE -eq 0) {
    Write-Step "已包含 $sourceRef，无需同步（HEAD $($oldHead.Substring(0, 8))）"
    if (Test-Path $Marker) { Remove-Item $Marker -Force }
    exit 0
}

Write-Step "快进合并 $sourceRef"
& git -C $RepoRoot merge --ff-only $sourceRef
if ($LASTEXITCODE -ne 0) {
    # 有本地提交时无法快进，退回普通合并（产生一个 merge commit）
    Write-Warn "无法快进（release 有本地提交），改用普通合并"
    & git -C $RepoRoot merge --no-edit $sourceRef
    if ($LASTEXITCODE -ne 0) {
        & git -C $RepoRoot merge --abort 2>&1 | Out-Null
        Fail "合并 $sourceRef 失败（存在冲突），已回滚本次合并"
    }
}

$newHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
$changed = @(& git -C $RepoRoot diff --name-only $oldHead $newHead)
Set-Content -Path $Marker -Value $changed -Encoding utf8
Write-Step ("已同步 {0} -> {1}，变更 {2} 个文件" -f $oldHead.Substring(0, 8), $newHead.Substring(0, 8), $changed.Count)
Write-Step "下一步：运行 deploy_release.ps1 打包并重启（-NoStart 可只打包）"
exit 0
