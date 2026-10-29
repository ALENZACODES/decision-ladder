@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File scripts\go_live.ps1
pause
