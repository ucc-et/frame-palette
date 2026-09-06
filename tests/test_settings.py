from __future__ import annotations

import pytest

from frame_palette.settings import PosterSettings


def test_defaults_are_valid():
    settings = PosterSettings()
    assert settings.color_mode == "average"
    assert settings.orientation == "vertical"
    assert settings.output_format == "png"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"stripe_width": 0},
        {"image_height": 0},
        {"max_output_width": 0},
        {"orientation": "diagonal"},
        {"color_mode": "mode"},
        {"smoothing": "extreme"},
        {"blur": -1},
        {"sample_every": 0},
        {"start_time": -1.0},
        {"end_time": -1.0},
        {"start_time": 5.0, "end_time": 5.0},
        {"start_time": 5.0, "end_time": 1.0},
        {"output_format": "gif"},
        {"jpg_quality": 0},
        {"jpg_quality": 101},
    ],
)
def test_invalid_values_raise(kwargs):
    with pytest.raises(ValueError):
        PosterSettings(**kwargs)
