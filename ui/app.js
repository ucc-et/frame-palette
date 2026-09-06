"use strict";

/* Frame Palette frontend -- talks to the FastAPI backend in frame_palette/server.py.
 * No build step, no framework: plain DOM wiring, kept in one file on purpose.
 */

const API = {
  video: "/api/video",
  stream: "/api/video/stream",
  preview: "/api/preview",
  generate: "/api/generate",
};

const DEFAULT_IMAGE_HEIGHT = 200; // fixed poster cross-axis thickness; not exposed in this UI

const el = (id) => document.getElementById(id);

const dom = {
  videoPreview: el("video-preview"),
  videoThumb: el("video-thumb"),
  videoThumbPlaceholder: el("video-thumb-placeholder"),
  videoThumbImg: el("video-thumb-img"),
  btnRemoveVideo: el("btn-remove-video"),
  videoName: el("video-name"),
  videoDetails: el("video-details"),
  btnChooseVideo: el("btn-choose-video"),

  stripeWidth: el("stripe-width"),
  valStripeWidth: el("val-stripe-width"),
  smoothing: el("smoothing"),
  colorMode: el("color-mode"),
  blur: el("blur"),
  valBlur: el("val-blur"),

  outputWidth: el("output-width"),
  valOutputWidth: el("val-output-width"),
  outputFormat: el("output-format"),
  btnGenerate: el("btn-generate"),
  btnPreview: el("btn-preview"),

  previewMode: el("preview-mode"),
  zoomValue: el("zoom-value"),
  previewStage: el("preview-stage"),
  previewEmpty: el("preview-empty"),
  previewImage: el("preview-image"),
  previewSpinner: el("preview-spinner"),

  btnPlay: el("btn-play"),
  timeCurrent: el("time-current"),
  timeTotal: el("time-total"),
  scrub: el("scrub"),
  sourceVideo: el("source-video"),

  drawer: el("drawer"),
  drawerToggle: el("drawer-toggle"),
  startTime: el("start-time"),
  endTime: el("end-time"),
  sampleEvery: el("sample-every"),
  orientation: el("orientation"),

  aboutText: el("about-text"),
};

const state = {
  videoPath: null,
  videoInfo: null, // { width, height, fps, frame_count, duration_seconds }
  settings: {
    stripe_width: 2,
    image_height: DEFAULT_IMAGE_HEIGHT,
    max_output_width: 1080,
    orientation: "vertical",
    color_mode: "average",
    smoothing: "medium",
    blur: 0,
    sample_every: 1,
    start_time: 0,
    end_time: null,
    output_format: "png",
  },
};

// ---------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------

function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function formatTime(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds || 0));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}

function parseTime(text) {
  const parts = String(text).split(":").map((p) => parseInt(p, 10) || 0);
  while (parts.length < 3) parts.unshift(0);
  const [h, m, s] = parts.slice(-3);
  return h * 3600 + m * 60 + s;
}

async function postJSON(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

async function getJSON(url) {
  const response = await fetch(url);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function setSegmentedValue(container, value) {
  container.dataset.value = value;
  container.querySelectorAll("button").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.value === value);
  });
}

function wireSegmented(container, onChange) {
  container.addEventListener("click", (event) => {
    const btn = event.target.closest("button[data-value]");
    if (!btn) return;
    setSegmentedValue(container, btn.dataset.value);
    onChange(btn.dataset.value);
  });
}

// ---------------------------------------------------------------------
// video loading
// ---------------------------------------------------------------------

async function loadVideo(path) {
  try {
    const info = await postJSON(API.video, { path });

    state.videoPath = info.path;
    state.videoInfo = info;
    state.settings.start_time = 0;
    state.settings.end_time = info.duration_seconds;

    dom.videoPreview.classList.add("has-video");
    dom.videoThumbPlaceholder.hidden = true;
    if (info.thumbnail_base64) {
      dom.videoThumbImg.src = `data:image/png;base64,${info.thumbnail_base64}`;
      dom.videoThumbImg.hidden = false;
    }

    dom.videoName.textContent = info.path.split("/").pop();
    dom.videoDetails.textContent = [
      formatTime(info.duration_seconds),
      `${info.width}x${info.height}`,
      `${Math.round(info.fps)}fps`,
    ].join("   ");

    dom.startTime.value = formatTime(0);
    dom.endTime.value = formatTime(info.duration_seconds);

    dom.sourceVideo.src = `${API.stream}?path=${encodeURIComponent(info.path)}`;
    dom.scrub.disabled = false;
    dom.timeTotal.textContent = formatTime(info.duration_seconds);

    dom.btnGenerate.disabled = false;
    dom.btnPreview.disabled = false;

    requestPreview();
  } catch (err) {
    console.error("Failed to load video:", err.message);
  }
}

