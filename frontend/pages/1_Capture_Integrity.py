"""Page 1 - Capture Integrity (Layer 1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api_client  # noqa: E402
from capture import camera_help, files_from_frames, record_video  # noqa: E402
from components import gauge, reason_list, score_card  # noqa: E402

st.set_page_config(page_title="Capture Integrity", page_icon="🎥", layout="wide")
st.title("🎥 Layer 1 · Capture Integrity")
st.caption("Verify the stream comes from a real camera, not a virtual / replay / injected source.")

st.markdown(
    "Record a few seconds from your **camera** (or upload a clip). Timing jitter, "
    "device signatures and temporal entropy are analysed to detect virtual / "
    "replayed / injected streams."
)

camera_help()
source = st.radio("Capture source", ["📹 Record live video", "📁 Upload video clip"], horizontal=True)

video_file = None
frames: list[bytes] = []
if source == "📹 Record live video":
    c1, c2 = st.columns(2)
    seconds = c1.slider("Recording length (s)", 2.0, 6.0, 3.0, 0.5)
    device_index = c2.number_input("Camera index", min_value=0, value=0, step=1)
    if st.button("🔴 Record", type="primary"):
        fr, ts = record_video(
            "capture", seconds=seconds, device_index=int(device_index),
            countdown=2, show_oval=True,
        )
        st.session_state["_cap_frames"] = fr
        st.session_state["_cap_ts"] = ts
    frames = st.session_state.get("_cap_frames", [])
    if frames:
        st.caption(f"{len(frames)} frames ready (real timestamps captured for timing analysis).")
else:
    video_file = st.file_uploader("Short video clip (1-5s)", type=["mp4", "mov", "avi", "webm"])

with st.expander("Camera metadata (optional but recommended)", expanded=True):
    c1, c2, c3 = st.columns(3)
    device_name = c1.text_input("Device name", value="FaceTime HD Camera")
    driver = c2.text_input("Driver / backend", value="AVFoundation")
    fps = c3.number_input("Reported FPS", min_value=0.0, value=30.0)

if st.button("Run capture-integrity check"):
    files: list = []
    if video_file is not None:
        files.append(("video", (video_file.name, video_file.getvalue(), video_file.type)))
    elif frames:
        files = files_from_frames(frames)
    if not files:
        st.warning("Record video or upload a clip first.")
        st.stop()

    payload = {
        "metadata": {"device_name": device_name, "driver": driver, "fps": fps},
        "frame_timestamps_ms": st.session_state.get("_cap_ts", []),
    }
    with st.spinner("Analysing capture integrity..."):
        try:
            result = api_client.capture_check(files, {"payload": json.dumps(payload)})
        except Exception as exc:  # noqa: BLE001
            st.error(f"Request failed: {exc}")
            st.stop()

    st.session_state["capture_result"] = result
    st.success(f"Capture Integrity Score: {result['capture_score']:.1f}/100")

result = st.session_state.get("capture_result")
if result:
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        gauge("Capture", result["capture_score"], key="cap_g")
    with g2:
        score_card("Timing", result["timing_score"], "frame jitter")
    with g3:
        score_card("Metadata", result["metadata_score"], "device trust")
    with g4:
        score_card("Entropy", result["entropy_score"], "temporal")
    st.metric("Injection risk", f"{result['injection_score']:.0f}/100",
              help="Higher = more likely a virtual/injected stream")
    st.metric("Median FPS", f"{result['median_fps']:.1f}")
    reason_list("Reasoning", result.get("reasons", []))
