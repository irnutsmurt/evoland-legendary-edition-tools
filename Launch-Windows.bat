@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 editor.py %*
) else (
  python editor.py %*
)
if errorlevel 1 pause
