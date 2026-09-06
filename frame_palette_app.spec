# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the Frame Palette desktop app.

Bundles the pywebview shell (``main.py`` -> ``frame_palette.shell.main``),
the FastAPI backend, the engine, and the static ``ui/`` frontend into a
single windowed executable (and, on macOS, a proper ``.app`` bundle).

Build with:
    pyinstaller frame_palette_app.spec

Output lands in ``dist/`` (``dist/FramePalette.app`` on macOS,
``dist/FramePalette/FramePalette`` elsewhere). Both ``build/`` and
``dist/`` are git-ignored -- this file is the only build artifact meant
to be committed.
"""

import sys

from PyInstaller.utils.hooks import collect_all

APP_NAME = "FramePalette"

# Each of these ships its own compiled extensions and/or data files that
# PyInstaller's static import analysis can't always see on its own.
_COLLECT_PACKAGES = ["numpy", "cv2", "PIL", "fastapi", "uvicorn", "webview"]

datas = [("ui", "ui")]
binaries = []
hiddenimports = [
    # uvicorn picks these at runtime based on what's installed, so static
    # analysis misses them without a hint.
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

for package in _COLLECT_PACKAGES:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    except Exception as exc:  # pragma: no cover - build-time diagnostics only
        # collect_all() walks the installed package to discover its
        # submodules/data files; on a package with platform-conditional
        # imports (pywebview's macOS/GTK/Qt backends) that walk can raise
        # on a given build machine even though `import <package>` itself
        # works fine at runtime. Don't let that silently drop the package
        # from the bundle -- fall back to just hard-requiring its name and
        # print why, so a broken build says something instead of failing
        # at app launch with a bare ModuleNotFoundError.
        print(f"[frame_palette_app.spec] collect_all({package!r}) raised {exc!r}; "
              f"falling back to a bare hiddenimport for {package!r}")
        pkg_datas, pkg_binaries, pkg_hiddenimports = [], [], []
    if package not in pkg_hiddenimports:
        pkg_hiddenimports.append(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

# pywebview picks its native backend (Cocoa/GTK/Qt/WinForms) via nested
# try/except imports inside webview/guilib.py. PyInstaller's static
# analysis only descends into that file *after* it has already located
# the `webview` package itself, so force-including the one backend this
# platform actually needs closes that gap directly instead of relying on
# collect_all()/modulegraph to infer it.
if sys.platform == "darwin":
    hiddenimports.append("webview.platforms.cocoa")
elif sys.platform == "win32":
    hiddenimports.append("webview.platforms.winforms")
else:
    hiddenimports += ["webview.platforms.gtk", "webview.platforms.qt"]

print(f"[frame_palette_app.spec] hiddenimports includes 'webview': {'webview' in hiddenimports}")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name=f"{APP_NAME}.app",
        icon=None,
        bundle_identifier="com.ucc-et.frame-palette",
        info_plist={
            "CFBundleName": "Video to Stripes",
            "CFBundleDisplayName": "Video to Stripes",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
