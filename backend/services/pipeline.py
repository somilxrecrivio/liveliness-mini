"""End-to-end verification orchestrator.

Wires Layer 1 -> Layer 2 -> Layer 3 -> scoring -> reporting and supplies the
quality-compensation context. Used by the ``/verify`` endpoint and reused by
the per-layer endpoints where convenient.
"""
from __future__ import annotations

import numpy as np

from backend.schemas.requests import CameraMetadata, ChallengeType
from backend.schemas.responses import VerificationResponse
from backend.services.layer1_capture import analyze_capture
from backend.services.layer2_identity import verify_identity
from backend.services.layer3_liveness import verify_liveness
from backend.services.reporting import build_report
from backend.utils.face_engine import detect_faces
from backend.utils.image import sample_frames
from backend.utils.logger import logger
from backend.utils.quality import assess_quality, blur_metric


def _best_probe_frame(frames: list[np.ndarray]) -> np.ndarray:
    """Pick the sharpest frame that actually contains a detectable face.

    Choosing purely the sharpest frame can land on a mid-blink / turned-away /
    motion-blurred frame with no usable face. We rank candidates by sharpness
    and return the first one with a confident face, falling back to the
    sharpest frame overall.
    """
    if len(frames) == 1:
        return frames[0]
    sampled = sample_frames(frames, 12)
    ranked = sorted(sampled, key=blur_metric, reverse=True)
    for frame in ranked[:6]:  # cap detection cost
        faces = detect_faces(frame)
        if faces and float(faces[0].det_score) >= 0.5:
            return frame
    return ranked[0]


def _aggregate_quality(frames: list[np.ndarray]) -> tuple[float, list[str]]:
    sampled = sample_frames(frames, 8)
    reports = [assess_quality(f) for f in sampled]
    idx = float(np.mean([r.overall for r in reports]))
    issues: list[str] = []
    seen = set()
    for r in reports:
        for msg in r.issues:
            if msg not in seen:
                seen.add(msg)
                issues.append(msg)
    return idx, issues


def run_full_pipeline(
    reference_img: np.ndarray,
    frames: list[np.ndarray],
    timestamps_ms: list[float],
    metadata: CameraMetadata,
    challenge: ChallengeType,
    fps: float,
) -> VerificationResponse:
    """Run all three layers and return the composed, explainable report."""
    logger.info("Running full verification pipeline over {} frames.", len(frames))

    capture = analyze_capture(frames, timestamps_ms, metadata)
    probe = _best_probe_frame(frames)
    identity = verify_identity(reference_img, probe)
    liveness = verify_liveness(frames, challenge=challenge, fps=fps)

    quality_index, quality_issues = _aggregate_quality(frames)

    return build_report(
        capture=capture,
        identity=identity,
        liveness=liveness,
        quality_index=quality_index,
        quality_issues=quality_issues,
    )
