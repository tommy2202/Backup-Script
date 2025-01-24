@echo off
cd /d "%~dp0"
call env\Scripts\activate
python backup_script.py
pause
