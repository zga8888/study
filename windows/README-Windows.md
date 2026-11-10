# Windows 使用说明

仓库中的 Linux 版本 **不能直接在 Windows 上运行**。
Windows 版需要单独运行源码或打包，下面两种方式任选一种。

> 仓库中的 `yt_dlp_gui.py`、`assets/` 和 `windows/` 已经包含 Windows 兼容代码和打包脚本。
>
> Windows 发布包由 GitHub Actions 自动构建，不需要复制 Linux 的运行目录。

---

## 方式一：直接运行 Python 源码（最简单）

### 1. 安装 Python

从 [python.org](https://www.python.org/downloads/windows/) 下载 Python 3.10 或更高版本。

安装时务必勾选：

- **Add python.exe to PATH**
- **tcl/tk and IDLE**（Tkinter GUI 依赖）

也可以在 PowerShell 中执行：

```powershell
winget install --id Python.Python.3.12 -e --source winget
```

### 2. 安装 yt-dlp 和 FFmpeg

在 PowerShell 中执行：

```powershell
winget install --id yt-dlp.yt-dlp -e --source winget
winget install --id Gyan.FFmpeg -e --source winget
```

安装完成后 **关闭并重新打开终端**，然后确认：

```powershell
yt-dlp --version
ffmpeg -version
```

也可以直接运行：

```text
windows\install_dependencies.bat
```

### 3. 运行程序

把整个项目文件夹复制到 Windows，保留目录结构：

```text
yt-dlp-gui\
├─ yt_dlp_gui.py
├─ assets\
└─ windows\
```

双击：

```text
windows\run_source.bat
```

或者在该目录打开 CMD/PowerShell：

```powershell
python yt_dlp_gui.py
```

---

## 方式二：打包成 Windows .exe（推荐）

**必须在 Windows 上打包。** PyInstaller 不支持从 Linux 交叉编译 Windows 程序。

### 1. 安装 Python、yt-dlp、FFmpeg

同上。

### 2. 安装 PyInstaller

```powershell
python -m pip install --upgrade pyinstaller
```

### 3. 执行打包脚本

双击：

```text
windows\build_windows.bat
```

脚本会自动：

- 打包为 **onedir** 版本（启动快）
- 使用卡皮巴拉 `.ico` 作为 exe 图标
- 把 `assets/` 一起打包
- 在桌面创建“卡皮巴拉视频下载器”快捷方式

输出位置：

```text
dist\CapybaraDownloader\CapybaraDownloader.exe
```

### 4. 如果快捷方式没有自动创建

在项目目录打开 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File windows\create_shortcut.ps1
```

### 5. 固定到任务栏

启动程序后，在任务栏找到卡皮巴拉图标：

**右键 → 固定到任务栏 / Pin to taskbar**

---

## 便携版（可选）

如果希望把 yt-dlp 和 FFmpeg 一起带到别的电脑：

1. 下载 Windows 版 `yt-dlp.exe` 和 `ffmpeg.exe`
2. 放到项目根目录，或放到生成的 `CapybaraDownloader.exe` 旁边
3. 程序会优先查找同目录下的 `yt-dlp.exe` / `ffmpeg.exe`

也可以重新执行 `build_windows.bat`，脚本会把根目录下的这两个 exe 自动复制进发布目录。

---

## 单文件 exe（可选，启动较慢）

如果更在意“只有一个 exe 文件”，运行：

```text
windows\build_windows_onefile.bat
```

输出：

```text
dist\CapybaraDownloader.exe
```

单文件模式每次启动都要解压运行时，启动会比 onedir 模式慢。

---

## 文件说明

| 文件 | 用途 |
|---|---|
| `windows\install_dependencies.bat` | 用 winget 安装 Python / yt-dlp / FFmpeg |
| `windows\run_source.bat` | 直接运行 Python 源码 |
| `windows\build_windows.bat` | 打包为启动较快的 onedir 版 |
| `windows\build_windows_onefile.bat` | 打包为单文件 exe |
| `windows\create_shortcut.ps1` | 创建桌面快捷方式 |
| `assets\capybara.ico` | Windows exe 图标 |

---

## 常见问题

### 双击 exe 出现“Windows 已保护你的电脑”

这是 SmartScreen 对未签名程序的提示。点击“更多信息”→“仍要运行”。

### 提示找不到 yt-dlp

确认：

```powershell
where yt-dlp
```

如果没有输出，重新执行：

```powershell
winget install --id yt-dlp.yt-dlp -e --source winget
```

或者把 `yt-dlp.exe` 放到程序目录旁边。

### 提示找不到 ffmpeg

```powershell
where ffmpeg
```

如果没有输出：

```powershell
winget install --id Gyan.FFmpeg -e --source winget
```

安装后重新打开终端，或重启电脑。

### 设置保存在哪里

Windows 下为：

```text
%APPDATA%\yt-dlp-gui\settings.json
```

### 更新 yt-dlp

```powershell
winget upgrade --id yt-dlp.yt-dlp -e
```

如果是单独下载的 `yt-dlp.exe`：

```powershell
yt-dlp -U
```

---

## 主要参考

- [Python for Windows](https://www.python.org/downloads/windows/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [FFmpeg](https://ffmpeg.org/download.html)
- [winget yt-dlp 包](https://winget.ragerworks.com/package/yt-dlp.yt-dlp)
- [winget FFmpeg 清单](https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Gyan/FFmpeg)
