"""Health-check endpoint with model-readiness reporting."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.schemas.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report service status and whether models are present on disk."""
    models_path = settings.models_path
    details = {
        "face_landmarker": (models_path / "face_landmarker.task").exists(),
        "blaze_face": (models_path / "blaze_face_short_range.tflite").exists(),
        "insightface": any((models_path / "insightface").rglob("*.onnx")),
    }
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        models_ready=all(details.values()),
        details=details,
    )
