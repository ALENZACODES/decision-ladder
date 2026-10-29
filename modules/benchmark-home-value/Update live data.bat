@echo off
setlocal
title Benchmark Home Value - update live data
cd /d "%~dp0"
echo.
echo   Updating live data (Bank of Canada rates, chart library)...
echo.
py -3 -c "import urllib.request" >nul 2>&1
if not errorlevel 1 (
  py -3 tools\update_data.py
  goto :done
)
python -c "import urllib.request" >nul 2>&1
if not errorlevel 1 (
  python tools\update_data.py
  goto :done
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\update_data.ps1"
:done
echo.
pause
endlocal
