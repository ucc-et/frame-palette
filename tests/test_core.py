from __future__ import annotations

import csv

import numpy as np
import pytest
from PIL import Image

from frame_palette import core
from frame_palette.settings import PosterSettings


# --- pure aggregation helpers (exercised directly, no video I/O involved) ---


def test_frame_color_average_mode_returns_mean_rgb():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[:, :] = (10, 20, 30)  # BGR
    assert core._frame_color(frame, "average") == (30, 20, 10)  # RGB


def test_frame_color_median_mode_ignores_a_small_outlier_patch():
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    frame[:, :] = (10, 10, 10)  # BGR, uniform dark
    frame[0:3, 0:3] = (250, 250, 250)  # tiny bright outlier corner

    median_color = core._frame_color(frame, "median")
    average_color = core._frame_color(frame, "average")

    assert median_color == (10, 10, 10)
    # the outlier patch should pull the average away from the median
    assert average_color[0] > median_color[0]


def test_apply_smoothing_dampens_a_single_frame_spike():
    baseline = [(50, 50, 50)] * 10
    colors = list(baseline)
    colors[5] = (250, 250, 250)  # one-frame spike

    smoothed = core._apply_smoothing(colors, "medium")

    assert len(smoothed) == len(colors)
    # the spike should be pulled toward its neighbors, not eliminate them
    assert smoothed[5][0] < colors[5][0]
    assert smoothed[5][0] > baseline[0][0]


def test_apply_smoothing_off_is_a_no_op():
    colors = [(1, 2, 3), (4, 5, 6)]
    assert core._apply_smoothing(colors, "off") == colors


# --- build_palette_image: geometry, orientation, blur, title ---


def _solid_colors(n: int) -> np.ndarray:
    return np.array([[i, i, i] for i in range(n)], dtype=np.uint8)


def test_build_palette_image_vertical_dimensions():
    settings = PosterSettings(stripe_width=3, image_height=40, orientation="vertical")
    image = core.build_palette_image(_solid_colors(10), settings)
    assert image.width == 10 * 3
    assert image.height == 40


def test_build_palette_image_horizontal_dimensions():
    settings = PosterSettings(stripe_width=3, image_height=40, orientation="horizontal")
    image = core.build_palette_image(_solid_colors(10), settings)
    assert image.width == 40
    assert image.height == 10 * 3


def test_build_palette_image_respects_max_output_width():
    settings = PosterSettings(stripe_width=10, image_height=20, max_output_width=50, orientation="vertical")
    image = core.build_palette_image(_solid_colors(20), settings)  # would be 200px wide uncapped
    assert image.width <= 50


def test_build_palette_image_blur_reduces_high_frequency_variance():
    colors = np.array([[0, 0, 0], [255, 255, 255]] * 20, dtype=np.uint8)
    settings_sharp = PosterSettings(stripe_width=4, image_height=20, blur=0)
    settings_blurred = PosterSettings(stripe_width=4, image_height=20, blur=6)

    sharp = np.asarray(core.build_palette_image(colors, settings_sharp))
    blurred = np.asarray(core.build_palette_image(colors, settings_blurred))

    assert blurred.astype(np.float64).std() < sharp.astype(np.float64).std()


def test_build_palette_image_with_title_adds_a_band_below():
    settings = PosterSettings(stripe_width=2, image_height=20, title_band_height=50)
    without_title = core.build_palette_image(_solid_colors(5), settings)
    with_title = core.build_palette_image(_solid_colors(5), settings, title="My Poster")
    assert with_title.height == without_title.height + settings.title_band_height
    assert with_title.width == without_title.width


def test_build_palette_image_rejects_empty_colors():
    settings = PosterSettings()
    with pytest.raises(ValueError):
        core.build_palette_image(np.empty((0, 3), dtype=np.uint8), settings)


# --- read_frame_colors / generate / save: exercised through real (synthetic) video files ---


def test_read_frame_colors_returns_one_color_per_frame(solid_color_video):
    settings = PosterSettings(color_mode="average")
    colors = core.read_frame_colors(solid_color_video, settings=settings)
    assert len(colors) == 5
    # first fixture frame is solid BGR (0,0,200) -> RGB, dominant channel should be red
    assert colors[0][0] > colors[0][1]
    assert colors[0][0] > colors[0][2]


def test_read_frame_colors_reports_progress_to_completion(solid_color_video):
    settings = PosterSettings()
    updates: list[tuple[int, int | None]] = []
    core.read_frame_colors(
        solid_color_video,
        settings=settings,
        progress_callback=lambda processed, total, message: updates.append((processed, total)),
    )
    assert updates
    assert updates[-1][0] == 5
    assert updates[-1][1] == 5


def test_read_frame_colors_raises_when_trim_range_yields_no_frames(solid_color_video):
    settings = PosterSettings(start_time=10.0)  # video is only ~1s long
    with pytest.raises(ValueError):
        core.read_frame_colors(solid_color_video, settings=settings)


def test_generate_palette_image_end_to_end(solid_color_video):
    settings = PosterSettings(stripe_width=4, image_height=30)
    image = core.generate_palette_image(solid_color_video, settings)
    assert image.width == 5 * 4  # 5 frames
    assert image.height == 30


def test_save_palette_image_writes_png_by_default(solid_color_video, tmp_path):
    settings = PosterSettings(stripe_width=2, image_height=20, output_format="png")
    output_path = core.save_palette_image(solid_color_video, tmp_path / "poster", settings)
    assert output_path.suffix == ".png"
    assert output_path.exists()
    with Image.open(output_path) as saved:
        assert saved.format == "PNG"


def test_save_palette_image_writes_jpg_with_quality(solid_color_video, tmp_path):
    settings = PosterSettings(stripe_width=2, image_height=20, output_format="jpg", jpg_quality=80)
    output_path = core.save_palette_image(solid_color_video, tmp_path / "poster.png", settings)
    assert output_path.suffix == ".jpg"
    assert output_path.exists()
    with Image.open(output_path) as saved:
        assert saved.format == "JPEG"


# --- CSV interop (kept for the legacy extract-to-CSV workflow) ---


def test_read_colors_from_csv_round_trip(tmp_path):
    csv_path = tmp_path / "colors.csv"
    rows = [(0, 10, 20, 30), (1, 40, 50, 60)]
    with csv_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame", "R", "G", "B"])
        writer.writerows(rows)

    colors = core.read_colors_from_csv(csv_path)

    assert colors.shape == (2, 3)
    assert colors.dtype == np.uint8
    assert tuple(colors[0]) == (10, 20, 30)
    assert tuple(colors[1]) == (40, 50, 60)
