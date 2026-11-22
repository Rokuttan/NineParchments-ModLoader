@echo off
rem NPModLoader launcher for Windows.
rem   modloader.bat <command> [options]      e.g.  modloader.bat build   /   modloader.bat install
rem Double-clicking it (no command) shows the help.
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
"%PYEXE%" %PYARG% modloader.py %*
set "RC=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %RC%
