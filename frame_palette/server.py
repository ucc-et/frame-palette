"""FastAPI backend exposing the Frame Palette engine over HTTP.

This is the seam between any frontend (a browser tab, a pywebview shell)
and the engine in ``frame_palette.core`` / ``frame_palette.video``. It holds
no UI logic of its own: request/response translation, a background job
tracker for long-running poster generation, HTTP range serving for the
video scrubber, and static file serving for the ``ui/`` frontend.
"""

from __future__ import annotations

import base64
import io
import re
import sys
import threading
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Iterator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from frame_palette import core, video
from frame_palette.settings import ColorMode, Orientation, OutputFormat, PosterSettings, Smoothing


def _resolve_ui_dir() -> Path:
    """Locate the ``ui/`` static asset directory.

    In a normal source checkout this is the ``ui/`` folder next to
    ``frame_palette/``. Inside a PyInstaller-frozen build there is no
    ``frame_palette`` source tree on disk -- everything is unpacked under
    ``sys._MEIPASS`` instead, with ``ui/`` bundled there as a top-level
    data directory (see ``frame_palette_app.spec``).
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / "ui"
    return Path(__file__).resolve().parent.parent / "ui"


UI_DIR = _resolve_ui_dir()

app = FastAPI(title="Frame Palette API")


# --------------------------------------------------------------------------
# Request/response models
# --------------------------------------------------------------------------


class PosterSettingsPayload(BaseModel):
    """Mirrors frame_palette.settings.PosterSettings for JSON request bodies."""

    stripe_width: int = 2
    image_height: int = 1200
    max_output_width: int = 8000
    orientation: Orientation = "vertical"
    color_mode: ColorMode = "average"
    smoothing: Smoothing = "off"
    blur: int = 0
    sample_every: int = 1
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    title_band_height: int = 180
    title_font_size: int = 54
    title_margin: int = 28
    output_format: OutputFormat = "png"
    jpg_quality: int = 92

    def to_settings(self) -> PosterSettings:
        try:
            return PosterSettings(**self.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class VideoRequest(BaseModel):
    path: str


class VideoInfoResponse(BaseModel):
    path: str
    width: int
    height: int
    fps: float
    frame_count: int
    duration_seconds: float
    thumbnail_base64: Optional[str] = None


class PreviewRequest(BaseModel):
    video_path: str
    settings: PosterSettingsPayload = Field(default_factory=PosterSettingsPayload)
    title: str = ""
    max_frames: int = 300
    max_preview_width: int = 1600


class PreviewResponse(BaseModel):
    image_base64: str
    width: int
    height: int


class GenerateRequest(BaseModel):
    video_path: str
    output_path: str
    settings: PosterSettingsPayload = Field(default_factory=PosterSettingsPayload)
    title: str = ""


class GenerateAcceptedResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str = "pending"  # "pending" | "running" | "done" | "error"
    processed: int = 0
    total: Optional[int] = None
    message: str = ""
    output_path: Optional[str] = None
    error: Optional[str] = None


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _resolve_existing_file(path: str, kind: str = "file") -> Path:
    resolved = Path(path)
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"{kind.capitalize()} not found: {path}")
    return resolved


def _image_to_base64(image, image_format: str = "PNG") -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# --------------------------------------------------------------------------
# Video metadata + thumbnail
# --------------------------------------------------------------------------


@app.post("/api/video", response_model=VideoInfoResponse)
def get_video_info(payload: VideoRequest) -> VideoInfoResponse:
    video_path = _resolve_existing_file(payload.path, kind="video")

    try:
        metadata = video.get_metadata(video_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    thumbnail = video.get_thumbnail(video_path)
    thumbnail_base64 = _image_to_base64(thumbnail) if thumbnail is not None else None

    return VideoInfoResponse(
        path=str(video_path),
        width=metadata.width,
        height=metadata.height,
        fps=metadata.fps,
        frame_count=metadata.frame_count,
        duration_seconds=metadata.duration_seconds,
        thumbnail_base64=thumbnail_base64,
    )


# --------------------------------------------------------------------------
# Video streaming (HTTP range requests, for a <video> scrubber)
# --------------------------------------------------------------------------

_RANGE_HEADER_RE = re.compile(r"bytes=(\d*)-(\d*)")
_CHUNK_SIZE = 1024 * 1024


def _iter_file_range(path: Path, start: int, end: int, chunk_size: int = _CHUNK_SIZE) -> Iterator[bytes]:
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@app.get("/api/video/stream")
def stream_video(path: str, request: Request) -> StreamingResponse:
    video_path = _resolve_existing_file(path, kind="video")
    file_size = video_path.stat().st_size
    media_type = "video/mp4"  # best-effort; most browsers sniff actual content anyway
    range_header = request.headers.get("range")

    if range_header is None:
        return StreamingResponse(
            _iter_file_range(video_path, 0, file_size - 1),
            media_type=media_type,
            headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
        )

    match = _RANGE_HEADER_RE.match(range_header)
    if not match:
        raise HTTPException(status_code=416, detail="Invalid Range header")

    start_text, end_text = match.groups()
    start = int(start_text) if start_text else 0
    end = int(end_text) if end_text else file_size - 1
    end = min(end, file_size - 1)

    if start > end or start >= file_size:
        raise HTTPException(status_code=416, detail="Requested range not satisfiable")

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
    }
    return StreamingResponse(
        _iter_file_range(video_path, start, end),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


# --------------------------------------------------------------------------
# Quick preview: synchronous, deliberately cheap regardless of the caller's
# real settings, so the UI can call this on every slider tick.
# --------------------------------------------------------------------------


@app.post("/api/preview", response_model=PreviewResponse)
def create_preview(payload: PreviewRequest) -> PreviewResponse:
    video_path = _resolve_existing_file(payload.video_path, kind="video")
    settings = payload.settings.to_settings()

    try:
        metadata = video.get_metadata(video_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sample_every = settings.sample_every
    estimated_frames = video.estimate_sampled_frame_count(
        metadata,
        start_time=settings.start_time,
        end_time=settings.end_time,
        sample_every=sample_every,
    )
    if estimated_frames and payload.max_frames > 0 and estimated_frames > payload.max_frames:
        # Bump sample_every just enough to keep the preview under max_frames.
        sample_every = max(sample_every, -(-estimated_frames // payload.max_frames))

    preview_settings = replace(
        settings,
        sample_every=sample_every,
        max_output_width=min(settings.max_output_width, payload.max_preview_width),
    )

    try:
        image = core.generate_palette_image(video_path, preview_settings, title=payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PreviewResponse(image_base64=_image_to_base64(image), width=image.width, height=image.height)


# --------------------------------------------------------------------------
# Full generation: a background job the client polls for progress, so a
# long video doesn't block the HTTP request (or the UI) while it processes.
# --------------------------------------------------------------------------

_jobs: dict[str, JobStatusResponse] = {}
_jobs_lock = threading.Lock()


def _run_generate_job(job_id: str, video_path: Path, output_path: Path, settings: PosterSettings, title: str) -> None:
    with _jobs_lock:
        _jobs[job_id].status = "running"

    def on_progress(processed: int, total: int | None, message: str) -> None:
        with _jobs_lock:
            job = _jobs[job_id]
            job.status = "running"
            job.processed = processed
            job.total = total
            job.message = message

    try:
        saved_path = core.save_palette_image(
            video_path, output_path, settings, title=title, progress_callback=on_progress
        )
    except Exception as exc:  # noqa: BLE001 -- surface any failure to the polling client, not the thread's stderr
        with _jobs_lock:
            job = _jobs[job_id]
            job.status = "error"
            job.error = str(exc)
        return

    with _jobs_lock:
        job = _jobs[job_id]
        job.status = "done"
        job.output_path = str(saved_path)
        job.message = f"Saved poster to {saved_path}"


@app.post("/api/generate", response_model=GenerateAcceptedResponse, status_code=202)
def start_generate(payload: GenerateRequest) -> GenerateAcceptedResponse:
    video_path = _resolve_existing_file(payload.video_path, kind="video")
    settings = payload.settings.to_settings()

    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = JobStatusResponse(job_id=job_id, status="pending")

    thread = threading.Thread(
        target=_run_generate_job,
        args=(job_id, video_path, Path(payload.output_path), settings, payload.title),
        daemon=True,
    )
    thread.start()

    return GenerateAcceptedResponse(job_id=job_id)


@app.get("/api/generate/{job_id}", response_model=JobStatusResponse)
def get_generate_status(job_id: str) -> JobStatusResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Unknown job id: {job_id}")
        return job.model_copy()


# --------------------------------------------------------------------------
# Static frontend
# --------------------------------------------------------------------------

if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
