# Building a standalone app

This produces a double-clickable desktop app with no Python install required,
using [PyInstaller](https://pyinstaller.org/).

## 1. Install build dependencies

From a clean virtual environment, on the machine/OS you want to build for
(PyInstaller does not cross-compile -- build on macOS to get a `.app`, on
Windows to get a `.exe`, etc.):

```sh
pip install -e ".[dev]"
pip install pyinstaller
```

## 2. Build

```sh
pyinstaller frame_palette_app.spec
```

This bundles the engine, the FastAPI backend, the `ui/` frontend, and the
pywebview shell into one artifact under `dist/`:

- **macOS**: `dist/FramePalette.app`
- **Windows/Linux**: `dist/FramePalette/FramePalette(.exe)`

`build/` and `dist/` are git-ignored -- rerun step 2 any time to rebuild;
delete both directories first for a fully clean build.

## 3. Run it

- **macOS**: double-click `dist/FramePalette.app`. Since the app isn't
  signed/notarized, the first launch may need **right-click -> Open** to get
  past Gatekeeper (System Settings -> Privacy & Security also offers an
  "Open Anyway" button after the first blocked attempt).
- **Windows/Linux**: run the executable in `dist/FramePalette/` directly.

The app starts its own local backend on an unused port and opens a native
window pointed at it -- no terminal, no browser tab, no manual server step.

## Notes

- `frame_palette_app.spec` bundles `ui/` as a data directory and pulls in
  `numpy`, `opencv-python` (`cv2`), `Pillow`, `fastapi`, `uvicorn`, and
  `pywebview` (plus a few uvicorn hidden imports it only resolves at
  runtime) via `PyInstaller.utils.hooks.collect_all`.
- `bundle_identifier` in the spec (`com.ucc-et.frame-palette`) and `icon`
  (currently unset) are placeholders -- swap in a real reverse-DNS id and an
  `.icns`/`.ico` file if you want a custom app icon or plan to distribute
  the app more widely.
