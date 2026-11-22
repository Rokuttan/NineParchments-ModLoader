@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py -3 modloader.py %*) || (python modloader.py %*)
if "%~1"=="" pause
