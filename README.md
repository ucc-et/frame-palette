# FramePalette

Turn any video into a stripe poster: one stripe per sampled frame, colored by
that frame's average (or median) color, laid out vertically or horizontally
into a single downloadable image. Feed it a movie, a music video, a home
recording -- the output is a visual fingerprint of how its color palette
changes from start to end.

![FramePalette desktop app with a video loaded and a live stripe preview](docs/screenshots/ui-preview.png)

Loading a video shows its thumbnail and metadata, scrubs frame-by-frame, and
live-updates a low-res preview as you adjust settings -- before generating
the full-resolution poster.

## Download

Prebuilt apps for macOS, Windows, and Linux are attached to every release on
the [Releases page](../../releases). Unzip and run -- no Python install
needed. The macOS build is for Apple Silicon Macs (M1 and later).

### Opening the app on macOS

Until a release is signed and notarized by Apple (see
[`BUILDING.md`](BUILDING.md#signing-and-notarizing-the-macos-app)), macOS
blocks it on first launch with *"Apple could not verify 'FramePalette' is
free of malware..."*. You only have to get past this once per download:

1. Unzip `FramePalette-macOS.zip` and move `FramePalette.app` to
   **Applications**.
2. Double-click it. When the warning appears, click **Done** (not *Move to
   Trash*).
3. Open **System Settings -> Privacy & Security**, scroll down to
   **Security**, and click **Open Anyway** next to the message about
   FramePalette. Confirm with your password or Touch ID, then click **Open
   Anyway** once more.

From then on it opens like any other app. (On macOS 15 Sequoia and later,
the old *right-click -> Open* shortcut no longer skips this check.)

Alternatively, remove the "downloaded from the internet" flag that triggers
the check, from Terminal:

```sh
xattr -dr com.apple.quarantine /Applications/FramePalette.app
```

## What's in this repository

- **`frame_palette/core.py`, `frame_palette/video.py`** -- the engine.
  UI-agnostic video sampling and poster-rendering logic, driven by a single
  `PosterSettings` object (`frame_palette/settings.py`).
- **`frame_palette/cli.py`** -- a command-line tool (`frame-palette-cli`) for
  scripting poster generation without any UI.
- **`frame_palette/server.py`** -- a FastAPI backend exposing the engine over
  HTTP: video upload/scrubbing, a live low-res preview, and background poster
  generation jobs.
- **`ui/`** -- a small dependency-free HTML/CSS/JS frontend that talks to the
  backend.
- **`frame_palette/shell.py`** -- a desktop shell (`pywebview`) that runs the
  backend locally and opens the UI in a native window, so the whole thing
  behaves like a normal downloadable app rather than "start a server, open a
  browser tab."
- **`frame_palette_app.spec`** -- a PyInstaller spec that packages all of the
  above into a single double-clickable app. See [`BUILDING.md`](BUILDING.md)
  for building it yourself, or [download](#download) a prebuilt one --
  `.github/workflows/release.yml` builds a fresh macOS/Windows/Linux release
  automatically on every merge to `main`.

## Running it locally

Requires Python 3.10+.

```sh
git clone <this repo>
cd frame-palette
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

**Desktop app** (recommended -- opens a native window, no terminal/browser
juggling):

```sh
python3 main.py
```

**Backend + browser**, useful for frontend development (auto-reloads on code
changes):

```sh
uvicorn frame_palette.server:app --reload
```

Then open `http://127.0.0.1:8000` in a browser.

**Command line**, for scripting or batch use:

```sh
frame-palette-cli render my-video.mp4 --output poster.png --orientation vertical
```

Run `frame-palette-cli --help` for the full set of options (color mode,
smoothing, stripe width, output size and format, and more -- the same
settings the UI exposes).

**Tests**:

```sh
pytest
```

## Example: results

The same video rendered as vertical stripes with a title band, and again as
horizontal stripes:

<table>
<tr>
<td><img src="docs/screenshots/example-poster-vertical.png" alt="Example vertical stripe poster" width="360"></td>
<td><img src="docs/screenshots/example-poster-horizontal.png" alt="Example horizontal stripe poster" width="480"></td>
</tr>
<tr>
<td align="center">Vertical, with title</td>
<td align="center">Horizontal</td>
</tr>
</table>

Each stripe is one sampled frame's average color; smoothing blends
neighboring stripes together to reduce flicker from noisy footage, and
stripe width, sample rate, and output size are all adjustable per render.