function clearVideo() {
  state.videoPath = null;
  state.videoInfo = null;

  dom.videoPreview.classList.remove("has-video");
  dom.videoThumbPlaceholder.hidden = false;
  dom.videoThumbImg.hidden = true;
  dom.videoThumbImg.removeAttribute("src");
  dom.videoName.textContent = "No video selected";
  dom.videoDetails.textContent = "";

  dom.sourceVideo.removeAttribute("src");
  dom.scrub.disabled = true;
  dom.timeCurrent.textContent = "00:00:00";
  dom.timeTotal.textContent = "00:00:00";

  dom.btnGenerate.disabled = true;
  dom.btnPreview.disabled = true;

  dom.previewImage.hidden = true;
  dom.previewEmpty.hidden = false;
}

// ---------------------------------------------------------------------
// preview
// ---------------------------------------------------------------------

function currentSettingsPayload() {
  return { ...state.settings };
}

async function requestPreview() {
  if (!state.videoPath) return;

  dom.previewStage.classList.add("is-loading");
  try {
    const result = await postJSON(API.preview, {
      video_path: state.videoPath,
      settings: currentSettingsPayload(),
      max_frames: 400,
      max_preview_width: 1600,
    });

    dom.previewEmpty.hidden = true;
    dom.previewImage.hidden = false;
    dom.previewImage.src = `data:image/png;base64,${result.image_base64}`;
    dom.previewImage.onload = updateZoomIndicator;
  } catch (err) {
    console.error("Preview failed:", err.message);
  } finally {
    dom.previewStage.classList.remove("is-loading");
  }
}

const requestPreviewDebounced = debounce(requestPreview, 400);

function updateZoomIndicator() {
  if (dom.previewImage.hidden || !dom.previewImage.naturalWidth) {
    dom.zoomValue.textContent = "100%";
    return;
  }
  const mode = dom.previewMode.dataset.value;
  if (mode === "actual") {
    dom.zoomValue.textContent = "100%";
    return;
  }
  const rect = dom.previewImage.getBoundingClientRect();
  const zoom = Math.round((rect.width / dom.previewImage.naturalWidth) * 100);
  dom.zoomValue.textContent = `${zoom}%`;
}

// ---------------------------------------------------------------------
// generate
// ---------------------------------------------------------------------

function defaultOutputPath() {
  const path = state.videoPath;
  const dot = path.lastIndexOf(".");
  const stem = dot > -1 ? path.slice(0, dot) : path;
  const ext = state.settings.output_format === "jpg" ? "jpg" : "png";
  return `${stem}_palette.${ext}`;
}

async function pickOutputPath() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_path_dialog) {
    try {
      const chosen = await window.pywebview.api.save_path_dialog();
      if (chosen) return chosen;
    } catch (err) {
      console.warn("Native save dialog unavailable, using default path:", err);
    }
  }
  return defaultOutputPath();
}

async function pollJob(jobId) {
  for (;;) {
    const status = await getJSON(`${API.generate}/${jobId}`);
    if (status.status === "done" || status.status === "error") return status;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}

async function startGenerate() {
  if (!state.videoPath) return;

  const outputPath = await pickOutputPath();
  const originalLabel = dom.btnGenerate.innerHTML;
  dom.btnGenerate.disabled = true;
  dom.btnGenerate.textContent = "Generating…";

  try {
    const { job_id } = await postJSON(API.generate, {
      video_path: state.videoPath,
      output_path: outputPath,
      settings: currentSettingsPayload(),
    });
    const result = await pollJob(job_id);

    if (result.status === "done") {
      dom.btnGenerate.textContent = "Saved ✓";
      console.log("Saved poster to:", result.output_path);
    } else {
      dom.btnGenerate.textContent = "Failed";
      console.error("Generate failed:", result.error);
    }
  } catch (err) {
    dom.btnGenerate.textContent = "Failed";
    console.error("Generate failed:", err.message);
  } finally {
    setTimeout(() => {
      dom.btnGenerate.innerHTML = originalLabel;
      dom.btnGenerate.disabled = false;
    }, 1800);
  }
}

// ---------------------------------------------------------------------
// event wiring
// ---------------------------------------------------------------------

dom.btnChooseVideo.addEventListener("click", async () => {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_video_dialog) {
    try {
      const path = await window.pywebview.api.open_video_dialog();
      if (path) loadVideo(path);
    } catch (err) {
      console.error("Native file dialog failed:", err);
    }
    return;
  }
  console.info(
    "The native file dialog is provided by the desktop shell (pywebview) and isn't available in a plain browser. " +
      "Use ?video=<absolute-path> in the URL, or call FramePalette.loadVideo(path) from the console."
  );
});

