"""Reporting Engine.

Assembles the explainable, human-readable verification report from the three
layer results plus the quality-compensation information. Produces the final
:class:`VerificationResponse`.
"""
from __future__ import annotations

from backend.schemas.responses import (
    CaptureResult,
    ConfidenceLevel,
    DecisionStatus,
    IdentityResult,
    LivenessResult,
    QualityInfo,
    VerificationResponse,
)
from backend.services.scoring import score_pipeline
from backend.utils.logger import logger
from backend.utils.quality import confidence_penalty

_STATUS_LABEL = {
    DecisionStatus.VERIFIED: "Verified",
    DecisionStatus.VERIFIED_HIGH: "Verified (High Confidence)",
    DecisionStatus.VERIFIED_MEDIUM: "Verified (Medium Confidence)",
    DecisionStatus.MANUAL_REVIEW: "Manual Review",
    DecisionStatus.REJECTED: "Rejected",
}


def status_label(status: DecisionStatus) -> str:
    return _STATUS_LABEL.get(status, status.value)


def _gather_warnings(
    capture: CaptureResult, identity: IdentityResult, liveness: LivenessResult,
    quality_index: float,
) -> list[str]:
    warnings: list[str] = []
    if capture.injection_score >= 50:
        warnings.append("Elevated stream-injection risk; verify camera source.")
    if not identity.match:
        warnings.append("Identity did not meet the match threshold.")
    if not liveness.challenge_passed:
        warnings.append("Active head-turn challenge was not clearly completed.")
    if not liveness.depth_passed:
        warnings.append("Depth/parallax evidence was weak; screen replay not excluded.")
    if liveness.replay_resistance_score < 50:
        warnings.append("Possible replay characteristics detected.")
    if quality_index < 60:
        warnings.append("Low capture quality reduced overall confidence.")
    return warnings


def build_report(
    capture: CaptureResult,
    identity: IdentityResult,
    liveness: LivenessResult,
    quality_index: float,
    quality_issues: list[str],
) -> VerificationResponse:
    """Compose the final, explainable verification response."""
    penalty_frac = confidence_penalty(quality_index)
    penalty_pct = round(penalty_frac * 100.0, 1)

    breakdown = score_pipeline(
        capture_score=capture.capture_score,
        identity_score=identity.identity_score,
        liveness_score=liveness.liveness_score,
        quality_penalty_pct=penalty_pct,
        identity_match=identity.match,
    )

    reasons: list[str] = []
    reasons.extend(capture.reasons)
    reasons.extend(identity.reasons)
    reasons.extend(liveness.reasons)

    warnings = _gather_warnings(capture, identity, liveness, quality_index)

    notes: list[str] = []
    if penalty_pct > 0:
        notes.append(
            f"Capture quality reduced confidence by ~{penalty_pct:.0f}% "
            "(genuine-user protection: not counted as a failure)."
        )
    notes.extend(quality_issues)
    if identity.threshold < 0.5 and identity.match:
        notes.append("Reference image appears aged/low-quality; adaptive threshold applied.")

    quality_info = QualityInfo(
        capture_quality_index=round(quality_index, 1),
        confidence_penalty_pct=penalty_pct,
        issues=quality_issues,
    )

    response = VerificationResponse(
        status=breakdown.status,
        capture_score=breakdown.capture_score,
        identity_score=breakdown.identity_score,
        liveness_score=breakdown.liveness_score,
        final_score=breakdown.final_score,
        confidence=breakdown.confidence,
        reasons=reasons,
        warnings=warnings,
        capture=capture,
        identity=identity,
        liveness=liveness,
        quality=quality_info,
        notes=notes,
    )
    logger.info(
        "Report: status={} final={:.1f} confidence={}",
        breakdown.status.value, breakdown.final_score, breakdown.confidence.value,
    )
    return response


def single_layer_response(
    *,
    capture: CaptureResult | None = None,
    identity: IdentityResult | None = None,
    liveness: LivenessResult | None = None,
) -> VerificationResponse:
    """Wrap a single-layer result in a partial response (for per-layer endpoints)."""
    cap = capture.capture_score if capture else 0.0
    idn = identity.identity_score if identity else 0.0
    liv = liveness.liveness_score if liveness else 0.0
    reasons: list[str] = []
    for r in (capture, identity, liveness):
        if r is not None:
            reasons.extend(r.reasons)

    confidence = ConfidenceLevel.MEDIUM
    return VerificationResponse(
        status=DecisionStatus.MANUAL_REVIEW,
        capture_score=cap,
        identity_score=idn,
        liveness_score=liv,
        final_score=round(max(cap, idn, liv), 1),
        confidence=confidence,
        reasons=reasons,
        capture=capture,
        identity=identity,
        liveness=liveness,
    )
