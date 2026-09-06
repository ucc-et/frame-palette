from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

import cv2
import numpy as np
import pytest


def _write_video(path: Path, frames: Sequence[np.ndarray], fps: float = 10.0) -> Path:
    height, width = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Could not open cv2.VideoWriter -- no codec backend available in this environment")
    try:
        for frame in frames:
            writer.write(frame)
    finally:
        writer.release()
    return path


@pytest.fixture
def make_video_from_frames(tmp_path: Path) -> Callable[..., Path]:
    """Factory fixture: make_video_from_frames([frame, frame, ...], fps=10) -> Path to an mp4."""

    def _factory(frames: Sequence[np.ndarray], fps: float = 10.0) -> Path:
        return _write_video(tmp_path / "fixture.mp4", frames, fps=fps)

    return _factory


@pytest.fixture
def make_video(make_video_from_frames: Callable[..., Path]) -> Callable[..., Path]:
    """Factory fixture: make_video([(b,g,r), ...], fps=10, size=(64,48)) -> Path to an mp4 of solid-color frames."""

    def _factory(
        frame_colors_bgr: Sequence[tuple[int, int, int]],
        fps: float = 10.0,
        size: tuple[int, int] = (64, 48),
    ) -> Path:
        width, height = size
        frames = []
        for color in frame_colors_bgr:
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :] = color
            frames.append(frame)
        return make_video_from_frames(frames, fps=fps)

    return _factory


@pytest.fixture
def solid_color_video(make_video: Callable[..., Path]) -> Path:
    """A 5-frame, 5fps video stepping through distinct solid BGR colors."""
    colors = [
        (0, 0, 200),  # -> RGB red-ish
        (0, 200, 0),  # -> RGB green-ish
        (200, 0, 0),  # -> RGB blue-ish
        (0, 200, 200),  # -> RGB yellow-ish
        (200, 200, 0),  # -> RGB cyan-ish
    ]
    return make_video(colors, fps=5.0, size=(64, 48))
