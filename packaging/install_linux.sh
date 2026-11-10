#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "$0")" && pwd)"

APP_DIR=""
APP_EXE=""
for directory in \
    "$HERE/CapybaraDownloader" \
    "$HERE/dist/CapybaraDownloader" \
    "$HERE/capybara-app"; do
    if [ -x "$directory/CapybaraDownloader" ]; then
        APP_DIR="$directory"
        APP_EXE="$directory/CapybaraDownloader"
        break
    fi
    if [ -x "$directory/capybara-downloader" ]; then
        APP_DIR="$directory"
        APP_EXE="$directory/capybara-downloader"
        break
    fi
done

if [ -z "$APP_EXE" ]; then
    echo "CapybaraDownloader was not found." >&2
    echo "Run ./build_linux.sh first, or extract the release package." >&2
    exit 1
fi

ICON_SOURCE=""
for candidate in \
    "$APP_DIR/_internal/assets/capybara-256.png" \
    "$APP_DIR/assets/capybara-256.png" \
    "$HERE/assets/capybara-256.png" \
    "$HERE/../assets/capybara-256.png"; do
    if [ -f "$candidate" ]; then
        ICON_SOURCE="$candidate"
        break
    fi
done

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR_DATA="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
ICON_DEST="$ICON_DIR/capybara-downloader.png"
DESKTOP_FILE="$APP_DIR_DATA/capybara-downloader.desktop"

install -d "$APP_DIR_DATA" "$ICON_DIR"
if [ -n "$ICON_SOURCE" ]; then
    install -m 644 "$ICON_SOURCE" "$ICON_DEST"
    ICON_VALUE="$ICON_DEST"
else
    ICON_VALUE="application-x-executable"
fi

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=卡皮巴拉视频下载器
Name[zh_CN]=卡皮巴拉视频下载器
Name[en]=Capybara Video Downloader
GenericName=视频下载器
Comment=基于 yt-dlp 的视频下载器
Exec="$APP_EXE"
TryExec=$APP_EXE
Path=$APP_DIR
Icon=$ICON_VALUE
Terminal=false
Categories=AudioVideo;
Keywords=video;download;yt-dlp;bilibili;youtube;capybara;视频;下载;卡皮巴拉;
StartupNotify=true
StartupWMClass=Capybaradownloader
EOF

chmod 755 "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR_DATA" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Installed:"
echo "  $DESKTOP_FILE"
if [ -n "$ICON_SOURCE" ]; then
    echo "  $ICON_DEST"
fi
echo
echo "You can now launch '卡皮巴拉视频下载器' from the application menu."
