# Changelog

All notable changes to this project are documented here.

## [1.0.1] - 2026-11-12

### Fixed

- Automatically detect the system proxy on Linux, Windows and macOS
- Respect `HTTPS_PROXY` / `HTTP_PROXY` environment variables
- Fix YouTube downloads when the GUI is started from the desktop but the terminal has a proxy

## [1.0.0] - 2026-11-10

### Added

- Tkinter GUI for yt-dlp
- Video download with quality presets from 360p to 4K
- MP3 audio extraction with selectable bitrate
- Real-time progress, speed, ETA and size
- Download cancellation
- Playlist support
- Optional subtitle embedding
- Optional browser cookie import
- Linux and Windows packaging scripts
- GitHub Actions builds for Linux and Windows
