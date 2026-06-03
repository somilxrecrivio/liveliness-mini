"""Shared route helpers for parsing multipart uploads into frames."""
from __future__ import annotations

import json

import numpy as np
from fastapi import HTTPException, UploadFile

from backend.utils.image import decode_image_bytes, decode_video_bytes
from backend.utils.logger import logger


async def read_frames(
    video: UploadFile | None,
    frames: list[UploadFile] | None,
    *,
    max_frames: int = 90,
) -> list[np.ndarray]:
    """Read frames from either a single video upload or many image uploads."""
    out: list[np.ndarray] = []
    if video is not None:
        data = await video.read()
        try:
            out = decode_video_bytes(data, max_frames=max_frames)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid video: {exc}") from exc
    elif frames:
        for f in frames:
            data = await f.read()
            try:
                out.append(decode_image_bytes(data))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid frame '{f.filename}': {exc}") from exc
    if not out:
        raise HTTPException(
            status_code=400,
            detail="Provide either a 'video' file or one or more 'frames' image files.",
        )
    logger.debug("Parsed {} frames from upload.", len(out))
    return out


async def read_image(file: UploadFile, label: str = "image") -> np.ndarray:
    data = await file.read()
    try:
        return decode_image_bytes(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label}: {exc}") from exc


def parse_payload(payload: str | None, model):
    """Parse an optional JSON form field into a pydantic model (defaults if None)."""
    if not payload:
        return model()
    try:
        return model(**json.loads(payload))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid payload JSON: {exc}") from exc
