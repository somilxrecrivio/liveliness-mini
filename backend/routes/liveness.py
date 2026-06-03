"""Layer 3 endpoint - active liveness check."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from backend.routes.deps import parse_payload, read_frames
from backend.schemas.requests import LivenessCheckRequest
from backend.schemas.responses import LivenessResult
from backend.services.layer3_liveness import verify_liveness

router = APIRouter(tags=["liveness"])


@router.post("/liveness-check", response_model=LivenessResult)
async def liveness_check(
    video: UploadFile | None = File(default=None),
    frames: list[UploadFile] | None = File(default=None),
    payload: str | None = Form(default=None),
) -> LivenessResult:
    """Run Layer 3 active-liveness verification over a frame sequence.

    Send a ``video`` clip or multiple ``frames``. The ``payload`` JSON form
    field matches :class:`LivenessCheckRequest` (challenge + fps).
    """
    req = parse_payload(payload, LivenessCheckRequest)
    parsed = await read_frames(video, frames)
    return verify_liveness(parsed, challenge=req.challenge, fps=req.fps)
