"""Response schemas for the verification API.

Every layer returns a sub-result with its score, granular sub-scores and a list
of human-readable reasons. The final response composes them with the overall
decision, confidence and warnings.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DecisionStatus(str, Enum):
    VERIFIED = "verified"
    VERIFIED_HIGH = "verified_high_confidence"
    VERIFIED_MEDIUM = "verified_medium_confidence"
    MANUAL_REVIEW = "manual_review"
    REJECTED = "rejected"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CaptureResult(BaseModel):
    capture_score: float = Field(..., ge=0, le=100)
    timing_score: float = Field(..., ge=0, le=100)
    metadata_score: float = Field(..., ge=0, le=100)
    entropy_score: float = Field(..., ge=0, le=100)
    injection_score: float = Field(..., ge=0, le=100, description="Higher = more injection risk")
    median_fps: float = Field(default=0.0, ge=0)
    reasons: list[str] = Field(default_factory=list)


class IdentityResult(BaseModel):
    identity_score: float = Field(..., ge=0, le=100)
    similarity: float = Field(..., ge=-1, le=1)
    threshold: float = Field(..., description="Quality-adaptive decision threshold")
    match: bool = False
    landmark_score: float = Field(default=0.0, ge=0, le=100)
    quality_score: float = Field(default=0.0, ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class LivenessResult(BaseModel):
    liveness_score: float = Field(..., ge=0, le=100)
    position_score: float = Field(default=0.0, ge=0, le=100)
    lighting_score: float = Field(default=0.0, ge=0, le=100)
    blink_score: float = Field(default=0.0, ge=0, le=100)
    challenge_score: float = Field(default=0.0, ge=0, le=100)
    depth_score: float = Field(default=0.0, ge=0, le=100)
    motion_score: float = Field(default=0.0, ge=0, le=100)
    replay_resistance_score: float = Field(default=0.0, ge=0, le=100)
    blink_detected: bool = False
    challenge_passed: bool = False
    depth_passed: bool = False
    rppg_bpm: float | None = Field(default=None, description="Advisory only; never gates")
    reasons: list[str] = Field(default_factory=list)


class QualityInfo(BaseModel):
    capture_quality_index: float = Field(..., ge=0, le=100)
    confidence_penalty_pct: float = Field(..., ge=0, le=100)
    issues: list[str] = Field(default_factory=list)


class VerificationResponse(BaseModel):
    """Top-level response for the full pipeline."""

    status: DecisionStatus
    capture_score: float = Field(..., ge=0, le=100)
    identity_score: float = Field(..., ge=0, le=100)
    liveness_score: float = Field(..., ge=0, le=100)
    final_score: float = Field(..., ge=0, le=100)
    confidence: ConfidenceLevel
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Detailed breakdown (the explainable report).
    capture: CaptureResult | None = None
    identity: IdentityResult | None = None
    liveness: LivenessResult | None = None
    quality: QualityInfo | None = None
    notes: list[str] = Field(default_factory=list)


class DecisionResponse(BaseModel):
    """Fused decision from three pre-computed layer scores."""

    status: DecisionStatus
    final_score: float = Field(..., ge=0, le=100)
    confidence: ConfidenceLevel
    capture_score: float = Field(..., ge=0, le=100)
    identity_score: float = Field(..., ge=0, le=100)
    liveness_score: float = Field(..., ge=0, le=100)


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str
    models_ready: bool
    details: dict[str, bool] = Field(default_factory=dict)
