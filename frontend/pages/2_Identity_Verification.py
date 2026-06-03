"""Page 2 - Identity Verification (Layer 2)."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api_client  # noqa: E402
from capture import camera_help, single_camera  # noqa: E402
from components import gauge, reason_list, score_card  # noqa: E402

st.set_page_config(page_title="Identity Verification", page_icon="🪪", layout="wide")
st.title("🪪 Layer 2 · Identity Verification")
st.caption("Match the live user against a reference ID photo — robust to aging, beards and glasses.")

left, right = st.columns(2)

with left:
    st.subheader("Reference ID image")
    ref_mode = st.radio("Reference source", ["📁 Upload", "📷 Camera"],
                        horizontal=True, key="ref_mode")
    if ref_mode == "📁 Upload":
        ref_upload = st.file_uploader("Aadhaar / Passport / License photo", type=["jpg", "jpeg", "png"])
        if ref_upload is not None:
            st.session_state["reference_image"] = ref_upload.getvalue()
    else:
        ref_cam = single_camera("ref", "Capture the ID document / reference photo")
        if ref_cam is not None:
            st.session_state["reference_image"] = ref_cam
    if st.session_state.get("reference_image"):
        st.image(st.session_state["reference_image"], caption="Reference", width=240)

with right:
    st.subheader("Live capture")
    probe_mode = st.radio("Probe source", ["📷 Camera", "📁 Upload"],
                          horizontal=True, key="probe_mode")
    if probe_mode == "📷 Camera":
        camera_help()
        probe = single_camera("probe", "Look at the camera")
        if probe is not None:
            st.session_state["_probe_bytes"] = probe
    else:
        probe_upload = st.file_uploader("Live photo", type=["jpg", "jpeg", "png"], key="probe_up")
        if probe_upload is not None:
            st.session_state["_probe_bytes"] = probe_upload.getvalue()
    if st.session_state.get("_probe_bytes"):
        st.image(st.session_state["_probe_bytes"], caption="Live capture", width=240)

if st.button("Verify identity", type="primary"):
    ref = st.session_state.get("reference_image")
    probe_bytes = st.session_state.get("_probe_bytes")
    if not ref:
        st.warning("Provide a reference image first.")
        st.stop()
    if not probe_bytes:
        st.warning("Provide a live photo first.")
        st.stop()
    with st.spinner("Comparing embeddings..."):
        try:
            result = api_client.identity_check(ref, probe_bytes)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Request failed: {exc}")
            st.stop()
    st.session_state["identity_result"] = result

result = st.session_state.get("identity_result")
if result:
    st.divider()
    g1, g2, g3 = st.columns([1, 1, 1])
    with g1:
        gauge("Identity Match", result["identity_score"], key="id_g")
    with g2:
        score_card("Similarity", result["similarity"] * 100, f"threshold {result['threshold']:.2f}")
    with g3:
        score_card("Geometry", result["landmark_score"], "age-stable")
    if result["match"]:
        st.success(f"✅ Match (similarity {result['similarity']:.2f} ≥ {result['threshold']:.2f})")
    else:
        st.error(f"❌ No match (similarity {result['similarity']:.2f} < {result['threshold']:.2f})")
    reason_list("Reasoning", result.get("reasons", []))
