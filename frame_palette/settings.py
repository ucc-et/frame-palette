from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

ColorMode = Literal["average", "median"]
Smoothing = Literal["off", "low", "medium", "high"]
Orientation = Literal["vertical", "horizontal"]
OutputFormat = Literal["png", "jpg"]

COLOR_MODES: tuple[str, ...] = get_args(ColorMode)
SMOOTHING_LEVELS: tuple[str, ...] = get_args(Smoothing)
ORIENTATIONS: tuple[str, ...] = get_args(Orientation)
OUTPUT_FORMATS: tuple[str, ...] = get_args(OutputFormat)


@dataclass(slots=True)
class PosterSettings:
    """All knobs that affect how a poster is built from a video.

    Kept intentionally UI-agnostic: this is the shared contract between the
    CLI, the (future) HTTP API, and any GUI shell built on top of the
    engine, so every field here should be something a caller can set from a
    plain JSON payload or argparse namespace.
    """

    # --- stripe / canvas geometry ---
    stripe_width: int = 2
    image_height: int = 1200
    max_output_width: int = 8000
    orientation: Orientation = "vertical"

    # --- color extraction ---
    color_mode: ColorMode = "average"
    smoothing: Smoothing = "off"
    blur: int = 0

    # --- frame sampling / trimming ---
    sample_every: int = 1
    start_time: float | None = None
    end_time: float | None = None

    # --- title band ---
    title_band_height: int = 180
    title_font_size: int = 54
    title_margin: int = 28
    background_color: tuple[int, int, int] = (0, 0, 0)
    title_color: tuple[int, int, int] = (255, 255, 255)

    # --- export ---
    output_format: OutputFormat = "png"
    jpg_quality: int = 92

    def __post_init__(self) -> None:
        if self.stripe_width < 1:
            raise ValueError("stripe_width must be at least 1")
        if self.image_height < 1:
            raise ValueError("image_height must be at least 1")
        if self.max_output_width < 1:
            raise ValueError("max_output_width must be at least 1")
        if self.orientation not in ORIENTATIONS:
            raise ValueError(f"orientation must be one of {ORIENTATIONS}")
        if self.color_mode not in COLOR_MODES:
            raise ValueError(f"color_mode must be one of {COLOR_MODES}")
        if self.smoothing not in SMOOTHING_LEVELS:
            raise ValueError(f"smoothing must be one of {SMOOTHING_LEVELS}")
        if self.blur < 0:
            raise ValueError("blur must be zero or positive")
        if self.sample_every < 1:
            raise ValueError("sample_every must be at least 1")
        if self.start_time is not None and self.start_time < 0:
            raise ValueError("start_time must be zero or positive")
        if self.end_time is not None and self.end_time < 0:
            raise ValueError("end_time must be zero or positive")
        if self.start_time is not None and self.end_time is not None and self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        if self.output_format not in OUTPUT_FORMATS:
            raise ValueError(f"output_format must be one of {OUTPUT_FORMATS}")
        if not (1 <= self.jpg_quality <= 100):
            raise ValueError("jpg_quality must be between 1 and 100")
