"""Desktop shell for Frame Palette.

Wraps the FastAPI backend (``frame_palette.server``) and the ``ui/``
frontend in a native window using pywebview, so the app can be launched
as a normal desktop program instead of "run a server, open a browser".

The backend runs in a background thread on a locally-bound free port;
pywebview then points its window at that local server. A small
``Api`` class is exposed to the frontend as ``window.pywebview.api`` so
JS can trigger native "open video" / "save poster" file dialogs -- the
two things a browser sandbox cannot do on its own. The method names
here (``open_video_dialog``, ``save_path_dialog``) are load-bearing:
``ui/app.js`` already calls them by these exact names.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Optional, Sequence, Union

import uvicorn
import webview

from frame_palette.server import app as fastapi_app

WINDOW_TITLE = "Video to Stripes"
DEFAULT_WIDTH = 1240
DEFAULT_HEIGHT = 900
MIN_SIZE = (960, 700)
BACKGROUND_COLOR = "#14161a"

VIDEO_FILE_TYPES = ("Video Files (*.mp4;*.mov;*.m4v;*.avi;*.mkv;*.webm)", "All files (*.*)")
IMAGE_FILE_TYPES = ("PNG Image (*.png)", "JPEG Image (*.jpg;*.jpeg)", "All files (*.*)")
DEFAULT_SAVE_NAME = "palette.png"

FileDialogResult = Union[Sequence[str], str, None]


def _find_free_port() -> int:
    """Ask the OS for an unused TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 10.0) -> None:
    """Block until something is accepting connections on ``port``, or raise."""
    deadline = time.monotonic() + timeout
    last_error: Optional[OSError] = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"Backend server did not start on port {port} within {timeout}s") from last_error


def _run_server(port: int) -> None:
    """Run the FastAPI app with uvicorn. Intended to run on a daemon thread."""
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
    uvicorn.Server(config).run()


def _first_path(result: FileDialogResult) -> Optional[str]:
    """Normalize a pywebview file-dialog result to a single path or None.

    ``create_file_dialog`` returns ``None``/``()`` when the user cancels,
    a sequence of paths for OPEN dialogs, and (depending on platform/
    pywebview version) either a bare string or a one-item sequence for
    SAVE dialogs. This collapses all of those into one shape.
    """
    if not result:
        return None
    if isinstance(result, (list, tuple)):
        return result[0] if result else None
    return result


class Api:
    """Methods exposed to the frontend as ``window.pywebview.api.<name>``."""

    def open_video_dialog(self) -> Optional[str]:
        """Show a native "open file" dialog scoped to video files."""
        window = webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=VIDEO_FILE_TYPES,
        )
        return _first_path(result)

    def save_path_dialog(self, suggested_name: str = DEFAULT_SAVE_NAME) -> Optional[str]:
        """Show a native "save file" dialog scoped to image files."""
        window = webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=suggested_name,
            file_types=IMAGE_FILE_TYPES,
        )
        return _first_path(result)


def main() -> None:
    """Start the backend in the background and open the desktop window."""
    port = _find_free_port()
    server_thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    server_thread.start()
    _wait_for_server(port)

    webview.create_window(
        WINDOW_TITLE,
        url=f"http://127.0.0.1:{port}/",
        js_api=Api(),
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
        min_size=MIN_SIZE,
        background_color=BACKGROUND_COLOR,
    )
    webview.start()


if __name__ == "__main__":
    main()
