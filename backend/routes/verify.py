"""Full-pipeline endpoint - runs Layers 1-3 and returns the final report."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from backend.routes.deps import parse_payload, read_frames, read_image
from backend.schemas.requests import VerifyRequest
from backend.schemas.responses import VerificationResponse
from backend.services.pipeline import run_full_pipeline

router = APIRouter(tags=["verify"])


@router.post("/verify", response_model=VerificationResponse)
async def verify(
    reference: UploadFile = File(..., description="Reference ID photo"),
    video: UploadFile | None = File(default=None),
    frames: list[UploadFile] | None = File(default=None),
    payload: str | None = Form(default=None),
) -> VerificationResponse:
    """Run the complete verification pipeline.

    Requires a ``reference`` ID photo plus a live capture (``video`` clip or
    multiple ``frames``). The ``payload`` JSON form field matches
    :class:`VerifyRequest` (challenge, fps, frame timestamps, camera metadata).
    """
    req = parse_payload(payload, VerifyRequest)
    ref_img = await read_image(reference, "reference image")
    parsed = await read_frames(video, frames)
    return run_full_pipeline(
        reference_img=ref_img,
        frames=parsed,
        timestamps_ms=req.frame_timestamps_ms,
        metadata=req.metadata,
        challenge=req.challenge,
        fps=req.fps,
    )
