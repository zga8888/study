#!/usr/bin/env python3
"""yt-dlp 视频下载器（Tkinter 图形界面）。

依赖系统中的 yt-dlp 与 ffmpeg：
    yt-dlp --version
    ffmpeg -version

直接运行：
    python3 yt_dlp_gui.py
"""

from __future__ import annotations

import json
import os
import queue
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from typing import Any
from urllib.parse import urlparse

APP_NAME = "视频下载器"
PROGRESS_MARKER = "__YTDLP_PROGRESS__"

# 界面配色
BG = "#eef2f7"
CARD = "#ffffff"
BORDER = "#dfe5ee"
TEXT = "#1e293b"
MUTED = "#64748b"
FAINT = "#94a3b8"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_SOFT = "#eaf1ff"
SUCCESS = "#15803d"
SUCCESS_SOFT = "#eaf7ee"
DANGER = "#dc2626"
DANGER_SOFT = "#fdecec"
WARNING = "#b45309"
WARNING_SOFT = "#fff7e6"

VIDEO_QUALITIES: list[tuple[str, int | None]] = [
    ("最高画质（自动）", None),
    ("2160p 4K", 2160),
    ("1440p 2K", 1440),
    ("1080p 全高清", 1080),
    ("720p 高清", 720),
    ("480p 流畅", 480),
    ("360p 省流", 360),
]

AUDIO_QUALITIES: list[tuple[str, str]] = [
    ("320 kbps（最佳）", "320K"),
    ("256 kbps", "256K"),
    ("192 kbps（推荐）", "192K"),
    ("128 kbps", "128K"),
]

BROWSERS: list[tuple[str, str | None]] = [
    ("不使用", None),
    ("Chrome", "chrome"),
    ("Chromium", "chromium"),
    ("Firefox", "firefox"),
    ("Edge", "edge"),
    ("Brave", "brave"),
]

if os.name == "nt":
    _CONFIG_ROOT = Path(os.environ.get("APPDATA", str(Path.home())))
else:
    _CONFIG_ROOT = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))

SETTINGS_FILE = _CONFIG_ROOT / "yt-dlp-gui" / "settings.json"


def pick_font(root: tk.Misc) -> tuple[str, str]:
    """选择一款可用的中文字体，并返回正文字体与等宽字体。"""
    families = set(tkfont.families(root))
    for family in (
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Micro Hei",
        "Microsoft YaHei",
        "PingFang SC",
        "Noto Sans SC",
    ):
        if family in families:
            body = family
            break
    else:
        body = tkfont.nametofont("TkDefaultFont").actual("family")

    for family in (
        "Noto Sans Mono CJK SC",
        "Noto Sans Mono",
        "DejaVu Sans Mono",
        "Liberation Mono",
    ):
        if family in families:
            mono = family
            break
    else:
        mono = tkfont.nametofont("TkFixedFont").actual("family")
    return body, mono


def default_download_dir() -> Path:
    for candidate in (Path.home() / "下载", Path.home() / "Downloads", Path.home()):
        if candidate.is_dir():
            return candidate
    return Path.cwd()


