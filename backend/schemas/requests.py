"""Request schemas for the verification API.

Most endpoints accept multipart uploads (images / video) so the heavy binary
payloads are not base64-inflated. These models capture the structured side
channel (frame timestamps, camera metadata, challenge selection).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ChallengeType(str, Enum):
    """Supported active-liveness head-turn challenges."""

    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    LOOK_UP = "look_up"
    LOOK_DOWN = "look_down"


class CameraMetadata(BaseModel):
    """Client-reported camera metadata for Layer 1 validation."""

    device_name: str | None = Field(default=None, description="Human-readable device label")
    device_id: str | None = Field(default=None, description="Unique device identifier")
    driver: str | None = Field(default=None, description="Driver / backend name")
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    fps: float | None = Field(default=None, ge=0)


class CaptureCheckRequest(BaseModel):
    """Structured payload accompanying a capture-integrity check.

    ``frame_timestamps_ms`` are client-side capture timestamps (milliseconds)
    used for frame-timing / jitter analysis. The frames themselves are sent as
    multipart files alongside this JSON blob.
    """

    frame_timestamps_ms: list[float] = Field(
        default_factory=list,
        description="Per-frame capture timestamps in milliseconds",
    )
    metadata: CameraMetadata = Field(default_factory=CameraMetadata)


class LivenessCheckRequest(BaseModel):
    """Structured payload accompanying a liveness check."""

    challenge: ChallengeType = Field(
        default=ChallengeType.TURN_LEFT,
        description="Head-turn challenge the user was asked to perform",
    )
    fps: float = Field(default=15.0, gt=0, description="Capture frame rate")
    frame_timestamps_ms: list[float] = Field(default_factory=list)


class VerifyRequest(BaseModel):
    """Structured payload for the full pipeline endpoint."""

    challenge: ChallengeType = Field(default=ChallengeType.TURN_LEFT)
    fps: float = Field(default=15.0, gt=0)
    frame_timestamps_ms: list[float] = Field(default_factory=list)
    metadata: CameraMetadata = Field(default_factory=CameraMetadata)


class ScoreRequest(BaseModel):
    """Fuse three already-computed layer scores into a final decision.

    Used by the Final Report, which aggregates results produced on the
    individual layer pages instead of re-running the whole pipeline.
    """

    capture_score: float = Field(..., ge=0, le=100)
    identity_score: float = Field(..., ge=0, le=100)
    liveness_score: float = Field(..., ge=0, le=100)
    identity_match: bool = Field(default=True)
    quality_index: float = Field(default=100.0, ge=0, le=100)
