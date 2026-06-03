"""Layer 1 - Capture Integrity.

Determines whether the stream originates from a *real* camera rather than a
virtual / injected / replayed source. Three independent signals are fused:

1. **Frame timing analysis** (60%) - real hardware exhibits natural,
   bounded jitter; injected streams are often suspiciously perfect or wildly
   irregular.
2. **Camera metadata validation** (20%) - virtual-camera device names and
   blacklisted drivers are flagged.
3. **Temporal entropy** (20%) - replay streams repeat frames and show
   deterministic cadence; we measure frame-difference entropy and variance.
"""
from __future__ import annotations

import numpy as np

from backend.schemas.requests import CameraMetadata
from backend.schemas.responses import CaptureResult
from backend.utils.image import to_gray
from backend.utils.logger import logger
from backend.utils.metrics import (
    clamp,
    coefficient_of_variation,
    linear_map,
    median_abs_deviation,
    shannon_entropy,
)

# Substrings that mark a software / virtual camera. Kept specific to avoid
# flagging legitimate hardware (e.g. "OBSBOT" webcams must NOT match "obs").
VIRTUAL_CAMERA_SIGNATURES = (
    "obs virtual", "obs-cam", "obsvirtual", "virtual camera", "virtualcam",
    "manycam", "snap camera", "snapcam", "xsplit", "droidcam", "epoccam",
    "ndi ", "splitcam", "v4l2loopback", "fake camera", "dummy camera",
    "screencam", "wirecast", "vmix", "avatarify", "deepfacelive", "facerig",
    "camtwist", "iriun", "obs-camera",
)
BLACKLISTED_DRIVERS = ("v4l2loopback", "obs-virtualcam", "akvirtualcamera")


def _timing_analysis(timestamps_ms: list[float]) -> tuple[float, float, float, list[str]]:
    """Return (timing_score, injection_score, median_fps, reasons)."""
    reasons: list[str] = []
    if len(timestamps_ms) < 3:
        reasons.append("Insufficient frame timing data; timing check is neutral.")
        return 60.0, 40.0, 0.0, reasons

    ts = np.asarray(sorted(timestamps_ms), dtype=np.float64)
    deltas = np.diff(ts)
    deltas = deltas[deltas > 0]
    if deltas.size < 2:
        reasons.append("Degenerate frame timestamps; timing check is neutral.")
        return 55.0, 45.0, 0.0, reasons

    median_dt = float(np.median(deltas))
    median_fps = 1000.0 / median_dt if median_dt > 0 else 0.0
    mad = median_abs_deviation(deltas)
    jitter_ratio = mad / median_dt if median_dt > 0 else 0.0  # normalized jitter
    cv = coefficient_of_variation(deltas)

    # Natural cameras: small but non-zero jitter (~0.02 - 0.25 of cadence).
    # Zero jitter  -> deterministic / injected.
    # Huge jitter  -> unstable / synthetic / dropped-frame injection.
    if jitter_ratio < 0.005:
        injection = 85.0
        reasons.append("Frame cadence is unnaturally perfect (deterministic timing).")
    elif jitter_ratio > 0.8:
        injection = 70.0
        reasons.append("Frame timing is highly irregular; possible stream tampering.")
    else:
        # Map the 'natural' band to low injection risk.
        injection = clamp(linear_map(abs(jitter_ratio - 0.12), 0.0, 0.5, 5.0, 60.0))

    # Penalise implausible frame rates.
    if median_fps < 5 or median_fps > 120:
        injection = clamp(injection + 15.0)
        reasons.append(f"Reported frame rate ({median_fps:.1f} fps) is out of expected range.")

    # Excessive cadence variance independent of jitter band.
    if cv > 1.0:
        injection = clamp(injection + 10.0)

    timing_score = clamp(100.0 - injection)
    if not reasons:
        reasons.append("Real hardware timing observed with natural frame jitter.")
    return timing_score, clamp(injection), median_fps, reasons


def _metadata_validation(meta: CameraMetadata) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 100.0
    haystack = " ".join(
        str(x).lower() for x in (meta.device_name, meta.device_id, meta.driver) if x
    )
    if not haystack:
        reasons.append("No camera metadata supplied; metadata trust reduced.")
        return 65.0, reasons

    for sig in VIRTUAL_CAMERA_SIGNATURES:
        if sig in haystack:
            score = 5.0
            reasons.append(f"Virtual-camera signature detected: '{sig}'.")
            break

    for drv in BLACKLISTED_DRIVERS:
        if meta.driver and drv in meta.driver.lower():
            score = min(score, 5.0)
            reasons.append(f"Blacklisted driver detected: '{drv}'.")

    if score > 90:
        reasons.append("No virtual-camera signatures found in device metadata.")
    return clamp(score), reasons


def _temporal_entropy(frames: list[np.ndarray]) -> tuple[float, list[str]]:
    """Detect repeated frames / deterministic cadence via diff entropy."""
    reasons: list[str] = []
    if len(frames) < 3:
        reasons.append("Too few frames for temporal entropy analysis.")
        return 60.0, reasons

    grays = [to_gray(f).astype(np.float32) for f in frames]
    # Resize to a common small size for robust comparison.
    import cv2

    grays = [cv2.resize(g, (160, 120)) for g in grays]

    diffs = []
    repeated = 0
    for a, b in zip(grays, grays[1:]):
        d = np.abs(a - b)
        mean_diff = float(d.mean())
        diffs.append(mean_diff)
        if mean_diff < 0.5:  # near-identical consecutive frames
            repeated += 1

    diffs_arr = np.asarray(diffs)
    ent = shannon_entropy(diffs_arr, bins=32)
    temporal_var = float(np.var(diffs_arr))
    repeat_ratio = repeated / len(diffs)

    # High entropy + healthy variance + few repeats => authentic.
    ent_component = linear_map(ent, 0.5, 3.5, 0.0, 100.0)
    var_component = linear_map(temporal_var, 0.2, 10.0, 0.0, 100.0)
    score = clamp(0.6 * ent_component + 0.4 * var_component)

    if repeat_ratio > 0.3:
        score = clamp(score - 40.0 * repeat_ratio)
        reasons.append(f"{repeat_ratio*100:.0f}% of frames are near-duplicates (replay indicator).")
    if temporal_var < 0.2:
        reasons.append("Extremely low temporal variance; deterministic/static feed suspected.")
    if not reasons:
        reasons.append("Natural temporal variation detected; no replay characteristics.")
    return score, reasons


def analyze_capture(
    frames: list[np.ndarray],
    timestamps_ms: list[float],
    metadata: CameraMetadata,
) -> CaptureResult:
    """Run the full Layer 1 capture-integrity analysis."""
    timing_score, injection_score, median_fps, t_reasons = _timing_analysis(timestamps_ms)
    metadata_score, m_reasons = _metadata_validation(metadata)
    entropy_score, e_reasons = _temporal_entropy(frames)

    capture_score = clamp(
        0.60 * timing_score + 0.20 * metadata_score + 0.20 * entropy_score
    )

    reasons = t_reasons + m_reasons + e_reasons
    logger.info(
        "Layer1 capture_score={:.1f} (timing={:.1f}, meta={:.1f}, entropy={:.1f}, inject={:.1f})",
        capture_score, timing_score, metadata_score, entropy_score, injection_score,
    )

    return CaptureResult(
        capture_score=round(capture_score, 1),
        timing_score=round(timing_score, 1),
        metadata_score=round(metadata_score, 1),
        entropy_score=round(entropy_score, 1),
        injection_score=round(injection_score, 1),
        median_fps=round(median_fps, 2),
        reasons=reasons,
    )
