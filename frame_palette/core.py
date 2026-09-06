"""Poster generation: turn a sequence of frame colors into a stripe image.

This module is deliberately UI-agnostic -- it knows nothing about Tkinter,
HTTP, or any particular caller. ``read_frame_colors`` and
``build_palette_image`` are the two building blocks; ``generate_palette_image``
and ``save_palette_image`` compose them for the common case of "give me a
video, give me back a poster".
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from frame_palette.settings import PosterSettings
from frame_palette.video import estimate_sampled_frame_count, get_metadata, iter_frames

ProgressCallback = Callable[[int, int | None, str], None]

_SMOOTHING_WINDOWS: dict[str, int] = {"off": 1, "low": 3, "medium": 7, "high": 15}


def _normalize_rgb(color: Iterable[float]) -> tuple[int, int, int]:
    blue, green, red = color
    return int(red), int(green), int(blue)


def _frame_color(frame: np.ndarray, color_mode: str) -> tuple[int, int, int]:
    if color_mode == "median":
        pixel = np.median(frame.reshape(-1, 3), axis=0)
    else:
        pixel = frame.mean(axis=(0, 1))
    return _normalize_rgb(pixel)


def _apply_smoothing(colors: list[tuple[int, int, int]], smoothing: str) -> list[tuple[int, int, int]]:
    """Average each color with its neighbors to reduce frame-to-frame flicker."""
    window = _SMOOTHING_WINDOWS.get(smoothing, 1)
    if window <= 1 or len(colors) < 2:
        return colors

    array = np.array(colors, dtype=np.float64)
    kernel = np.ones(window) / window
    pad = window // 2
    padded = np.pad(array, ((pad, pad), (0, 0)), mode="edge")
    smoothed = np.stack(
        [np.convolve(padded[:, channel], kernel, mode="valid") for channel in range(3)],
        axis=1,
    )
    return [tuple(int(round(value)) for value in row) for row in smoothed]


def read_frame_colors(
    video_path: str | Path,
    settings: PosterSettings | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[tuple[int, int, int]]:
    """Read (a possibly trimmed/sampled range of) a video's frames and return one color per frame."""
    settings = settings or PosterSettings()

    metadata = get_metadata(video_path)
    total_estimate = estimate_sampled_frame_count(
        metadata,
        start_time=settings.start_time,
        end_time=settings.end_time,
        sample_every=settings.sample_every,
    )

    frame_colors: list[tuple[int, int, int]] = []
    processed = 0

    for frame in iter_frames(
        video_path,
        start_time=settings.start_time,
        end_time=settings.end_time,
        sample_every=settings.sample_every,
    ):
        frame_colors.append(_frame_color(frame, settings.color_mode))
        processed += 1

        if progress_callback is not None:
            message = (
                f"Processed frame {processed}"
                if not total_estimate
                else f"Processed frame {processed} of {total_estimate}"
            )
            progress_callback(processed, total_estimate, message)

    if not frame_colors:
        raise ValueError(f"No frames could be read from: {video_path}")

    if settings.smoothing != "off":
        frame_colors = _apply_smoothing(frame_colors, settings.smoothing)

    return frame_colors


def _load_title_font(font_size: int) -> "ImageFont.ImageFont":
    from PIL import ImageFont

    candidate_paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/System/Library/Fonts/Supplemental/Verdana.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for font_path in candidate_paths:
        try:
            return ImageFont.truetype(font_path, font_size)
        except OSError:
            continue

    return ImageFont.load_default()


def build_palette_image(colors: np.ndarray, settings: PosterSettings, title: str = "") -> "Image.Image":
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Pillow is required to generate poster images. Install dependencies with 'python3 -m pip install -r requirements.txt'."
        ) from exc

    if colors.size == 0:
        raise ValueError("No colors were provided")

    stripes = np.repeat(colors, settings.stripe_width, axis=0)

    if settings.orientation == "horizontal":
        # Stripes run left-to-right as horizontal bands; "image_height" is
        # reused as the fixed cross-axis thickness (here, the poster width).
        image_array = np.tile(stripes[:, np.newaxis, :], (1, settings.image_height, 1))
        image = Image.fromarray(image_array, mode="RGB")
        if image.height > settings.max_output_width:
            scale = settings.max_output_width / image.height
            resized_height = max(1, int(image.height * scale))
            image = image.resize((settings.image_height, resized_height), Image.LANCZOS)
    else:
        image_array = np.tile(stripes[np.newaxis, :, :], (settings.image_height, 1, 1))
        image = Image.fromarray(image_array, mode="RGB")
        if image.width > settings.max_output_width:
            scale = settings.max_output_width / image.width
            resized_width = max(1, int(image.width * scale))
            image = image.resize((resized_width, settings.image_height), Image.LANCZOS)

    if settings.blur > 0:
        from PIL import ImageFilter

        image = image.filter(ImageFilter.GaussianBlur(radius=settings.blur))

    if not title.strip():
        return image

    title_band_height = settings.title_band_height
    canvas = Image.new("RGB", (image.width, image.height + title_band_height), settings.background_color)
    canvas.paste(image, (0, 0))

    draw = ImageDraw.Draw(canvas)
    font = _load_title_font(settings.title_font_size)
    text = title.strip()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (canvas.width - text_width) // 2
    y = (
        image.height
        + settings.title_margin
        + ((title_band_height - settings.title_margin * 2 - text_height) // 2)
        - bbox[1]
    )
    draw.text((x, y), text, fill=settings.title_color, font=font)

    return canvas


def generate_palette_image(
    video_path: str | Path,
    settings: PosterSettings,
    title: str = "",
    progress_callback: ProgressCallback | None = None,
) -> "Image.Image":
    colors = read_frame_colors(video_path, settings=settings, progress_callback=progress_callback)
    color_array = np.array(colors, dtype=np.uint8)
    return build_palette_image(color_array, settings, title=title)


def save_palette_image(
    video_path: str | Path,
    output_path: str | Path,
    settings: PosterSettings,
    title: str = "",
    progress_callback: ProgressCallback | None = None,
) -> Path:
    image = generate_palette_image(video_path, settings, title=title, progress_callback=progress_callback)
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.output_format == "jpg":
        if target_path.suffix.lower() not in (".jpg", ".jpeg"):
            target_path = target_path.with_suffix(".jpg")
        image.convert("RGB").save(target_path, format="JPEG", quality=settings.jpg_quality)
    else:
        if target_path.suffix.lower() != ".png":
            target_path = target_path.with_suffix(".png")
        image.save(target_path, format="PNG")

    return target_path


def read_colors_from_csv(csv_file: str | Path) -> np.ndarray:
    """Read a ``frame,R,G,B`` CSV (as produced by the legacy extraction script)."""
    import csv

    colors: list[list[int]] = []
    with open(csv_file, "r", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        for row in reader:
            colors.append([int(row["R"]), int(row["G"]), int(row["B"])])
    return np.array(colors, dtype=np.uint8)
