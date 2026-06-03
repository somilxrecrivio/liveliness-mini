"""Reusable camera-capture widgets (native, local-camera based).

Two capture mechanisms:

* :func:`single_camera` - one still via ``st.camera_input`` (identity /
  reference photos). Prompts the browser for camera permission and shows a feed.
* :func:`record_video`  - records a short **continuous video** straight from the
  local webcam via OpenCV, with a live on-screen preview. This is what the
  liveness layer needs: genuine temporal frames for blink and head-turn
  detection (a static photo cannot show motion).

``record_video`` reads the camera on the machine running Streamlit. Because this
app runs locally on your Mac, that is your real webcam. macOS will ask the
terminal/IDE running Streamlit for camera permission the first time.
"""
from __future__ import annotations

import time

import cv2
import streamlit as st


def camera_help() -> None:
    """Explain how to pick the right camera device."""
    with st.expander("📷 Camera tips / not seeing your real webcam?"):
        st.markdown(
            "- **Photo capture** uses the browser's camera — switch it via the "
            "camera icon in the address bar (Chrome) if it shows OBS/virtual.\n"
            "- **Video recording** reads the webcam directly via OpenCV. macOS "
            "must allow camera access for the app running Streamlit "
            "(**System Settings → Privacy & Security → Camera → Terminal/iTerm/VS Code**).\n"
            "- If recording is black or empty, change the **camera index** "
            "(0 = built-in webcam; OBS / virtual cams are usually 1 or 2)."
        )


def single_camera(key: str, label: str = "Take a photo") -> bytes | None:
    """Capture a single still; returns its bytes (persisted in session)."""
    shot = st.camera_input(label, key=f"cam_{key}")
    if shot is not None:
        st.session_state[f"_single_{key}"] = shot.getvalue()
    return st.session_state.get(f"_single_{key}")


def _draw_oval(img):
    """Return a copy of ``img`` with a face-placement oval guide drawn on it."""
    disp = img.copy()
    h, w = disp.shape[:2]
    cv2.ellipse(disp, (w // 2, h // 2), (int(w * 0.30), int(h * 0.42)),
                0, 0, 360, (0, 200, 255), 2)
    return disp


def record_video(
    key: str,
    seconds: float = 5.0,
    device_index: int = 0,
    countdown: int = 3,
    preview_width: int = 360,
    show_oval: bool = True,
) -> tuple[list[bytes], list[float]]:
    """Record ~``seconds`` of webcam video with a live preview + oval guide.

    Returns ``(frames_jpeg, timestamps_ms)`` where ``timestamps_ms`` are the
    real capture times of each frame (used for frame-timing / jitter analysis).
    Returns ``([], [])`` (with an error shown) if the camera cannot be opened.
    The oval guide is drawn on the *preview only*, never on the stored frames.
    """
    cap = cv2.VideoCapture(device_index)
    if not cap.isOpened():
        cap.release()
        st.error(
            f"Could not open camera at index {device_index}. Grant camera "
            "permission to your terminal/IDE in macOS System Settings → Privacy "
            "& Security → Camera, or try a different camera index."
        )
        return [], []

    preview = st.empty()
    status = st.empty()

    # Warm up the sensor and run a visible countdown.
    for n in range(countdown, 0, -1):
        ok, frame = cap.read()
        if ok:
            small = cv2.resize(frame, (preview_width, int(preview_width * 0.75)))
            if show_oval:
                small = _draw_oval(small)
            preview.image(small, channels="BGR", caption=f"Get ready… {n}  (centre your face in the oval)")
        time.sleep(1.0)

    frames: list = []
    timestamps_ms: list[float] = []
    start = time.time()
    i = 0
    while time.time() - start < seconds:
        ok, frame = cap.read()
        if not ok:
            break
        now = time.time()
        frames.append(frame)
        timestamps_ms.append((now - start) * 1000.0)
        if i % 2 == 0:  # update preview every other frame to stay responsive
            small = cv2.resize(frame, (preview_width, int(preview_width * 0.75)))
            if show_oval:
                small = _draw_oval(small)
            elapsed = now - start
            preview.image(small, channels="BGR",
                          caption=f"🔴 Recording {elapsed:0.1f}/{seconds:0.0f}s — blink & move your head")
            status.progress(min(1.0, elapsed / seconds))
        i += 1

    cap.release()
    preview.empty()
    status.empty()

    if not frames:
        st.error("No frames were captured. Check camera permissions / index.")
        return [], []

    out: list[bytes] = []
    out_ts: list[float] = []
    for f, ts in zip(frames, timestamps_ms):
        ok, buf = cv2.imencode(".jpg", f)
        if ok:
            out.append(buf.tobytes())
            out_ts.append(ts)
    st.success(f"Recorded {len(out)} frames ({len(out) / max(seconds,1):.0f} fps).")
    return out, out_ts


def files_from_frames(frames: list[bytes], field: str = "frames") -> list[tuple]:
    """Build a multipart files list from frame bytes."""
    return [
        (field, (f"frame_{i}.jpg", fb, "image/jpeg"))
        for i, fb in enumerate(frames)
    ]
