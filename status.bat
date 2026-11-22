@echo off
rem Double-click: shows the mods and what is installed.
setlocal
cd /d "%~dp0"
call modloader.bat list
echo.
call modloader.bat status
pause
