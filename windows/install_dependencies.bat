@echo off
setlocal
echo This helper installs Python, yt-dlp and FFmpeg with winget.
echo If winget is unavailable, install them manually from their official sites.
echo.

where winget >nul 2>nul
if errorlevel 1 (
    echo winget was not found. Please use the manual steps in README-Windows.md.
    pause
    exit /b 1
)

winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
winget install --id yt-dlp.yt-dlp -e --source winget --accept-package-agreements --accept-source-agreements
winget install --id Gyan.FFmpeg -e --source winget --accept-package-agreements --accept-source-agreements

echo.
echo Done. Close this window and open a new terminal so PATH changes take effect.
pause
