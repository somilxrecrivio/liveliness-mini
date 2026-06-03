"""Page 3 - Active Liveness Verification (Layer 3) - live video."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api_client  # noqa: E402
from capture import camera_help, files_from_frames, record_video  # noqa: E402
from components import gauge, reason_list, score_card  # noqa: E402

st.set_page_config(page_title="Liveness Verification", page_icon="🧬", layout="wide")
st.title("🧬 Layer 3 · Active Liveness Verification")
st.caption("Records a short live video — blink, head-turn, depth parallax and micro-movement are analysed.")

CHALLENGES = {
    "turn_left": "↩️ Turn your head LEFT",
    "turn_right": "↪️ Turn your head RIGHT",
    "look_up": "⬆️ Look UP",
    "look_down": "⬇️ Look DOWN",
}

if "challenge" not in st.session_state or st.button("🎲 New random challenge"):
    st.session_state["challenge"] = random.choice(list(CHALLENGES))
challenge = st.session_state["challenge"]
move_text = CHALLENGES[challenge].split(" ", 1)[1]

st.subheader("Your challenge")
st.info(
    f"**{CHALLENGES[challenge]}**\n\n"
    "When you press record (after the countdown):\n"
    "1. Face the camera straight on and **blink naturally** once or twice.\n"
    f"2. Then **{move_text}** and return to centre.\n"
    "Keep your whole face in frame with even lighting."
)

camera_help()
source = st.radio("Capture source", ["📹 Record live video", "📁 Upload clip"], horizontal=True)

frames: list[bytes] = []
if source == "📹 Record live video":
    c1, c2, c3 = st.columns(3)
    seconds = c1.slider("Recording length (s)", 3.0, 8.0, 5.0, 0.5)
    device_index = c2.number_input("Camera index", min_value=0, value=0, step=1,
                                   help="0 = built-in webcam. Try 1/2 for external/virtual cams.")
    fps = c3.number_input("Advisory FPS", min_value=5.0, value=15.0)
    if st.button("🔴 Record liveness video", type="primary"):
        fr, ts = record_video("liveness", seconds=seconds, device_index=int(device_index))
        st.session_state["_liv_frames"] = fr
        st.session_state["_liv_ts"] = ts
        # Derive the true capture fps from real timestamps.
        if len(ts) > 1 and ts[-1] > 0:
            st.session_state["_liv_fps"] = (len(ts) - 1) / (ts[-1] / 1000.0)
    frames = st.session_state.get("_liv_frames", [])
    if frames:
        st.caption(f"{len(frames)} frames ready · ~{st.session_state.get('_liv_fps', fps):.0f} fps captured.")
else:
    fps = st.number_input("Advisory FPS", min_value=5.0, value=15.0)
    video = st.file_uploader("Liveness clip", type=["mp4", "mov", "avi", "webm"])
    if video is not None:
        st.session_state["liveness_video"] = (video.name, video.getvalue(), video.type)
        st.video(video)

if st.button("Run liveness verification"):
    if source == "📹 Record live video":
        frames = st.session_state.get("_liv_frames", [])
        if len(frames) < 6:
            st.warning("Record a video first (need at least ~6 frames).")
            st.stop()
        files = files_from_frames(frames)
        fps = st.session_state.get("_liv_fps", fps)
    else:
        lv = st.session_state.get("liveness_video")
        if not lv:
            st.warning("Upload a short liveness clip first.")
            st.stop()
        files = [("video", lv)]

    payload = {"challenge": challenge, "fps": fps,
               "frame_timestamps_ms": st.session_state.get("_liv_ts", [])}
    with st.spinner("Analysing blink, head-turn, depth, micro-movement..."):
        try:
            result = api_client.liveness_check(files, {"payload": json.dumps(payload)})
        except Exception as exc:  # noqa: BLE001
            st.error(f"Request failed: {exc}")
            st.stop()
    st.session_state["liveness_result"] = result

result = st.session_state.get("liveness_result")
if result:
    st.divider()
    top = st.columns(3)
    with top[0]:
        gauge("Liveness", result["liveness_score"], key="liv_g")
    top[1].metric("Blink", "✅ Detected" if result["blink_detected"] else "❌ None")
    top[1].metric("Challenge", "✅ Passed" if result["challenge_passed"] else "❌ Failed")
    top[2].metric("Depth", "✅ 3D" if result["depth_passed"] else "❌ Planar")
    if result.get("rppg_bpm"):
        top[2].metric("rPPG (advisory)", f"{result['rppg_bpm']:.0f} bpm")

    st.subheader("Stage scores")
    cols = st.columns(6)
    stage_map = [
        ("Position", "position_score"), ("Lighting", "lighting_score"),
        ("Blink", "blink_score"), ("Head-Turn", "challenge_score"),
        ("Depth", "depth_score"), ("Micro-Move", "motion_score"),
    ]
    for col, (label, key) in zip(cols, stage_map):
        with col:
            score_card(label, result[key])
    st.metric("Replay resistance", f"{result['replay_resistance_score']:.0f}/100")
    reason_list("Reasoning", result.get("reasons", []))
