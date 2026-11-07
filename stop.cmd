@echo off
chcp 65001 >nul
setlocal
rem Double-click entry for stop_release.ps1 (release worktree root).
rem Any arguments are forwarded, e.g. stop.cmd -Port 9999
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_release.ps1" -RepoRoot "%~dp0." %*
set "RC=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %RC%
