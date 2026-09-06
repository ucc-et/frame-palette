"""Frame palette poster generation engine.

This package is the framework-agnostic core of Frame Palette: given a video
file, it extracts one representative color per frame and renders those
colors as a stripe poster. It has no dependency on any particular UI
(Tkinter, a web frontend, a CLI) so it can be reused from any of them.
"""

from frame_palette.settings import PosterSettings
from frame_palette.video import VideoMetadata

__all__ = ["PosterSettings", "VideoMetadata"]
