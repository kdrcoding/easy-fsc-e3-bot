@echo off
cd /d "%~dp0"
py -3 easy_fsc_app.py
if errorlevel 1 (
  python easy_fsc_app.py
)
