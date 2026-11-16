@echo off
cd /d "%~dp0"
py -3 -m pip install pyinstaller
if errorlevel 1 goto fail
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name EvolandToolkit --add-data "catalog.json;." --add-data "patch_manifest.json;." editor.py
if errorlevel 1 goto fail
echo Built dist\EvolandToolkit.exe
pause
exit /b 0
:fail
echo Build failed. Verify Python and pip are installed.
pause
exit /b 1
