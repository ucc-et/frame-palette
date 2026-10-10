# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the Frame Palette desktop app.

Bundles the pywebview shell (``main.py`` -> ``frame_palette.shell.main``),
the FastAPI backend, the engine, and the static ``ui/`` frontend into a
single windowed executable (and, on macOS, a proper ``.app`` bundle).

Build with:
    pyinstaller frame_palette_app.spec

Output lands in ``dist/`` (``dist/FramePalette.app`` on macOS,
``dist/FramePalette.exe`` / ``dist/FramePalette`` elsewhere). Both
``build/`` and ``dist/`` are git-ignored -- this file is the only build
artifact meant to be committed.

macOS code signing is driven by environment variables so the same spec
works for local, unsigned CI, and signed CI builds:

- ``MACOS_CODESIGN_IDENTITY`` unset (the default): every binary and the
  ``.app`` are ad-hoc signed. Runs locally, but a downloaded copy trips
  Gatekeeper's "could not verify ... free of malware" prompt.
- ``MACOS_CODESIGN_IDENTITY="Developer ID Application: ..."`` (or that
  certificate's SHA-1 hash): PyInstaller signs everything with that
  identity, hardened runtime enabled, using
  ``packaging/macos/entitlements.plist``. The result can then be
  notarized -- see the release workflow and BUILDING.md.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_all

APP_NAME = "FramePalette"

IS_MACOS = sys.platform == "darwin"
CODESIGN_IDENTITY = os.environ.get("MACOS_CODESIGN_IDENTITY") or None
ENTITLEMENTS_FILE = os.path.join("packaging", "macos", "entitlements.plist") if IS_MACOS else None

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
if IS_MACOS:
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

if IS_MACOS:
    # onedir inside the .app, not onefile: a onefile .app re-extracts the
    # whole bundle to a temp dir on every launch, which is slow and is
    # exactly what Gatekeeper/notarization dislike -- PyInstaller 6 warns
    # that combination "clashes with macOS's security" and 7.0 will reject
    # it outright. With onedir every dylib sits signed inside the bundle.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # UPX-packed Mach-O binaries break code signing
        console=False,
        codesign_identity=CODESIGN_IDENTITY,
        entitlements_file=ENTITLEMENTS_FILE,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=APP_NAME,
    )
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=None,
        bundle_identifier="com.ucc-et.frame-palette",
        info_plist={
            "CFBundleName": "FramePalette",
            "CFBundleDisplayName": "FramePalette",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
else:
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
