"""Reusable Streamlit UI components (gauges, score cards, banners)."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

_BAND_COLORS = [
    (70, "#e74c3c"),    # rejected / review boundary
    (80, "#e67e22"),
    (90, "#f1c40f"),
    (95, "#2ecc71"),
    (101, "#27ae60"),
]


def _color_for(score: float) -> str:
    for limit, color in _BAND_COLORS:
        if score < limit:
            return color
    return "#27ae60"


def gauge(title: str, score: float, key: str | None = None) -> None:
    """Render a single 0-100 score gauge."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": title, "font": {"size": 16}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": _color_for(score)},
                "steps": [
                    {"range": [0, 70], "color": "#fdecea"},
                    {"range": [70, 80], "color": "#fef5e7"},
                    {"range": [80, 90], "color": "#fef9e7"},
                    {"range": [90, 100], "color": "#eafaf1"},
                ],
            },
        )
    )
    fig.update_layout(height=240, margin=dict(l=20, r=20, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True, key=key)


def score_card(label: str, score: float, subtitle: str = "") -> None:
    color = _color_for(score)
    st.markdown(
        f"""
        <div style="border:1px solid #e0e0e0;border-radius:12px;padding:16px;
                    text-align:center;background:#ffffff;">
            <div style="font-size:13px;color:#666;text-transform:uppercase;
                        letter-spacing:0.5px;">{label}</div>
            <div style="font-size:38px;font-weight:700;color:{color};">{score:.0f}</div>
            <div style="font-size:12px;color:#999;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def decision_banner(status: str, final_score: float, confidence: str) -> None:
    status_human = status.replace("_", " ").title()
    if status in ("verified", "verified_high_confidence", "verified_medium_confidence"):
        bg, icon = "#eafaf1", "✅"
    elif status == "manual_review":
        bg, icon = "#fef5e7", "🔎"
    else:
        bg, icon = "#fdecea", "⛔"
    st.markdown(
        f"""
        <div style="background:{bg};border-radius:14px;padding:24px;text-align:center;
                    margin-bottom:12px;">
            <div style="font-size:42px;">{icon}</div>
            <div style="font-size:26px;font-weight:700;">{status_human}</div>
            <div style="font-size:16px;color:#444;">Final Score: <b>{final_score:.1f}/100</b>
                &nbsp;·&nbsp; Confidence: <b>{confidence.title()}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def reason_list(title: str, items: list[str], icon: str = "•") -> None:
    if not items:
        return
    st.markdown(f"**{title}**")
    for it in items:
        st.markdown(f"{icon} {it}")
