@echo off
setlocal
cd /d "%~dp0\.."

set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python 3 was not found.
        echo Install it from https://www.python.org/downloads/windows/
        echo or run windows\install_dependencies.bat
        pause
        exit /b 1
    )
    set "PY=py -3"
)

%PY% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo Tkinter is missing. Reinstall Python and enable "tcl/tk and IDLE".
    pause
    exit /b 1
)

echo Installing/updating PyInstaller...
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo Failed to install PyInstaller.
    pause
    exit /b 1
)

echo Building Windows onedir package...
%PY% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name CapybaraDownloader ^
    --icon "assets\capybara.ico" ^
    --add-data "assets;assets" ^
    "yt_dlp_gui.py"
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

if exist "yt-dlp.exe" copy /y "yt-dlp.exe" "dist\CapybaraDownloader\yt-dlp.exe" >nul
if exist "ffmpeg.exe" copy /y "ffmpeg.exe" "dist\CapybaraDownloader\ffmpeg.exe" >nul

echo.
echo Build complete:
echo   dist\CapybaraDownloader\CapybaraDownloader.exe
echo.
echo Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
echo.
pause
