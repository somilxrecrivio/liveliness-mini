"""Layer 1 endpoint - capture integrity check."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from backend.routes.deps import parse_payload, read_frames
from backend.schemas.requests import CaptureCheckRequest
from backend.schemas.responses import CaptureResult
from backend.services.layer1_capture import analyze_capture

router = APIRouter(tags=["capture"])


@router.post("/capture-check", response_model=CaptureResult)
async def capture_check(
    video: UploadFile | None = File(default=None),
    frames: list[UploadFile] | None = File(default=None),
    payload: str | None = Form(default=None),
) -> CaptureResult:
    """Run Layer 1 capture-integrity analysis.

    Send frames as a ``video`` file or multiple ``frames`` image files, and an
    optional ``payload`` JSON form field matching :class:`CaptureCheckRequest`
    (frame timestamps + camera metadata).
    """
    req = parse_payload(payload, CaptureCheckRequest)
    parsed = await read_frames(video, frames)
    return analyze_capture(parsed, req.frame_timestamps_ms, req.metadata)