def asset_path(filename: str) -> Path:
    """兼容源码运行与 PyInstaller 打包后的资源路径。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / filename


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_tool(name: str) -> str | None:
    """优先查找程序目录旁的 exe，再查 PATH（方便 Windows 绿色版）。"""
    suffix = ".exe" if os.name == "nt" else ""
    for candidate in (
        app_base_dir() / f"{name}{suffix}",
        app_base_dir() / "bin" / f"{name}{suffix}",
    ):
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)


def find_ytdlp() -> list[str]:
    """优先使用命令行 yt-dlp，其次尝试当前 Python 的 yt_dlp 模块。"""
    executable = find_tool("yt-dlp")
    if not executable:
        for candidate in (
            "/usr/local/bin/yt-dlp",
            "/usr/bin/yt-dlp",
            str(Path.home() / ".local" / "bin" / "yt-dlp"),
        ):
            if os.access(candidate, os.X_OK):
                executable = candidate
                break
    if executable:
        return [executable]

    import importlib.util

    try:
        if importlib.util.find_spec("yt_dlp") is not None:
            return [sys.executable, "-m", "yt_dlp"]
    except (ImportError, ValueError):
        pass
    return []


def probe_version(command: list[str]) -> str | None:
    if not command:
        return None
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            [*command, "--version"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
            env=external_env(),
            **kwargs,
        )
        version = result.stdout.strip().splitlines()
        if result.returncode == 0 and version:
            return version[0]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def external_env() -> dict[str, str]:
    """给外部程序一个干净环境，避免 PyInstaller 的库路径污染。"""
    env = os.environ.copy()
    if os.name == "nt":
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")
    bundle = str(getattr(sys, "_MEIPASS", "") or "").rstrip(os.sep)
    if not bundle:
        return env

    bundle_prefix = bundle + os.sep
    for key in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH"):
        value = env.get(key)
        if not value:
            continue
        kept: list[str] = []
        for item in value.split(os.pathsep):
            if not item:
                continue
            resolved = os.path.abspath(item)
            if resolved == bundle or resolved.startswith(bundle_prefix):
                continue
            kept.append(item)
        if kept:
            env[key] = os.pathsep.join(kept)
        else:
            env.pop(key, None)
    return env


def normalise_proxy(value: str | None) -> str | None:
    if not value:
        return None
    proxy = value.strip().strip("\"'")
    if not proxy:
        return None
    if "://" not in proxy:
        proxy = "http://" + proxy
    parsed = urlparse(proxy)
    if not parsed.hostname:
        return None
    return proxy


def proxy_reachable(proxy: str) -> bool:
    parsed = urlparse(proxy if "://" in proxy else "http://" + proxy)
    host = parsed.hostname
    if not host:
        return False
    if parsed.port:
        port = parsed.port
    elif parsed.scheme.startswith("socks"):
        port = 1080
    elif parsed.scheme == "https":
        port = 443
    else:
        port = 80
    try:
        with socket.create_connection((host, port), timeout=0.7):
            return True
    except OSError:
        return False


def _gsettings_value(schema: str, key: str) -> str | None:
    if not shutil.which("gsettings"):
        return None
    try:
        result = subprocess.run(
            ["gsettings", "get", schema, key],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            env=external_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value or None


def linux_system_proxy() -> str | None:
    if _gsettings_value("org.gnome.system.proxy", "mode") != "manual":
        return None
    for scheme in ("https", "http"):
        host = _gsettings_value(f"org.gnome.system.proxy.{scheme}", "host")
        port = _gsettings_value(f"org.gnome.system.proxy.{scheme}", "port")
        if host:
            return f"http://{host}:{port or 80}"
    return None


def windows_system_proxy() -> str | None:
    try:
        import winreg
    except ImportError:
        return None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        try:
            enabled = winreg.QueryValueEx(key, "ProxyEnable")[0]
            server = winreg.QueryValueEx(key, "ProxyServer")[0]
        finally:
            winreg.CloseKey(key)
    except OSError:
        return None
    if not enabled or not server:
        return None
    if "=" in server:
        values = {}
        for part in server.split(";"):
            if "=" in part:
                name, value = part.split("=", 1)
                values[name.strip().lower()] = value.strip()
        server = values.get("https") or values.get("http") or values.get("socks") or ""
    return normalise_proxy(server)


def macos_system_proxy() -> str | None:
    try:
        result = subprocess.run(
            ["scutil", "--proxy"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = result.stdout
    for scheme in ("HTTPS", "HTTP"):
        enabled = f"{scheme}Enable : 1"
        if enabled not in text:
            continue
        host = ""
        port = ""
        for line in text.splitlines():
            if line.strip().startswith(f"{scheme}Proxy :"):
                host = line.split(":", 1)[1].strip()
            elif line.strip().startswith(f"{scheme}Port :"):
                port = line.split(":", 1)[1].strip()
        if host:
            return f"http://{host}:{port or 80}"
    return None


def system_proxy() -> str | None:
    if os.name == "nt":
        return windows_system_proxy()
    if sys.platform == "darwin":
        return macos_system_proxy()
    return linux_system_proxy()


def resolve_proxy(setting: str | None) -> tuple[str | None, str]:
    value = "auto" if setting is None else str(setting).strip()
    if value.lower() in {"", "none", "off", "direct", "disabled"}:
        return None, "已禁用"
    if value.lower() != "auto":
        proxy = normalise_proxy(value)
        return proxy, "配置文件" if proxy else "配置无效"

    for key in (
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
    ):
        proxy = normalise_proxy(os.environ.get(key))
        if proxy and proxy_reachable(proxy):
            return proxy, f"环境变量 {key}"

    proxy = system_proxy()
    if proxy and proxy_reachable(proxy):
        return proxy, "系统代理"
    return None, "未检测到可用代理"


def human_size(value: float | None) -> str:
    if value is None or value <= 0:
        return "--"
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{size:.0f} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def human_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "--"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def ellipsize(text: str, limit: int = 92) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    head = max(12, limit // 2 - 2)
    tail = max(12, limit - head - 1)
    return f"{text[:head]}…{text[-tail:]}"


def parse_number(value: str) -> float | None:
    value = (value or "").strip()
    if value in {"", "NA", "None", "N/A", "null"}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


class DownloaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME}  ·  yt-dlp")
        self.root.configure(bg=BG)
        self.root.minsize(820, 720)
        self.root.iconname(APP_NAME)
        self._window_icon: tk.PhotoImage | None = None
        self._header_icon: tk.PhotoImage | None = None
        self.ytdlp_badge: tk.Label | None = None
        self._load_icon_assets()

        self.body_font, self.mono_font = pick_font(root)
        self._configure_tk_fonts()
        self._configure_styles()

        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.ytdlp = find_ytdlp()
        self.ytdlp_version: str | None = None
        self.ffmpeg = find_tool("ffmpeg")

        self._process: subprocess.Popen[str] | None = None
        self._process_lock = threading.Lock()
        self._downloading = False
        self._cancel_requested = False
        self._closing = False
        self._progress_mode = "determinate"

        self._settings = self._load_settings()
        self._video_choice = self._settings.get("video_quality", "1080p 全高清")
        self._audio_choice = self._settings.get("audio_quality", "192 kbps（推荐）")
        proxy_setting = self._settings.get("proxy", "auto")
        self._proxy_setting = (
            proxy_setting.strip() if isinstance(proxy_setting, str) else "auto"
        )
        if self._video_choice not in dict(VIDEO_QUALITIES):
            self._video_choice = "1080p 全高清"
        if self._audio_choice not in dict(AUDIO_QUALITIES):
            self._audio_choice = "192 kbps（推荐）"

        self._build_variables()
        self._build_ui()
        self._on_mode_change()
        self._reset_progress()
        self._update_download_state(False)
        self._append_log(
            [
                "就绪。粘贴视频链接后点击“开始下载”，或按 Enter。",
                "提示：日志会显示 yt-dlp 的解析与下载信息。",
            ]
        )

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", self._on_escape)
        self._center_window()
        self.root.after(80, self._poll_queue)

        if self.ytdlp:
            threading.Thread(
                target=self._probe_ytdlp_version,
                name="yt-dlp-version",
                daemon=True,
            ).start()

    def _probe_ytdlp_version(self) -> None:
        version = probe_version(self.ytdlp)
        if version:
            self._queue.put(("ytdlp_version", version))

    # ------------------------------------------------------------------ 样式
    def _load_icon_assets(self) -> None:
        try:
            self._window_icon = tk.PhotoImage(file=str(asset_path("capybara-256.png")))
            self.root.iconphoto(True, self._window_icon)
        except (OSError, tk.TclError):
            self._window_icon = None

        try:
            self._header_icon = tk.PhotoImage(file=str(asset_path("capybara-48.png")))
        except (OSError, tk.TclError):
            self._header_icon = None

    def _configure_tk_fonts(self) -> None:
        for name, size in (
            ("TkDefaultFont", 10),
            ("TkTextFont", 10),
            ("TkMenuFont", 10),
            ("TkHeadingFont", 10),
        ):
            try:
                tkfont.nametofont(name).configure(family=self.body_font, size=size)
            except tk.TclError:
                pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        family = self.body_font
        style.configure(".", font=(family, 10), background=BG, foreground=TEXT)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.configure("TRadiobutton", background=CARD, foreground=TEXT)
        style.configure("Card.TFrame", background=CARD)

        style.configure(
            "TEntry",
            fieldbackground="#ffffff",
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            insertcolor=TEXT,
            padding=(8, 7),
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", ACCENT)],
            lightcolor=[("focus", ACCENT)],
            darkcolor=[("focus", ACCENT)],
        )

        style.configure(
            "TCombobox",
            fieldbackground="#ffffff",
            background="#ffffff",
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowcolor=MUTED,
            padding=(7, 5),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#ffffff")],
            selectbackground=[("readonly", "#ffffff")],
            selectforeground=[("readonly", TEXT)],
            bordercolor=[("focus", ACCENT)],
        )

        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#ffffff",
            bordercolor=ACCENT,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            focuscolor=ACCENT,
            borderwidth=0,
            padding=(20, 9),
            font=(family, 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("disabled", "#9eb8f0"),
                ("pressed", ACCENT_HOVER),
                ("active", ACCENT_HOVER),
            ],
            bordercolor=[("disabled", "#9eb8f0"), ("active", ACCENT_HOVER)],
            foreground=[("disabled", "#ffffff")],
        )

        style.configure(
            "Secondary.TButton",
            background="#ffffff",
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            focuscolor="#ffffff",
            borderwidth=1,
            padding=(14, 7),
        )
        style.map(
            "Secondary.TButton",
            background=[("pressed", "#e9eef7"), ("active", "#f5f8fc")],
            bordercolor=[("active", "#c6d2e3")],
        )

        style.configure(
            "Ghost.TButton",
            background=CARD,
            foreground=MUTED,
            borderwidth=0,
            padding=(6, 2),
            font=(family, 9),
        )
        style.map(
            "Ghost.TButton",
            background=[("active", "#f1f5fb")],
            foreground=[("active", TEXT)],
        )

        style.configure(
            "Card.TCheckbutton",
            background=CARD,
            foreground=TEXT,
            focuscolor=CARD,
        )
        style.map("Card.TCheckbutton", background=[("active", CARD)])
        style.configure(
            "Card.TRadiobutton",
            background=CARD,
            foreground=TEXT,
            focuscolor=CARD,
        )
        style.map("Card.TRadiobutton", background=[("active", CARD)])
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor="#e8eef7",
            background=ACCENT,
            bordercolor="#e8eef7",
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            borderwidth=0,
            thickness=10,
        )
        style.configure(
            "Vertical.TScrollbar",
            background="#cbd5e1",
            troughcolor="#f7f9fc",
            bordercolor="#f7f9fc",
            arrowcolor=MUTED,
        )

    # ------------------------------------------------------------------ 数据
    def _build_variables(self) -> None:
        self.url_var = tk.StringVar()
        saved_dir = str(self._settings.get("download_dir") or "").strip()
        self.dest_var = tk.StringVar(
            value=saved_dir if saved_dir else str(default_download_dir())
        )
        mode = self._settings.get("mode", "video")
        self.mode_var = tk.StringVar(
            value=mode if mode in {"video", "audio"} else "video"
        )
        self.quality_var = tk.StringVar(value=self._video_choice)
        self.playlist_var = tk.BooleanVar(
            value=bool(self._settings.get("playlist", False))
        )
        self.subs_var = tk.BooleanVar(
            value=bool(self._settings.get("subtitles", False))
        )
        browser = self._settings.get("browser", "不使用")
        if browser not in dict(BROWSERS):
            browser = "不使用"
        self.browser_var = tk.StringVar(value=browser)

        self.status_var = tk.StringVar(value="准备就绪")
        self.percent_var = tk.StringVar(value="0%")
        self.detail_var = tk.StringVar(value="速度 --   ·   剩余 --   ·   已下载 --")
        self.file_var = tk.StringVar(value="等待下载任务")

    # -------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=BG, padx=20, pady=14)
        outer.pack(fill="both", expand=True)

        self._build_header(outer)
        self._build_url_card(outer)
        self._build_options_card(outer)
        self._build_actions(outer)
        self._build_progress_card(outer)
        self._build_log_card(outer)

    def _build_header(self, parent: tk.Widget) -> None:
        header = tk.Frame(
            parent,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0,
        )
        header.pack(fill="x")

        inner = tk.Frame(header, bg=CARD, padx=18, pady=11)
        inner.pack(fill="x")

        if self._header_icon is not None:
            tk.Label(inner, image=self._header_icon, bg=CARD, bd=0).pack(
                side="left", padx=(0, 12)
            )
        else:
            logo = tk.Canvas(
                inner,
                width=44,
                height=44,
                bg=CARD,
                highlightthickness=0,
                bd=0,
            )
            logo.pack(side="left", padx=(0, 12))
            logo.create_oval(2, 2, 42, 42, fill=ACCENT_SOFT, outline="")
            logo.create_line(22, 11, 22, 27, fill=ACCENT, width=3, capstyle="round")
            logo.create_polygon(15, 22, 29, 22, 22, 31, fill=ACCENT, outline="")
            logo.create_line(14, 35, 30, 35, fill=ACCENT, width=3, capstyle="round")

        titles = tk.Frame(inner, bg=CARD)
        titles.pack(side="left", fill="y")
        tk.Label(
            titles,
            text=APP_NAME,
            bg=CARD,
            fg=TEXT,
            font=(self.body_font, 18, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            titles,
            text="yt-dlp 图形界面  ·  B 站、YouTube 等 1000+ 网站",
            bg=CARD,
            fg=MUTED,
            font=(self.body_font, 9),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        badges = tk.Frame(inner, bg=CARD)
        badges.pack(side="right", anchor="n")
        if self.ytdlp:
            version = self.ytdlp_version or "已安装"
            self.ytdlp_badge = self._badge(
                badges, f"yt-dlp {version}", ACCENT, ACCENT_SOFT
            )
            self.ytdlp_badge.pack(side="left", padx=(0, 6))
        else:
            self.ytdlp_badge = self._badge(badges, "未找到 yt-dlp", DANGER, DANGER_SOFT)
            self.ytdlp_badge.pack(side="left", padx=(0, 6))
        if self.ffmpeg:
            self._badge(badges, "ffmpeg 可用", SUCCESS, SUCCESS_SOFT).pack(side="left")
        else:
            self._badge(badges, "缺少 ffmpeg", WARNING, WARNING_SOFT).pack(side="left")

    def _badge(self, parent: tk.Widget, text: str, fg: str, bg: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=(self.body_font, 8),
            padx=8,
            pady=3,
        )

    def _card(self, parent: tk.Widget) -> tk.Frame:
        card = tk.Frame(
            parent,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0,
        )
        return card

    def _build_url_card(self, parent: tk.Widget) -> None:
        card = self._card(parent)
        card.pack(fill="x", pady=(12, 0))

        inner = tk.Frame(card, bg=CARD, padx=16, pady=10)
        inner.pack(fill="x")

        top = tk.Frame(inner, bg=CARD)
        top.pack(fill="x")
        tk.Label(
            top,
            text="视频链接",
            bg=CARD,
            fg=TEXT,
            font=(self.body_font, 10, "bold"),
            anchor="w",
        ).pack(side="left")
        tk.Label(
            top,
            text="按 Enter 可快速开始",
            bg=CARD,
            fg=FAINT,
            font=(self.body_font, 8),
            anchor="e",
        ).pack(side="right")

        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x", pady=(7, 0))

        self.url_entry = ttk.Entry(
            row,
            textvariable=self.url_var,
            font=(self.body_font, 11),
        )
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=1)
        self.url_entry.bind("<Return>", lambda _event: self._start_download())

        paste = ttk.Button(
            row,
            text="粘贴",
            style="Secondary.TButton",
            command=self._paste_url,
        )
        paste.pack(side="left", padx=(8, 0))

    def _build_options_card(self, parent: tk.Widget) -> None:
        card = self._card(parent)
        card.pack(fill="x", pady=(10, 0))

        inner = tk.Frame(card, bg=CARD, padx=16, pady=10)
        inner.pack(fill="x")
        inner.grid_columnconfigure(1, weight=1)
        inner.grid_columnconfigure(3, minsize=168)

        label_kw = {
            "bg": CARD,
            "fg": TEXT,
            "font": (self.body_font, 10),
            "anchor": "w",
        }

        tk.Label(inner, text="保存位置", **label_kw).grid(
            row=0, column=0, sticky="w", pady=(0, 9)
        )
        self.dest_entry = ttk.Entry(inner, textvariable=self.dest_var)
        self.dest_entry.grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=(10, 8), pady=(0, 9)
        )
        self.browse_btn = ttk.Button(
            inner,
            text="浏览…",
            style="Secondary.TButton",
            command=self._choose_directory,
        )
        self.browse_btn.grid(row=0, column=4, sticky="e", pady=(0, 9))

        tk.Label(inner, text="下载为", **label_kw).grid(
            row=1, column=0, sticky="w", pady=(0, 4)
        )

        mode_row = tk.Frame(inner, bg=CARD)
        mode_row.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(0, 4))
        self.video_radio = ttk.Radiobutton(
            mode_row,
            text="视频 MP4",
            value="video",
            variable=self.mode_var,
            style="Card.TRadiobutton",
            command=self._on_mode_change,
        )
        self.video_radio.pack(side="left")
        self.audio_radio = ttk.Radiobutton(
            mode_row,
            text="音频 MP3",
            value="audio",
            variable=self.mode_var,
            style="Card.TRadiobutton",
            command=self._on_mode_change,
        )
        self.audio_radio.pack(side="left", padx=(14, 0))

        self.quality_label = tk.Label(inner, text="画质", **label_kw)
        self.quality_label.grid(row=1, column=2, sticky="e", padx=(8, 8), pady=(0, 4))
        self.quality_combo = ttk.Combobox(
            inner,
            textvariable=self.quality_var,
            state="readonly",
            width=18,
        )
        self.quality_combo.grid(row=1, column=3, sticky="ew", pady=(0, 4))
        self.quality_combo.bind("<<ComboboxSelected>>", self._on_quality_selected)

        options = tk.Frame(inner, bg=CARD)
        options.grid(row=2, column=0, columnspan=5, sticky="ew", pady=(7, 0))

        self.playlist_check = ttk.Checkbutton(
            options,
            text="下载整个播放列表",
            variable=self.playlist_var,
            style="Card.TCheckbutton",
        )
        self.playlist_check.pack(side="left")

        self.subs_check = ttk.Checkbutton(
            options,
            text="嵌入字幕（如有）",
            variable=self.subs_var,
            style="Card.TCheckbutton",
        )
        self.subs_check.pack(side="left", padx=(20, 0))

        cookie_box = tk.Frame(options, bg=CARD)
        cookie_box.pack(side="right")
        tk.Label(
            cookie_box,
            text="Cookie：",
            bg=CARD,
            fg=MUTED,
            font=(self.body_font, 9),
        ).pack(side="left")
        self.cookie_combo = ttk.Combobox(
            cookie_box,
            textvariable=self.browser_var,
            values=[name for name, _ in BROWSERS],
            state="readonly",
            width=10,
        )
        self.cookie_combo.pack(side="left")

    def _build_actions(self, parent: tk.Widget) -> None:
        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill="x", pady=(10, 0))

        self.open_btn = ttk.Button(
            actions,
            text="打开下载目录",
            style="Secondary.TButton",
            command=self._open_download_dir,
        )
        self.open_btn.pack(side="left")

        self.start_btn = ttk.Button(
            actions,
            text="开始下载",
            style="Accent.TButton",
            command=self._start_download,
        )
        self.start_btn.pack(side="right")

        self.cancel_btn = ttk.Button(
            actions,
            text="取消下载",
            style="Secondary.TButton",
            command=self._cancel_download,
        )
        self.cancel_btn.pack(side="right", padx=(0, 8))

    def _build_progress_card(self, parent: tk.Widget) -> None:
        card = self._card(parent)
        card.pack(fill="x", pady=(10, 0))

        inner = tk.Frame(card, bg=CARD, padx=16, pady=10)
        inner.pack(fill="x")

        top = tk.Frame(inner, bg=CARD)
        top.pack(fill="x")

        self.status_label = tk.Label(
            top,
            textvariable=self.status_var,
            bg=CARD,
            fg=TEXT,
            font=(self.body_font, 11, "bold"),
            anchor="w",
        )
        self.status_label.pack(side="left")

        self.percent_label = tk.Label(
            top,
            textvariable=self.percent_var,
            bg=CARD,
            fg=ACCENT,
            font=(self.body_font, 11, "bold"),
            anchor="e",
        )
        self.percent_label.pack(side="right")

        self.progress = ttk.Progressbar(
            inner,
            mode="determinate",
            maximum=100,
            style="Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(9, 7))

        tk.Label(
            inner,
            textvariable=self.detail_var,
            bg=CARD,
            fg=MUTED,
            font=(self.body_font, 9),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            inner,
            textvariable=self.file_var,
            bg=CARD,
            fg=FAINT,
            font=(self.body_font, 8),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

    def _build_log_card(self, parent: tk.Widget) -> None:
        card = self._card(parent)
        card.pack(fill="both", expand=True, pady=(10, 0))

        inner = tk.Frame(card, bg=CARD, padx=14, pady=10)
        inner.pack(fill="both", expand=True)

        head = tk.Frame(inner, bg=CARD)
        head.pack(fill="x", pady=(0, 6))
        tk.Label(
            head,
            text="运行日志",
            bg=CARD,
            fg=TEXT,
            font=(self.body_font, 9, "bold"),
            anchor="w",
        ).pack(side="left")
        ttk.Button(
            head,
            text="清空",
            style="Ghost.TButton",
            command=self._clear_log,
        ).pack(side="right")

        text_wrap = tk.Frame(inner, bg=CARD)
        text_wrap.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            text_wrap,
            height=5,
            wrap="word",
            bg="#fafbfd",
            fg="#475569",
            relief="flat",
            bd=0,
            padx=9,
            pady=7,
            font=(self.mono_font, 9),
            insertbackground=TEXT,
            selectbackground="#dbe7ff",
            state="disabled",
        )
        scrollbar = ttk.Scrollbar(
            text_wrap,
            orient="vertical",
            command=self.log_text.yview,
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.log_text.tag_configure("muted", foreground=FAINT)
        self.log_text.tag_configure("error", foreground=DANGER)
        self.log_text.tag_configure("warning", foreground=WARNING)
        self.log_text.tag_configure("success", foreground=SUCCESS)
        self.log_text.bind("<Control-c>", self._copy_log_selection)
        self.log_text.bind("<Control-C>", self._copy_log_selection)

    # ----------------------------------------------------------------- 工具
    def _center_window(self) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(950, max(820, screen_w - 120))
        height = min(770, max(720, screen_h - 110))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 18)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _load_settings(self) -> dict[str, Any]:
        try:
            with SETTINGS_FILE.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        data = {
            "download_dir": self.dest_var.get().strip(),
            "mode": self.mode_var.get(),
            "video_quality": self._video_choice,
            "audio_quality": self._audio_choice,
            "playlist": bool(self.playlist_var.get()),
            "subtitles": bool(self.subs_var.get()),
            "browser": self.browser_var.get(),
            "proxy": self._proxy_setting,
        }
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with SETTINGS_FILE.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _refresh_quality_values(self) -> None:
        if self.mode_var.get() == "audio":
            values = [name for name, _ in AUDIO_QUALITIES]
            current = self._audio_choice
        else:
            values = [name for name, _ in VIDEO_QUALITIES]
            current = self._video_choice

        self.quality_combo.configure(values=values)
        if current not in values:
            current = values[0]
            if self.mode_var.get() == "audio":
                self._audio_choice = current
            else:
                self._video_choice = current
        self.quality_var.set(current)
        self._on_quality_selected()

    def _on_mode_change(self) -> None:
        is_video = self.mode_var.get() == "video"
        self.quality_label.configure(text="画质" if is_video else "音质")
        if is_video:
            self.subs_check.state(["!disabled"])
        else:
            self.subs_check.state(["disabled"])
        self._refresh_quality_values()

    def _on_quality_selected(self, _event: tk.Event | None = None) -> None:
        value = self.quality_var.get()
        if self.mode_var.get() == "audio":
            self._audio_choice = value
        else:
            self._video_choice = value

    def _paste_url(self) -> None:
        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            messagebox.showinfo(
                "剪贴板为空", "剪贴板中没有可粘贴的文本。", parent=self.root
            )
            return

        match = re.search(r"https?://\S+", text)
        if match:
            text = match.group(0)
        if text:
            self.url_var.set(text)
            self.url_entry.icursor("end")
            self.url_entry.focus_set()

    def _choose_directory(self) -> None:
        initial = Path(self.dest_var.get()).expanduser()
        selected = filedialog.askdirectory(
            parent=self.root,
            title="选择保存位置",
            initialdir=str(initial if initial.is_dir() else Path.home()),
            mustexist=False,
        )
        if selected:
            self.dest_var.set(selected)

    def _open_download_dir(self) -> None:
        directory = Path(self.dest_var.get()).expanduser()
        if not directory.is_dir():
            messagebox.showinfo(
                "文件夹不存在",
                f"保存目录不存在：\n{directory}",
                parent=self.root,
            )
            return

        directory = directory.resolve()
        if os.name == "nt":
            try:
                os.startfile(str(directory))  # type: ignore[attr-defined]
            except OSError as exc:
                messagebox.showerror(
                    "无法打开文件夹",
                    f"打开文件夹失败：{exc}",
                    parent=self.root,
                )
            return

        if sys.platform == "darwin":
            candidates = [("open", "open", str(directory))]
        else:
            # Cinnamon 下优先用 nemo，避免 xdg-open 在部分会话中静默失败。
            candidates = [
                ("Nemo", "nemo", str(directory)),
                ("xdg-open", "xdg-open", str(directory)),
                ("gio", "gio", "open", str(directory)),
            ]

        errors: list[str] = []
        for candidate in candidates:
            label, program, *arguments = candidate
            executable = shutil.which(program)
            if not executable:
                continue
            try:
                result = subprocess.run(
                    [executable, *arguments],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                    env=external_env(),
                )
            except subprocess.TimeoutExpired:
                # 文件管理器已启动并在等待窗口关闭。
                return
            except OSError as exc:
                errors.append(f"{label}: {exc}")
                continue

            if result.returncode == 0:
                return
            detail = (result.stderr or result.stdout).strip()
            errors.append(f"{label}: {detail or f'退出码 {result.returncode}'}")

        detail_text = "\n".join(errors) if errors else "没有找到可用的文件管理器。"
        messagebox.showerror(
            "无法打开文件夹",
            f"无法打开：\n{directory}\n\n{detail_text}",
            parent=self.root,
        )

    def _normalise_url(self, raw: str) -> str | None:
        value = raw.strip().strip("\"'")
        if not value:
            return None
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
            if re.match(r"^[\w.-]+\.[a-zA-Z]{2,}(?:[/?#]|$)", value):
                value = "https://" + value
            else:
                return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return value

    # ----------------------------------------------------------------- 日志
    def _append_log(self, lines: list[str]) -> None:
        if not lines:
            return
        self.log_text.configure(state="normal")
        for line in lines:
            tag = ""
            upper = line.upper()
            if "ERROR" in upper:
                tag = "error"
            elif "WARNING" in upper:
                tag = "warning"
            elif line.startswith("✓"):
                tag = "success"
            elif line.startswith("$"):
                tag = "muted"
            self.log_text.insert("end", line + "\n", tag)
        total_lines = int(self.log_text.index("end-1c").split(".")[0])
        if total_lines > 600:
            self.log_text.delete("1.0", f"{total_lines - 520}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _copy_log_selection(self, _event: tk.Event) -> str:
        try:
            selected = self.log_text.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)
        return "break"

    # ----------------------------------------------------------------- 状态
    def _reset_progress(self) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self._progress_mode = "determinate"
        self.percent_var.set("0%")
        self.status_var.set("准备就绪")
        self.status_label.configure(fg=TEXT)
        self.percent_label.configure(fg=ACCENT)
        self.detail_var.set("速度 --   ·   剩余 --   ·   已下载 --")
        self.file_var.set("等待下载任务")

    def _update_download_state(self, downloading: bool) -> None:
        self._downloading = downloading
        if downloading:
            self.start_btn.state(["disabled"])
            self.cancel_btn.state(["!disabled"])
            self.start_btn.configure(text="下载中…")
        else:
            self.start_btn.state(["!disabled"])
            self.cancel_btn.state(["disabled"])
            self.start_btn.configure(text="开始下载")

    def _set_progress_value(self, percent: float) -> None:
        percent = max(0.0, min(100.0, percent))
        if self._progress_mode != "determinate":
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self._progress_mode = "determinate"
        self.progress["value"] = percent

    def _set_indeterminate(self) -> None:
        if self._progress_mode != "indeterminate":
            self.progress.stop()
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
            self._progress_mode = "indeterminate"

    # --------------------------------------------------------------- 下载流程
    def _build_command(
        self,
        url: str,
        directory: Path,
        mode: str,
        quality: str,
        playlist: bool,
        subtitles: bool,
        browser: str,
        proxy: str | None = None,
    ) -> list[str]:
        command = [
            *self.ytdlp,
            "--newline",
            "--no-color",
            "--progress",
            "--progress-delta",
            "0.2",
            "--progress-template",
            (
                f"download:{PROGRESS_MARKER}"
                "%(progress.status)s|%(progress.downloaded_bytes)s|"
                "%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|"
                "%(progress.speed)s|%(progress.eta)s|"
                "%(progress.fragment_index)s|%(progress.fragment_count)s"
            ),
            "--paths",
            str(directory),
            "--output",
            "%(title).150B [%(id)s].%(ext)s",
            "--trim-filenames",
            "180",
            "--no-overwrites",
            "--concurrent-fragments",
            "4",
            "--retries",
            "10",
            "--fragment-retries",
            "10",
            "--embed-metadata",
        ]

        if self.ffmpeg:
            command.extend(["--ffmpeg-location", str(Path(self.ffmpeg).parent)])
        if proxy:
            command.extend(["--proxy", proxy])

        if playlist:
            command.append("--yes-playlist")
        else:
            command.append("--no-playlist")

        browser_id = dict(BROWSERS).get(browser)
        if browser_id:
            command.extend(["--cookies-from-browser", browser_id])

        if mode == "audio":
            audio_quality = dict(AUDIO_QUALITIES).get(quality, "192K")
            command.extend(
                [
                    "--format",
                    "ba/b",
                    "--extract-audio",
                    "--audio-format",
                    "mp3",
                    "--audio-quality",
                    audio_quality,
                ]
            )
        else:
            height = dict(VIDEO_QUALITIES).get(quality)
            if height is None:
                format_selector = "bv*+ba/b"
            else:
                format_selector = f"bv*[height<={height}]+ba/b[height<={height}]/b"
            command.extend(
                [
                    "--format",
                    format_selector,
                    "--merge-output-format",
                    "mp4",
                ]
            )
            if subtitles:
                command.extend(
                    [
                        "--write-subs",
                        "--write-auto-subs",
                        "--embed-subs",
                        "--sub-langs",
                        "zh-Hans,zh-CN,zh,en",
                        "--convert-subs",
                        "srt",
                    ]
                )

        command.extend(["--", url])
        return command

    def _start_download(self) -> None:
        if self._downloading:
            return

        url = self._normalise_url(self.url_var.get())
        if url is None:
            messagebox.showwarning(
                "链接无效",
                "请粘贴有效的 http:// 或 https:// 视频链接。",
                parent=self.root,
            )
            self.url_entry.focus_set()
            return

        if not self.ytdlp:
            messagebox.showerror(
                "未找到 yt-dlp",
                "系统中没有找到 yt-dlp。\n\n"
                "请先在终端安装：\n"
                "  sudo pip3 install -U yt-dlp\n"
                "或参考：https://github.com/yt-dlp/yt-dlp",
                parent=self.root,
            )
            return

        directory = Path(self.dest_var.get()).expanduser()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(
                "无法创建文件夹",
                f"无法创建保存目录：\n{directory}\n\n{exc}",
                parent=self.root,
            )
            return
        if not directory.is_dir():
            messagebox.showerror(
                "保存位置无效",
                f"保存位置不是文件夹：\n{directory}",
                parent=self.root,
            )
            return
        self.dest_var.set(str(directory))

        if not self.ffmpeg:
            proceed = messagebox.askyesno(
                "未找到 ffmpeg",
                "合并视频、转换 MP3 与嵌入字幕都需要 ffmpeg。\n"
                "当前系统未找到 ffmpeg，下载可能失败。\n\n"
                "仍要继续吗？",
                parent=self.root,
            )
            if not proceed:
                return

        proxy, proxy_source = resolve_proxy(self._proxy_setting)
        if proxy:
            self._append_log([f"网络代理：{proxy}（{proxy_source}）"])
        elif proxy_source not in {"未检测到可用代理", "已禁用"}:
            self._append_log([f"网络代理：未使用（{proxy_source}）"])

        cmd = self._build_command(
            url=url,
            directory=directory,
            mode=self.mode_var.get(),
            quality=self.quality_var.get(),
            playlist=bool(self.playlist_var.get()),
            subtitles=bool(self.subs_var.get()) and self.mode_var.get() == "video",
            browser=self.browser_var.get(),
            proxy=proxy,
        )

        self._save_settings()
        self._cancel_requested = False
        self._update_download_state(True)
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self._progress_mode = "determinate"
        self.percent_var.set("0%")
        self.percent_label.configure(fg=ACCENT)
        self.status_var.set("正在解析视频链接…")
        self.status_label.configure(fg=TEXT)
        self.detail_var.set("正在获取视频信息，请稍候…")
        self.file_var.set("")

        worker = threading.Thread(
            target=self._download_worker,
            args=(cmd, directory),
            name="yt-dlp-worker",
            daemon=True,
        )
        worker.start()

    def _download_worker(self, command: list[str], directory: Path) -> None:
        code = -1
        error = ""
        self._queue.put(("log", ["$ " + shlex.join(command)]))
        try:
            kwargs: dict[str, Any] = {
                "cwd": str(directory),
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "bufsize": 1,
                "env": external_env(),
            }
            if os.name == "nt":
                kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                )
            else:
                kwargs["start_new_session"] = True

            process = subprocess.Popen(command, **kwargs)
            with self._process_lock:
                self._process = process
            self._queue.put(("status", "正在连接并获取视频信息…"))

            if self._cancel_requested:
                self._terminate_process()

            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.replace("\r", "").strip()
                if not line:
                    continue
                marker_index = line.find(PROGRESS_MARKER)
                if marker_index >= 0:
                    data = self._parse_progress(
                        line[marker_index + len(PROGRESS_MARKER) :]
                    )
                    if data:
                        self._queue.put(("progress", data))
                    continue

                self._queue.put(("line", line))
                if "ERROR:" in line:
                    error = line

            code = process.wait()
        except FileNotFoundError as exc:
            error = f"找不到 yt-dlp 可执行文件：{exc}"
            self._queue.put(("line", f"ERROR: {error}"))
        except Exception as exc:  # noqa: BLE001 - 必须确保 GUI 收到结束消息
            error = f"{type(exc).__name__}: {exc}"
            self._queue.put(("line", f"ERROR: {error}"))
        finally:
            with self._process_lock:
                self._process = None
            self._queue.put(("finished", (code, error)))

    @staticmethod
    def _parse_progress(payload: str) -> dict[str, Any] | None:
        parts = payload.split("|")
        if len(parts) < 6:
            return None
        status = parts[0].strip()
        downloaded = parse_number(parts[1])
        total_bytes = parse_number(parts[2])
        total_estimate = parse_number(parts[3])
        speed = parse_number(parts[4])
        eta = parse_number(parts[5])
        fragment_index = parse_number(parts[6]) if len(parts) > 6 else None
        fragment_count = parse_number(parts[7]) if len(parts) > 7 else None

        total = total_bytes or total_estimate
        percent: float | None = None
        if total and downloaded is not None:
            percent = downloaded / total * 100.0
        elif status == "finished":
            percent = 100.0
        elif fragment_index and fragment_count:
            percent = fragment_index / fragment_count * 100.0

        return {
            "status": status,
            "downloaded": downloaded,
            "total": total,
            "speed": speed,
            "eta": eta,
            "percent": percent,
        }

    # ------------------------------------------------------------- 队列与回调
    def _poll_queue(self) -> None:
        if self._closing:
            return
        logs: list[str] = []
        try:
            for _ in range(400):
                kind, payload = self._queue.get_nowait()
                if kind == "log":
                    logs.extend(payload)
                elif kind == "line":
                    self._handle_line(payload)
                    logs.append(payload)
                elif kind == "progress":
                    self._handle_progress(payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "ytdlp_version":
                    if self.ytdlp_badge is not None:
                        self.ytdlp_badge.configure(text=f"yt-dlp {payload}")
                elif kind == "finished":
                    self._handle_finished(*payload)
        except queue.Empty:
            pass

        if logs:
            self._append_log(logs)
        if not self._closing:
            self.root.after(80, self._poll_queue)

    def _handle_line(self, line: str) -> None:
        if line.startswith("[download] Destination:"):
            path = line.split("Destination:", 1)[1].strip().strip('"')
            self.file_var.set("文件：" + ellipsize(Path(path).name, 86))
            current = self.status_var.get()
            if not current.startswith(("正在合并", "正在提取", "播放列表：")):
                self.status_var.set("正在下载…")
        elif line.startswith("[Merger] Merging formats into"):
            self.status_var.set("正在合并音视频…")
            self.detail_var.set("正在调用 ffmpeg 合并，请稍候…")
            if '"' in line:
                path = line.split('"', 1)[1].rsplit('"', 1)[0]
                self.file_var.set("文件：" + ellipsize(Path(path).name, 86))
        elif line.startswith("[ExtractAudio] Destination:"):
            self.status_var.set("正在提取音频…")
            self.detail_var.set("正在调用 ffmpeg 转换为 MP3，请稍候…")
            path = line.split("Destination:", 1)[1].strip().strip('"')
            self.file_var.set("文件：" + ellipsize(Path(path).name, 86))
        elif line.startswith(("[EmbedSubtitle]", "[SubtitlesConvertor]")):
            self.status_var.set("正在嵌入字幕…")
        elif line.startswith("[Metadata]"):
            self.status_var.set("正在写入元数据…")
        elif "Downloading item" in line or "Downloading video" in line:
            match = re.search(r"(\d+)\s+of\s+(\d+)", line)
            if match:
                self.status_var.set(
                    f"播放列表：第 {match.group(1)} / {match.group(2)} 个"
                )
            else:
                self.status_var.set("正在下载播放列表…")
        elif "has already been downloaded" in line:
            self.status_var.set("文件已存在，已跳过")

    def _handle_progress(self, data: dict[str, Any]) -> None:
        percent = data.get("percent")
        status = data.get("status")
        downloaded = data.get("downloaded")
        total = data.get("total")
        speed = data.get("speed")
        eta = data.get("eta")

        if percent is not None:
            self._set_progress_value(float(percent))
            self.percent_var.set(f"{min(100.0, float(percent)):.1f}%")
        else:
            self._set_indeterminate()
            self.percent_var.set("—")

        if status == "downloading":
            current = self.status_var.get()
            if not current or current.startswith(("正在解析", "正在连接", "正在处理")):
                self.status_var.set("正在下载…")
            self.status_label.configure(fg=TEXT)
        elif status == "finished":
            self._set_progress_value(100)
            self.percent_var.set("100%")
            if self.status_var.get() in {
                "正在解析视频链接…",
                "正在连接并获取视频信息…",
                "正在下载…",
                "正在下载播放列表…",
            }:
                self.status_var.set("正在处理…")
            self.status_label.configure(fg=TEXT)

        parts = [f"速度 {human_size(speed) + '/s' if speed else '--'}"]
        if eta is not None:
            parts.append(f"剩余 {human_eta(eta)}")
        else:
            parts.append("剩余 --")
        if total:
            parts.append(f"已下载 {human_size(downloaded)} / {human_size(total)}")
        elif downloaded:
            parts.append(f"已下载 {human_size(downloaded)}")
        else:
            parts.append("已下载 --")
        self.detail_var.set("   ·   ".join(parts))

    def _handle_finished(self, code: int, error: str) -> None:
        self._update_download_state(False)
        if self._cancel_requested:
            self.progress.stop()
            self.status_var.set("已取消")
            self.status_label.configure(fg=WARNING)
            self.percent_label.configure(fg=WARNING)
            self.detail_var.set("下载已取消，临时文件可能仍保留在保存目录中。")
            self._append_log(["■ 已取消下载。"])
        elif code == 0:
            self._set_progress_value(100)
            self.percent_var.set("100%")
            self.status_var.set("下载完成")
            self.status_label.configure(fg=SUCCESS)
            self.percent_label.configure(fg=SUCCESS)
            self.detail_var.set("文件已保存到：" + ellipsize(self.dest_var.get(), 88))
            self._append_log(["✓ 下载完成。"])
        else:
            self.progress.stop()
            self.status_var.set("下载失败")
            self.status_label.configure(fg=DANGER)
            self.percent_label.configure(fg=DANGER)
            reason = error or "yt-dlp 返回了错误，请查看下方日志。"
            self.detail_var.set(ellipsize(reason, 120))
            self._append_log([f"✗ 下载失败（退出码 {code}）。"])

        self._cancel_requested = False

    # ----------------------------------------------------------------- 取消
    def _cancel_download(self) -> None:
        if not self._downloading:
            return
        self._cancel_requested = True
        self.status_var.set("正在取消…")
        self.detail_var.set("正在结束 yt-dlp 进程，请稍候…")
        self._append_log(["■ 用户请求取消下载…"])
        self._terminate_process()

    def _terminate_process(self) -> None:
        with self._process_lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                process.terminate()
            except OSError:
                pass

        threading.Thread(
            target=self._force_kill_later,
            args=(process,),
            name="yt-dlp-killer",
            daemon=True,
        ).start()

    @staticmethod
    def _force_kill_later(process: subprocess.Popen[str]) -> None:
        try:
            process.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    def _on_escape(self, _event: tk.Event) -> None:
        if self._downloading:
            self._cancel_download()

    def _on_close(self) -> None:
        if self._downloading:
            if not messagebox.askyesno(
                "退出下载器",
                "当前仍在下载。确定要取消下载并退出吗？",
                parent=self.root,
            ):
                return
            self._closing = True
            self._cancel_requested = True
            self._terminate_process()
            self._save_settings()
            self.root.after(250, self.root.destroy)
            return

        self._save_settings()
        self.root.destroy()


def main() -> None:
    root = tk.Tk(className="CapybaraDownloader")
    app = DownloaderApp(root)
    if not app.ytdlp:
        root.after(
            300,
            lambda: messagebox.showerror(
                "未找到 yt-dlp",
                "没有找到 yt-dlp，程序无法下载视频。\n\n"
                "请先安装（任选一种）：\n"
                "  sudo pip3 install -U yt-dlp\n"
                "  pipx install yt-dlp\n\n"
                "安装后重新启动本程序。",
                parent=root,
            ),
        )
    root.mainloop()


if __name__ == "__main__":
    main()
