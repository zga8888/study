#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$0")"

DEPS="$PWD/.build-deps"
if [ ! -d "$DEPS/PyInstaller" ]; then
    echo "Installing PyInstaller into .build-deps ..."
    python3 -m pip install --target "$DEPS" pyinstaller
fi

PYTHONPATH="$DEPS" python3 -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --windowed \
    --name CapybaraDownloader \
    --add-data "$PWD/assets:assets" \
    --distpath "$PWD/dist" \
    --workpath "$PWD/build" \
    --specpath "$PWD/build" \
    "$PWD/yt_dlp_gui.py"

echo
echo "Build complete: $PWD/dist/CapybaraDownloader/CapybaraDownloader"
