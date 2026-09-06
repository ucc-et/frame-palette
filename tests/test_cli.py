from __future__ import annotations

import csv
from pathlib import Path

import pytest
from PIL import Image

from frame_palette import cli


# --- argument parsing ---


def test_extract_parses_defaults():
    args = cli.build_parser().parse_args(["extract", "video.mp4"])
    assert args.command == "extract"
    assert args.video == "video.mp4"
    assert args.output == "frame_colors.csv"
    assert args.color_mode == "average"
    assert args.smoothing == "off"
    assert args.sample_every == 1


def test_render_requires_a_source():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["render", "--output", "out.png"])


def test_render_rejects_both_sources_at_once():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["render", "--csv", "a.csv", "--video", "a.mp4"])


def test_no_command_is_rejected():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


# --- extract: video -> CSV (replaces poster.py) ---


def test_extract_end_to_end_writes_expected_csv(solid_color_video, tmp_path, capsys):
    output_csv = tmp_path / "colors.csv"
    cli.main(["extract", str(solid_color_video), "--output", str(output_csv)])

    assert output_csv.exists()
    with output_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 5
    assert set(rows[0].keys()) == {"frame", "R", "G", "B"}

    captured = capsys.readouterr()
    assert "Total frames processed: 5" in captured.out


def test_extract_respects_sample_every(solid_color_video, tmp_path):
    output_csv = tmp_path / "colors.csv"
    cli.main(["extract", str(solid_color_video), "--output", str(output_csv), "--sample-every", "2"])

    with output_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3


def test_extract_reports_error_for_missing_video(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["extract", str(tmp_path / "missing.mp4"), "--output", str(tmp_path / "out.csv")])
    assert exc_info.value.code == 1
    assert "Error" in capsys.readouterr().err


# --- render: CSV -> poster (replaces csv-to-image.py) ---


def _write_csv(path: Path, rows: list[tuple[int, int, int]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame", "R", "G", "B"])
        for index, (r, g, b) in enumerate(rows):
            writer.writerow([index, r, g, b])


def test_render_from_csv_writes_png(tmp_path):
    csv_path = tmp_path / "colors.csv"
    _write_csv(csv_path, [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
    output_path = tmp_path / "poster.png"

    cli.main(["render", "--csv", str(csv_path), "--output", str(output_path), "--stripe-width", "2", "--image-height", "10"])

    assert output_path.exists()
    with Image.open(output_path) as image:
        assert image.format == "PNG"
        assert image.width == 3 * 2
        assert image.height == 10


def test_render_from_csv_horizontal_orientation(tmp_path):
    csv_path = tmp_path / "colors.csv"
    _write_csv(csv_path, [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
    output_path = tmp_path / "poster.png"

    cli.main(
        [
            "render",
            "--csv",
            str(csv_path),
            "--output",
            str(output_path),
            "--stripe-width",
            "2",
            "--image-height",
            "10",
            "--orientation",
            "horizontal",
        ]
    )

    with Image.open(output_path) as image:
        assert image.width == 10
        assert image.height == 3 * 2


def test_render_from_video_end_to_end(solid_color_video, tmp_path):
    output_path = tmp_path / "poster.png"
    cli.main(["render", "--video", str(solid_color_video), "--output", str(output_path), "--stripe-width", "2", "--image-height", "10"])

    assert output_path.exists()
    with Image.open(output_path) as image:
        assert image.width == 5 * 2


def test_render_jpg_output_and_quality(solid_color_video, tmp_path):
    output_path = tmp_path / "poster.png"  # deliberately wrong suffix; CLI should correct it
    cli.main(
        [
            "render",
            "--video",
            str(solid_color_video),
            "--output",
            str(output_path),
            "--output-format",
            "jpg",
            "--jpg-quality",
            "70",
        ]
    )

    jpg_path = output_path.with_suffix(".jpg")
    assert jpg_path.exists()
    assert not output_path.exists()
    with Image.open(jpg_path) as image:
        assert image.format == "JPEG"


def test_render_with_title_adds_band(tmp_path):
    csv_path = tmp_path / "colors.csv"
    _write_csv(csv_path, [(10, 10, 10), (20, 20, 20)])
    no_title_path = tmp_path / "no_title.png"
    with_title_path = tmp_path / "with_title.png"

    cli.main(["render", "--csv", str(csv_path), "--output", str(no_title_path), "--image-height", "10"])
    cli.main(["render", "--csv", str(csv_path), "--output", str(with_title_path), "--image-height", "10", "--title", "Hello"])

    with Image.open(no_title_path) as no_title, Image.open(with_title_path) as with_title:
        assert with_title.height > no_title.height
