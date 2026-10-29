@echo off
cd /d "%~dp0"
start "" http://localhost:8000
python -m decision_ladder serve 8000 --offline
pause
