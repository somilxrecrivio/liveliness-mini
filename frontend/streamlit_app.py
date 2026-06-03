"""Enterprise Liveness Verification - Streamlit frontend (Home).

Streamlit auto-discovers the multi-page app from the sibling ``pages/``
directory. This module renders the overview/home page and a backend status
panel, and seeds shared ``session_state``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Make sibling modules importable when launched via `streamlit run`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import api_client  # noqa: E402

st.set_page_config(
    page_title="Liveness Verification",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Shared state across pages.
st.session_state.setdefault("reference_image", None)
st.session_state.setdefault("liveness_video", None)
st.session_state.setdefault("capture_result", None)
st.session_state.setdefault("identity_result", None)
st.session_state.setdefault("liveness_result", None)
st.session_state.setdefault("final_report", None)

st.title("🛡️ Enterprise Liveness & Identity Verification")
st.caption("Lightweight · Training-free · CPU-only · Explainable")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(
        """
### How it works

This system answers three questions with a fully explainable pipeline:

1. **Is the stream from a real camera?** — Layer 1 *Capture Integrity*
   (frame-timing jitter, virtual-camera detection, temporal entropy).
2. **Is this the same person as the ID?** — Layer 2 *Identity Verification*
   (InsightFace ArcFace embeddings, multi-crop + aging-tolerant thresholds,
   landmark geometry).
3. **Is the person physically present & alive?** — Layer 3 *Active Liveness*
   (blink, randomized head-turn challenge, motion-parallax depth,
   micro-movement, replay detection).

A risk-weighted **Final Decision Engine** fuses the three layers:

```
final = 0.20·capture + 0.35·identity + 0.45·liveness
```

#### Recommended flow
Use the pages in the sidebar in order, or jump straight to **Final Report**
for the complete one-shot pipeline.
        """
    )

with col2:
    st.subheader("Backend status")
    st.caption(f"Endpoint: `{api_client.backend_label()}`")
    try:
        h = api_client.health()
        if h.get("models_ready"):
            st.success("Backend online · models ready")
        else:
            st.warning("Backend online · some models missing")
        st.json(h.get("details", {}))
    except Exception as exc:  # noqa: BLE001
        st.error("Backend unreachable")
        st.caption(f"{exc}")
        st.info("Start it with `./run_backend.sh` (or `uvicorn backend.app:app`).")

st.divider()
st.subheader("Decision bands")
bands = {
    "95 – 100": "Verified",
    "90 – 95": "Verified (High Confidence)",
    "80 – 90": "Verified (Medium Confidence)",
    "70 – 80": "Manual Review",
    "< 70": "Rejected",
}
cols = st.columns(len(bands))
for c, (rng, label) in zip(cols, bands.items()):
    c.metric(rng, label)
