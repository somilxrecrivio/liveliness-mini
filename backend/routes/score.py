"""Decision-fusion endpoint - combine three layer scores into a final decision.

Used by the Final Report page, which aggregates the results computed on the
individual layer pages rather than re-running the whole pipeline.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.requests import ScoreRequest
from backend.schemas.responses import DecisionResponse
from backend.services.scoring import score_pipeline
from backend.utils.quality import confidence_penalty

router = APIRouter(tags=["score"])


@router.post("/score", response_model=DecisionResponse)
async def score(req: ScoreRequest) -> DecisionResponse:
    """Fuse capture/identity/liveness scores into the final risk-weighted decision."""
    penalty_pct = confidence_penalty(req.quality_index) * 100.0
    breakdown = score_pipeline(
        capture_score=req.capture_score,
        identity_score=req.identity_score,
        liveness_score=req.liveness_score,
        quality_penalty_pct=penalty_pct,
        identity_match=req.identity_match,
    )
    return DecisionResponse(
        status=breakdown.status,
        final_score=breakdown.final_score,
        confidence=breakdown.confidence,
        capture_score=breakdown.capture_score,
        identity_score=breakdown.identity_score,
        liveness_score=breakdown.liveness_score,
    )
