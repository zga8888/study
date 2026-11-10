$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$OneDirExe = Join-Path $Root 'dist\CapybaraDownloader\CapybaraDownloader.exe'
$OneFileExe = Join-Path $Root 'dist\CapybaraDownloader.exe'

if (Test-Path $OneDirExe) {
    $Exe = $OneDirExe
}
elseif (Test-Path $OneFileExe) {
    $Exe = $OneFileExe
}
else {
    Write-Host 'CapybaraDownloader.exe was not found.' -ForegroundColor Red
    Write-Host 'Run windows\build_windows.bat first.'
    exit 1
}

$Desktop = [Environment]::GetFolderPath('Desktop')
if ([string]::IsNullOrWhiteSpace($Desktop)) {
    $Desktop = Join-Path $env:USERPROFILE 'Desktop'
}

$ShortcutPath = Join-Path $Desktop '卡皮巴拉视频下载器.lnk'
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Exe
$Shortcut.WorkingDirectory = Split-Path -Parent $Exe
$Shortcut.IconLocation = "$Exe,0"
$Shortcut.Description = '卡皮巴拉视频下载器 - yt-dlp GUI'
$Shortcut.WindowStyle = 1
$Shortcut.Save()

Write-Host ''
Write-Host 'Desktop shortcut created:' -ForegroundColor Green
Write-Host "  $ShortcutPath"
Write-Host ''
Write-Host 'To pin it to the taskbar: launch it, then right-click the taskbar icon and choose "Pin to taskbar".'
