@echo off
cd /d "%~dp0"
py -3 -m pip install pyinstaller
if errorlevel 1 goto fail
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name EvolandSaveEditor --add-data "catalog.json;." editor.py
if errorlevel 1 goto fail
echo Built dist\EvolandSaveEditor.exe
pause
exit /b 0
:fail
echo Build failed. Verify Python and pip are installed.
pause
exit /b 1
