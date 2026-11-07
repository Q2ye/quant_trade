@echo off
chcp 65001 >nul
setlocal
rem Double-click entry for sync_release.ps1 (merge dev into release worktree).
rem Any arguments are forwarded, e.g. sync.cmd -NoFetch
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync_release.ps1" -RepoRoot "%~dp0." %*
set "RC=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %RC%
