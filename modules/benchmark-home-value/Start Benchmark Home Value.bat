@echo off
setlocal
title Benchmark Home Value
cd /d "%~dp0"
rem Pick a free port: 8765, else 8766, else 8767
set PORT=8765
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul && set PORT=8766
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul && set PORT=8767
echo.
echo   Benchmark Home Value is starting at http://localhost:%PORT%/
echo   Keep this window open while you use it. Close it to stop.
echo.
rem Open the browser two seconds from now, once the server is up
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:%PORT%/index.html'"
rem Fail-safe 1: the Python launcher (app server with data relay, then plain server).  Fail-safe 2: python.  Fail-safe 3: PowerShell, built into every Windows PC.
py -3 -c "import http.server" >nul 2>&1
if not errorlevel 1 (
  py -3 tools\serve.py %PORT%
  if errorlevel 1 py -3 -m http.server %PORT% --bind 127.0.0.1
  goto :end
)
python -c "import http.server" >nul 2>&1
if not errorlevel 1 (
  python tools\serve.py %PORT%
  if errorlevel 1 python -m http.server %PORT% --bind 127.0.0.1
  goto :end
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\serve.ps1" -Port %PORT% -NoBrowser
:end
endlocal
