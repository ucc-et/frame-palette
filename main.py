"""Repo-root entry point for the packaged desktop app.

Kept as a thin top-level module (rather than only ``frame_palette.__main__``)
because PyInstaller specs point at a single script file -- see
``frame_palette_app.spec``, which builds from ``main.py``.
"""

from __future__ import annotations

from frame_palette.shell import main

if __name__ == "__main__":
    main()
