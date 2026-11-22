@echo off
rem Double-click: generates the purple bar textures for the double_skill_tree mod from your own game files.
rem Run it once, then double-click build_and_install.bat in the NPModLoader folder.
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

rem Find Python 3.8+: first the "py" launcher, then "python". A candidate only counts if it prints OK,
rem so a missing command or the Microsoft Store placeholder is skipped.
set "PYEXE="
set "PYARG="
set "PYCHK="
for /f "delims=" %%v in ('py -3 -c "import sys; print('OK' if sys.version_info >= (3, 8) else 'OLD')" 2^>nul') do set "PYCHK=%%v"
if "%PYCHK%"=="OK" (
    set "PYEXE=py"
    set "PYARG=-3"
    goto run
)
set "PYCHK="
for /f "delims=" %%v in ('python -c "import sys; print('OK' if sys.version_info >= (3, 8) else 'OLD')" 2^>nul') do set "PYCHK=%%v"
if "%PYCHK%"=="OK" (
    set "PYEXE=python"
    goto run
)
if "%PYCHK%"=="OLD" (
    echo Your Python is too old: NPModLoader needs Python 3.8 or newer.
) else (
    echo Python 3.8 or newer was not found.
)
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH",
echo then open this window again.
pause
exit /b 9009

:run
"%PYEXE%" %PYARG% make_textures.py
if errorlevel 1 (
    echo.
    echo The textures were not generated. Read the message above.
    pause
    exit /b 1
)
echo.
echo Next step: double-click build_and_install.bat in the NPModLoader folder.
pause
