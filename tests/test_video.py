from __future__ import annotations

import pytest

from frame_palette import video


def test_get_metadata_reports_dimensions_fps_and_duration(solid_color_video):
    metadata = video.get_metadata(solid_color_video)
    assert metadata.width == 64
    assert metadata.height == 48
    assert metadata.frame_count == 5
    assert metadata.fps == pytest.approx(5.0, rel=0.2)
    assert metadata.duration_seconds == pytest.approx(1.0, rel=0.3)


def test_get_metadata_raises_for_missing_file(tmp_path):
    with pytest.raises(ValueError):
        video.get_metadata(tmp_path / "does-not-exist.mp4")


def test_get_thumbnail_returns_bounded_image(solid_color_video):
    thumbnail = video.get_thumbnail(solid_color_video, max_size=(50, 50))
    assert thumbnail is not None
    assert thumbnail.width <= 50
    assert thumbnail.height <= 50


def test_iter_frames_reads_every_frame_by_default(solid_color_video):
    frames = list(video.iter_frames(solid_color_video))
    assert len(frames) == 5


def test_iter_frames_sample_every_skips_frames(solid_color_video):
    frames = list(video.iter_frames(solid_color_video, sample_every=2))
    assert len(frames) == 3  # frames at index 0, 2, 4


def test_iter_frames_start_time_trims_early_frames(solid_color_video):
    # 5 frames @ 5fps = 1.0s total; starting halfway through should yield fewer frames.
    all_frames = list(video.iter_frames(solid_color_video))
    trimmed_frames = list(video.iter_frames(solid_color_video, start_time=0.5))
    assert 0 < len(trimmed_frames) < len(all_frames)


def test_iter_frames_end_time_trims_late_frames(solid_color_video):
    all_frames = list(video.iter_frames(solid_color_video))
    trimmed_frames = list(video.iter_frames(solid_color_video, end_time=0.5))
    assert 0 < len(trimmed_frames) < len(all_frames)


def test_estimate_sampled_frame_count_matches_actual_iteration(solid_color_video):
    metadata = video.get_metadata(solid_color_video)
    estimate = video.estimate_sampled_frame_count(metadata, sample_every=2)
    actual = len(list(video.iter_frames(solid_color_video, sample_every=2)))
    assert estimate == actual


def test_estimate_sampled_frame_count_none_when_metadata_unknown():
    empty_metadata = video.VideoMetadata(width=0, height=0, fps=0.0, frame_count=0, duration_seconds=0.0)
    assert video.estimate_sampled_frame_count(empty_metadata) is None
