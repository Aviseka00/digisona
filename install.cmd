@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
if errorlevel 1 (
  echo Installation did not finish. Check the message above, then run install.cmd again.
) else (
  echo Installation complete. Double-click start.cmd to open Digisona.
)
pause
