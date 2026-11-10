@echo off
setlocal
cd /d "%~dp0\.."

set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python 3 was not found.
        echo Run windows\install_dependencies.bat first.
        pause
        exit /b 1
    )
    set "PY=py -3"
)

%PY% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo Tkinter is missing. Reinstall Python with "tcl/tk and IDLE" enabled.
    pause
    exit /b 1
)

where yt-dlp >nul 2>nul
if errorlevel 1 (
    if not exist "yt-dlp.exe" (
        echo WARNING: yt-dlp was not found in PATH or next to this project.
        echo Install it with: winget install --id yt-dlp.yt-dlp -e
        echo.
    )
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    if not exist "ffmpeg.exe" (
        echo WARNING: ffmpeg was not found in PATH or next to this project.
        echo Install it with: winget install --id Gyan.FFmpeg -e
        echo.
    )
)

%PY% yt_dlp_gui.py
if errorlevel 1 pause
