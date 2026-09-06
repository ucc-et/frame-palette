"""Unified command-line interface for the Frame Palette engine.

Replaces the two standalone legacy scripts with subcommands backed by the
shared engine (``frame_palette.core`` / ``frame_palette.settings``):

- ``extract`` replaces ``poster.py`` (video -> CSV of per-frame colors).
- ``render``  replaces ``csv-to-image.py`` (CSV -> stripe poster), and can
  also go straight from a video to a poster in one step via ``--video``.
"""

from __future__ import annotations

import argparse
import csv as csv_module
import sys
from pathlib import Path
from typing import Sequence

from frame_palette.core import build_palette_image, read_colors_from_csv, read_frame_colors, save_image, save_palette_image
from frame_palette.settings import COLOR_MODES, ORIENTATIONS, OUTPUT_FORMATS, SMOOTHING_LEVELS, PosterSettings


def _print_progress(processed: int, total: int | None, message: str) -> None:
    print(message)


def _add_poster_look_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stripe-width", type=int, default=2, help="Width in pixels of each frame's stripe (default: 2)")
    parser.add_argument("--image-height", type=int, default=1200, help="Thickness of the poster's cross axis in pixels (default: 1200)")
    parser.add_argument("--max-output-width", type=int, default=8000, help="Cap on the poster's long axis in pixels (default: 8000)")
    parser.add_argument("--orientation", choices=ORIENTATIONS, default="vertical", help="Stripe direction (default: vertical)")
    parser.add_argument("--blur", type=int, default=0, help="Gaussian blur radius applied to the finished poster (default: 0)")
    parser.add_argument("--title", default="", help="Optional title printed below the poster")
    parser.add_argument("--output-format", choices=OUTPUT_FORMATS, default="png", help="Poster file format (default: png)")
    parser.add_argument("--jpg-quality", type=int, default=92, help="JPEG quality 1-100, used with --output-format=jpg (default: 92)")


def _add_extraction_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--color-mode", choices=COLOR_MODES, default="average", help="How to summarize each frame's color (default: average)")
    parser.add_argument("--smoothing", choices=SMOOTHING_LEVELS, default="off", help="Temporal smoothing across neighboring frames (default: off)")
    parser.add_argument("--sample-every", type=int, default=1, help="Keep 1 out of every N frames (default: 1 = every frame)")
    parser.add_argument("--start-time", type=float, default=None, help="Seconds into the video to start reading from")
    parser.add_argument("--end-time", type=float, default=None, help="Seconds into the video to stop reading at")


def _write_colors_csv(colors: list[tuple[int, int, int]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as handle:
        writer = csv_module.writer(handle)
        writer.writerow(["frame", "R", "G", "B"])
        for index, (red, green, blue) in enumerate(colors):
            writer.writerow([index, red, green, blue])


def _cmd_extract(args: argparse.Namespace) -> int:
    settings = PosterSettings(
        color_mode=args.color_mode,
        smoothing=args.smoothing,
        sample_every=args.sample_every,
        start_time=args.start_time,
        end_time=args.end_time,
    )

    colors = read_frame_colors(args.video, settings=settings, progress_callback=_print_progress)

    output_path = Path(args.output)
    _write_colors_csv(colors, output_path)

    print(f"Saved CSV to: {output_path}")
    print(f"Total frames processed: {len(colors)}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    settings = PosterSettings(
        stripe_width=args.stripe_width,
        image_height=args.image_height,
        max_output_width=args.max_output_width,
        orientation=args.orientation,
        blur=args.blur,
        output_format=args.output_format,
        jpg_quality=args.jpg_quality,
        color_mode=args.color_mode,
        smoothing=args.smoothing,
        sample_every=args.sample_every,
        start_time=args.start_time,
        end_time=args.end_time,
    )

    if args.video:
        output_path = save_palette_image(
            args.video, args.output, settings, title=args.title, progress_callback=_print_progress
        )
    else:
        colors = read_colors_from_csv(args.csv)
        image = build_palette_image(colors, settings, title=args.title)
        output_path = save_image(image, args.output, settings)

    print(f"Saved poster to: {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="frame-palette-cli",
        description=(
            "Command-line tools for the Frame Palette engine: extract per-frame "
            "colors from a video, and render them as a stripe poster."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract per-frame colors from a video into a CSV file",
        description=(
            "Replaces the old poster.py script: reads a video and writes one "
            "row of (frame, R, G, B) per processed frame to a CSV."
        ),
    )
    extract_parser.add_argument("video", help="Path to the input video")
    extract_parser.add_argument("--output", default="frame_colors.csv", help="Output CSV path (default: frame_colors.csv)")
    _add_extraction_arguments(extract_parser)
    extract_parser.set_defaults(func=_cmd_extract)

    render_parser = subparsers.add_parser(
        "render",
        help="Render a stripe poster from a CSV of frame colors, or directly from a video",
        description=(
            "Replaces the old csv-to-image.py script: builds a stripe poster "
            "from a CSV (as produced by 'extract'), or straight from a video "
            "in one step with --video."
        ),
    )
    source_group = render_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--csv", help="Input CSV path, as produced by 'extract'")
    source_group.add_argument("--video", help="Input video path -- extracts colors and renders the poster in one step")
    render_parser.add_argument("--output", default="movie_palette.png", help="Output image path (default: movie_palette.png)")
    _add_poster_look_arguments(render_parser)
    _add_extraction_arguments(render_parser)  # only meaningful together with --video; ignored with --csv
    render_parser.set_defaults(func=_cmd_render)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        exit_code = args.func(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
