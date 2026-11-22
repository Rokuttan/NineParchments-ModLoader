@echo off
rem Double-click: removes everything the loader installed and restores the game executable.
setlocal
cd /d "%~dp0"
call modloader.bat uninstall
pause
