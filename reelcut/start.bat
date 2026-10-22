@echo off
cd /d "%~dp0"
where python >nul 2>nul && (python rolka.py serve) || (py rolka.py serve)
pause
