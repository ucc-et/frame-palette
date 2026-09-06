"""Video I/O: metadata, thumbnails, and frame iteration.

Isolated from color/poster logic so it can be reused (and tested) on its
own -- a GUI needs metadata and a thumbnail the moment a video is picked,
long before anyone hits "Generate".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import cv2
import numpy as np

if TYPE_CHECKING:
    from PIL.Image import Image


@dataclass(slots=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    frame_count: int
    duration_seconds: float


def _open_capture(video_path: str | Path) -> cv2.VideoCapture:
    path = str(video_path)
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {path}")
    return capture


def get_metadata(video_path: str | Path) -> VideoMetadata:
    capture = _open_capture(video_path)
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_seconds = frame_count / fps if fps else 0.0
    finally:
        capture.release()

    return VideoMetadata(
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        duration_seconds=duration_seconds,
    )


def get_thumbnail(video_path: str | Path, max_size: tuple[int, int] = (286, 144)) -> "Image | None":
    """Return a Pillow image of the first frame, or None if it can't be read."""
    from PIL import Image

    capture = _open_capture(video_path)
    try:
        success, frame = capture.read()
    finally:
        capture.release()

    if not success:
        return None

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(frame_rgb)
    image.thumbnail(max_size, Image.LANCZOS)
    return image


def iter_frames(
    video_path: str | Path,
    start_time: float | None = None,
    end_time: float | None = None,
    sample_every: int = 1,
) -> Iterator[np.ndarray]:
    """Yield BGR frames (as read by OpenCV) from ``video_path``.

    ``start_time``/``end_time`` are seconds into the video; ``sample_every``
    keeps 1 out of every N frames within that range (1 = every frame).
    """
    sample_every = max(1, int(sample_every))
    capture = _open_capture(video_path)

    try:
        if start_time:
            capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, start_time) * 1000.0)

        index = 0
        while True:
            success, frame = capture.read()
            if not success:
                break

            if end_time is not None:
                position_ms = capture.get(cv2.CAP_PROP_POS_MSEC)
                if position_ms and position_ms / 1000.0 > end_time:
                    break

            if index % sample_every == 0:
                yield frame

            index += 1
    finally:
        capture.release()


def estimate_sampled_frame_count(
    metadata: VideoMetadata,
    start_time: float | None = None,
    end_time: float | None = None,
    sample_every: int = 1,
) -> int | None:
    """Best-effort count of frames ``iter_frames`` will yield, for progress bars."""
    total = metadata.frame_count or None
    if not total:
        return None

    fps = metadata.fps or 0.0
    start_frame = 0
    if start_time and fps:
        start_frame = int(start_time * fps)

    end_frame = total
    if end_time is not None and fps:
        end_frame = min(total, int(end_time * fps))

    remaining = max(0, end_frame - start_frame)
    if remaining == 0:
        return None

    sample_every = max(1, int(sample_every))
    return (remaining + sample_every - 1) // sample_every
