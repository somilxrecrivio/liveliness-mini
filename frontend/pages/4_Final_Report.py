"""Page 4 - Final Report.

Aggregates the results of the three layer tests (Capture Integrity, Identity,
Liveness) that were run on the other pages, fuses them into the final
risk-weighted decision, and renders the explainable report. It does **not**
capture anything itself — run the three tests first, then open this page.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api_client  # noqa: E402
from components import decision_banner, gauge, reason_list  # noqa: E402

st.set_page_config(page_title="Final Report", page_icon="📋", layout="wide")
st.title("📋 Final Verification Report")
st.caption("Aggregates the three layer tests into the final decision: "
           "0.20·Capture + 0.35·Identity + 0.45·Liveness.")

cap = st.session_state.get("capture_result")
idn = st.session_state.get("identity_result")
liv = st.session_state.get("liveness_result")

# --- Status of each prerequisite test ---
st.subheader("Test status")
s1, s2, s3 = st.columns(3)
s1.metric("🎥 Capture Integrity", f"{cap['capture_score']:.0f}" if cap else "—",
          "done" if cap else "not run")
s2.metric("🪪 Identity", f"{idn['identity_score']:.0f}" if idn else "—",
          "done" if idn else "not run")
s3.metric("🧬 Liveness", f"{liv['liveness_score']:.0f}" if liv else "—",
          "done" if liv else "not run")

missing = [name for name, r in
           (("Capture Integrity", cap), ("Identity", idn), ("Liveness", liv)) if not r]
if missing:
    st.warning(
        "Run these tests first (sidebar pages): **" + ", ".join(missing) + "**. "
        "Their results are remembered and aggregated here."
    )

if st.button("🧮 Compute final decision", type="primary", disabled=bool(missing)):
    payload = {
        "capture_score": cap["capture_score"],
        "identity_score": idn["identity_score"],
        "liveness_score": liv["liveness_score"],
        "identity_match": bool(idn.get("match", False)),
        "quality_index": float(idn.get("quality_score", 100.0)),
    }
    with st.spinner("Fusing scores..."):
        try:
            st.session_state["final_decision"] = api_client.score(payload)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Request failed: {exc}")
            st.stop()

decision = st.session_state.get("final_decision")
if decision and not missing:
    st.divider()
    decision_banner(decision["status"], decision["final_score"], decision["confidence"])

    g = st.columns(4)
    with g[0]:
        gauge("Capture", decision["capture_score"], key="r_cap")
    with g[1]:
        gauge("Identity", decision["identity_score"], key="r_id")
    with g[2]:
        gauge("Liveness", decision["liveness_score"], key="r_liv")
    with g[3]:
        gauge("Final", decision["final_score"], key="r_final")

    st.divider()
    st.subheader("Layer-wise detail")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**🎥 Capture Integrity**")
        st.metric("Score", f"{cap['capture_score']:.0f}/100")
        st.caption(f"Injection risk: {cap['injection_score']:.0f}/100")
        reason_list("", cap.get("reasons", []))
    with col2:
        st.markdown("**🪪 Identity**")
        st.metric("Score", f"{idn['identity_score']:.0f}/100")
        st.caption(f"Similarity {idn['similarity']:.2f} · match: {'✅' if idn['match'] else '❌'}")
        reason_list("", idn.get("reasons", []))
    with col3:
        st.markdown("**🧬 Liveness**")
        st.metric("Score", f"{liv['liveness_score']:.0f}/100")
        st.caption(
            f"Blink {'✅' if liv['blink_detected'] else '❌'} · "
            f"Challenge {'✅' if liv['challenge_passed'] else '❌'} · "
            f"Depth {'✅' if liv['depth_passed'] else '❌'}"
        )
        reason_list("", liv.get("reasons", []))

    with st.expander("Raw decision JSON"):
        st.json(decision)
