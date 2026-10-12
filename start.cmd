@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install.cmd first. It installs Python and the models locally.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8765/"
".venv\Scripts\python.exe" server.py
pause
