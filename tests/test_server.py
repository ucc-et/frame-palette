from __future__ import annotations

import base64
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from frame_palette.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _decode_image(image_base64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(image_base64)))


def _wait_for_job(client: TestClient, job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/generate/{job_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] in ("done", "error"):
            return data
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


# --- POST /api/video ---


def test_get_video_info_returns_metadata_and_thumbnail(client, solid_color_video):
    response = client.post("/api/video", json={"path": str(solid_color_video)})
    assert response.status_code == 200

    data = response.json()
    assert data["width"] == 64
    assert data["height"] == 48
    assert data["frame_count"] == 5
    assert data["thumbnail_base64"]

    thumbnail = _decode_image(data["thumbnail_base64"])
    assert thumbnail.width <= 286
    assert thumbnail.height <= 144


def test_get_video_info_404_for_missing_file(client, tmp_path):
    response = client.post("/api/video", json={"path": str(tmp_path / "missing.mp4")})
    assert response.status_code == 404


# --- GET /api/video/stream ---


def test_stream_video_without_range_returns_full_file(client, solid_color_video):
    response = client.get("/api/video/stream", params={"path": str(solid_color_video)})
    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert int(response.headers["content-length"]) == solid_color_video.stat().st_size
    assert len(response.content) == solid_color_video.stat().st_size


def test_stream_video_with_range_returns_partial_content(client, solid_color_video):
    response = client.get("/api/video/stream", params={"path": str(solid_color_video)}, headers={"Range": "bytes=0-9"})
    assert response.status_code == 206
    assert response.headers["content-length"] == "10"
    assert len(response.content) == 10
    file_size = solid_color_video.stat().st_size
    assert response.headers["content-range"] == f"bytes 0-9/{file_size}"


def test_stream_video_invalid_range_header_returns_416(client, solid_color_video):
    response = client.get("/api/video/stream", params={"path": str(solid_color_video)}, headers={"Range": "not-a-range"})
    assert response.status_code == 416


def test_stream_video_404_for_missing_file(client, tmp_path):
    response = client.get("/api/video/stream", params={"path": str(tmp_path / "missing.mp4")})
    assert response.status_code == 404


# --- POST /api/preview ---


def test_preview_returns_base64_image(client, solid_color_video):
    response = client.post(
        "/api/preview",
        json={"video_path": str(solid_color_video), "settings": {"stripe_width": 2, "image_height": 20}},
    )
    assert response.status_code == 200

    data = response.json()
    image = _decode_image(data["image_base64"])
    assert image.width == 5 * 2  # 5 frames, stripe_width 2, well under max_frames
    assert image.height == 20
    assert data["width"] == image.width
    assert data["height"] == image.height


def test_preview_caps_frames_when_over_max_frames(client, solid_color_video):
    response = client.post(
        "/api/preview",
        json={
            "video_path": str(solid_color_video),
            "settings": {"stripe_width": 2, "image_height": 20},
            "max_frames": 2,
        },
    )
    assert response.status_code == 200
    image = _decode_image(response.json()["image_base64"])
    # 5 frames capped to <=2 -> fewer stripes than the uncapped 5*2=10px wide poster
    assert image.width < 5 * 2


def test_preview_404_for_missing_video(client, tmp_path):
    response = client.post("/api/preview", json={"video_path": str(tmp_path / "missing.mp4")})
    assert response.status_code == 404


def test_preview_422_for_invalid_settings(client, solid_color_video):
    response = client.post(
        "/api/preview",
        json={"video_path": str(solid_color_video), "settings": {"stripe_width": 0}},
    )
    assert response.status_code == 422


# --- POST /api/generate + GET /api/generate/{job_id} ---


def test_generate_and_poll_until_done(client, solid_color_video, tmp_path):
    output_path = tmp_path / "poster.png"
    response = client.post(
        "/api/generate",
        json={
            "video_path": str(solid_color_video),
            "output_path": str(output_path),
            "settings": {"stripe_width": 2, "image_height": 20},
            "title": "Test Poster",
        },
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    final = _wait_for_job(client, job_id)
    assert final["status"] == "done"
    assert final["output_path"] == str(output_path)
    assert output_path.exists()


def test_generate_404_for_missing_video(client, tmp_path):
    response = client.post(
        "/api/generate",
        json={"video_path": str(tmp_path / "missing.mp4"), "output_path": str(tmp_path / "out.png")},
    )
    assert response.status_code == 404


def test_generate_status_404_for_unknown_job(client):
    response = client.get("/api/generate/does-not-exist")
    assert response.status_code == 404


# --- static frontend ---


def test_root_serves_static_ui(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Frame Palette" in response.text