dom.btnRemoveVideo.addEventListener("click", (event) => {
  event.stopPropagation();
  clearVideo();
});

dom.stripeWidth.addEventListener("input", () => {
  state.settings.stripe_width = Number(dom.stripeWidth.value);
  dom.valStripeWidth.textContent = `${state.settings.stripe_width}px`;
  requestPreviewDebounced();
});

dom.smoothing.addEventListener("change", () => {
  state.settings.smoothing = dom.smoothing.value;
  requestPreviewDebounced();
});

wireSegmented(dom.colorMode, (value) => {
  state.settings.color_mode = value;
  requestPreviewDebounced();
});

dom.blur.addEventListener("input", () => {
  state.settings.blur = Number(dom.blur.value);
  dom.valBlur.textContent = `${state.settings.blur}px`;
  requestPreviewDebounced();
});

dom.outputWidth.addEventListener("input", () => {
  state.settings.max_output_width = Number(dom.outputWidth.value);
  dom.valOutputWidth.textContent = `${state.settings.max_output_width}px`;
  requestPreviewDebounced();
});

wireSegmented(dom.outputFormat, (value) => {
  state.settings.output_format = value;
});

wireSegmented(dom.orientation, (value) => {
  state.settings.orientation = value;
  const noun = value === "horizontal" ? "horizontal" : "vertical";
  dom.aboutText.textContent = `Each ${noun} stripe represents the average color of a single frame in the video. Longer videos will result in more stripes.`;
  requestPreviewDebounced();
});

dom.startTime.addEventListener("change", () => {
  state.settings.start_time = parseTime(dom.startTime.value);
  dom.startTime.value = formatTime(state.settings.start_time);
  requestPreviewDebounced();
});

dom.endTime.addEventListener("change", () => {
  state.settings.end_time = parseTime(dom.endTime.value);
  dom.endTime.value = formatTime(state.settings.end_time);
  requestPreviewDebounced();
});

dom.sampleEvery.addEventListener("change", () => {
  state.settings.sample_every = Math.max(1, Number(dom.sampleEvery.value) || 1);
  dom.sampleEvery.value = state.settings.sample_every;
  requestPreviewDebounced();
});

document.querySelectorAll(".spin-input__controls button").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = el(btn.dataset.target);
    const direction = Number(btn.dataset.dir);
    const seconds = Math.max(0, parseTime(target.value) + direction);
    target.value = formatTime(seconds);
    target.dispatchEvent(new Event("change"));
  });
});

wireSegmented(dom.previewMode, (value) => {
  dom.previewStage.classList.remove("mode-fit", "mode-fill", "mode-actual");
  dom.previewStage.classList.add(`mode-${value}`);
  updateZoomIndicator();
});

dom.btnPreview.addEventListener("click", requestPreview);
dom.btnGenerate.addEventListener("click", startGenerate);

dom.drawerToggle.addEventListener("click", () => {
  dom.drawer.classList.toggle("is-open");
});

// scrubber <-> hidden <video> element

dom.sourceVideo.addEventListener("loadedmetadata", () => {
  dom.scrub.max = String(dom.sourceVideo.duration || 0);
});

dom.sourceVideo.addEventListener("timeupdate", () => {
  dom.timeCurrent.textContent = formatTime(dom.sourceVideo.currentTime);
  dom.scrub.value = String(dom.sourceVideo.currentTime);
});

dom.scrub.addEventListener("input", () => {
  dom.sourceVideo.currentTime = Number(dom.scrub.value);
});

dom.btnPlay.addEventListener("click", () => {
  if (dom.sourceVideo.paused) {
    dom.sourceVideo.play();
    dom.btnPlay.innerHTML =
      '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>';
  } else {
    dom.sourceVideo.pause();
    dom.btnPlay.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7-11-7Z"/></svg>';
  }
});

window.addEventListener("resize", updateZoomIndicator);

// ---------------------------------------------------------------------
// dev/testing entry points (no pywebview shell yet -- see Task 5)
// ---------------------------------------------------------------------

function initUI() {
  dom.smoothing.value = state.settings.smoothing;
  dom.valStripeWidth.textContent = `${state.settings.stripe_width}px`;
  dom.valBlur.textContent = `${state.settings.blur}px`;
  dom.valOutputWidth.textContent = `${state.settings.max_output_width}px`;
}

initUI();

window.FramePalette = { loadVideo, clearVideo, state };

const params = new URLSearchParams(window.location.search);
const initialVideo = params.get("video");
if (initialVideo) loadVideo(initialVideo);
