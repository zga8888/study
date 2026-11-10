#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$0")"

# Prefer a packaged build, then a local Linux build, then run from source.
for candidate in \
    "./CapybaraDownloader/CapybaraDownloader" \
    "./dist/CapybaraDownloader/CapybaraDownloader" \
    "./capybara-app/capybara-downloader"; do
    if [ -x "$candidate" ]; then
        exec "$candidate" "$@"
    fi
done

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 was not found. Install Python 3.10+ first." >&2
    exit 1
fi

exec python3 yt_dlp_gui.py "$@"
