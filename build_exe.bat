@echo off
cd /d "%~dp0"
py -3 -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name Easy_FSC_E3 ^
  --clean ^
  easy_fsc_app.py

echo.
echo Build complete.
echo EXE: %~dp0dist\Easy_FSC_E3.exe
pause
