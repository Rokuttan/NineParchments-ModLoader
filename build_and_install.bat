@echo off
rem Double-click: builds the active mods and installs them into the game.
rem Co-op mode (the default) needs no launch option. For classic mode run:  build_and_install.bat --modpack
setlocal
cd /d "%~dp0"
call modloader.bat build %*
if errorlevel 1 (
    echo.
    echo Build failed: nothing was installed. Read the errors above.
    pause
    exit /b 1
)
call modloader.bat install
if errorlevel 1 (
    echo.
    echo Install failed. Read the messages above.
    pause
    exit /b 1
)
echo.
echo Done. Start the game normally.
pause
