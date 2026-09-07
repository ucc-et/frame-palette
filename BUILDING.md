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
pywebview shell into a single onefile artifact under `dist/`:

- **macOS**: `dist/FramePalette.app` (a proper app bundle wrapping the
  onefile executable)
- **Windows**: `dist/FramePalette.exe` (one file, nothing else needed)
- **Linux**: `dist/FramePalette` (one file; `chmod +x` it if it isn't
  already executable)

`build/` and `dist/` are git-ignored -- rerun step 2 any time to rebuild;
delete both directories first for a fully clean build.

## 3. Run it

- **macOS**: double-click `dist/FramePalette.app`. Since the app isn't
  signed/notarized, the first launch may need **right-click -> Open** to get
  past Gatekeeper (System Settings -> Privacy & Security also offers an
  "Open Anyway" button after the first blocked attempt).
- **Windows/Linux**: run `dist/FramePalette.exe` / `dist/FramePalette`
  directly.

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

## Automated releases

`.github/workflows/release.yml` runs this same build automatically for
macOS, Windows, and Linux every time a merge lands on `main` (not on pull
requests), and publishes the three archives as assets on a new GitHub
Release. It pins Python 3.11 for the build rather than whatever's newest --
see the comment in the workflow for why. If you push a version bump, it
shows up in the next release's tag (`v<version>-<run number>`).
