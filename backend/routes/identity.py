"""Layer 2 endpoint - identity verification check."""
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from backend.routes.deps import read_image
from backend.schemas.responses import IdentityResult
from backend.services.layer2_identity import verify_identity

router = APIRouter(tags=["identity"])


@router.post("/identity-check", response_model=IdentityResult)
async def identity_check(
    reference: UploadFile = File(..., description="Reference ID photo"),
    probe: UploadFile = File(..., description="Live capture of the user"),
) -> IdentityResult:
    """Run Layer 2 identity verification between a reference photo and a probe."""
    ref_img = await read_image(reference, "reference image")
    probe_img = await read_image(probe, "probe image")
    return verify_identity(ref_img, probe_img)
