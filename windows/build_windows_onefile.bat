@echo off
setlocal
cd /d "%~dp0\.."

set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python 3 was not found.
        pause
        exit /b 1
    )
    set "PY=py -3"
)

echo Installing/updating PyInstaller...
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo Failed to install PyInstaller.
    pause
    exit /b 1
)

echo Building single-file Windows exe. Startup will be slower than onedir...
%PY% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
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

if exist "yt-dlp.exe" copy /y "yt-dlp.exe" "dist\yt-dlp.exe" >nul
if exist "ffmpeg.exe" copy /y "ffmpeg.exe" "dist\ffmpeg.exe" >nul

echo.
echo Build complete:
echo   dist\CapybaraDownloader.exe
echo.
pause
