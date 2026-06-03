"""Automatic model download & cache management.

Downloads the MediaPipe Face Landmarker, BlazeFace detector and triggers the
InsightFace model pack download. Downloads are:

* **lazy**   - only fetched if missing,
* **atomic** - written to a ``.part`` file then renamed,
* **retried**- with exponential back-off,
* **verified**- a sha256 manifest guards against cache corruption.

Run directly to provision everything::

    python -m backend.utils.model_manager
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from backend.config import settings
from backend.utils.logger import logger

MEDIAPIPE_BASE = "https://storage.googleapis.com/mediapipe-models"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    url: str
    filename: str


MODEL_SPECS: list[ModelSpec] = [
    ModelSpec(
        name="face_landmarker",
        url=f"{MEDIAPIPE_BASE}/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        filename="face_landmarker.task",
    ),
    ModelSpec(
        name="blaze_face_short_range",
        url=f"{MEDIAPIPE_BASE}/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
        filename="blaze_face_short_range.tflite",
    ),
]


def _manifest_path() -> Path:
    return settings.models_path / "manifest.json"


def _load_manifest() -> dict:
    p = _manifest_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            logger.warning("Model manifest corrupt; rebuilding.")
    return {}


def _save_manifest(manifest: dict) -> None:
    _manifest_path().write_text(json.dumps(manifest, indent=2))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_atomic(spec: ModelSpec, dest: Path, retries: int = 3) -> None:
    """Download ``spec.url`` to ``dest`` atomically with retries."""
    part = dest.with_suffix(dest.suffix + ".part")
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            logger.info("Downloading {} (attempt {}/{})", spec.name, attempt, retries)
            with requests.get(spec.url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with part.open("wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        if chunk:
                            fh.write(chunk)
            part.replace(dest)
            logger.success("Downloaded {} -> {}", spec.name, dest.name)
            return
        except Exception as exc:  # noqa: BLE001 - want broad retry semantics
            last_err = exc
            logger.warning("Download failed for {}: {}", spec.name, exc)
            if part.exists():
                part.unlink(missing_ok=True)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to download {spec.name} after {retries} attempts") from last_err


def ensure_mediapipe_models() -> dict[str, Path]:
    """Ensure MediaPipe models exist & are integrity-checked. Returns paths."""
    manifest = _load_manifest()
    paths: dict[str, Path] = {}
    for spec in MODEL_SPECS:
        dest = settings.models_path / spec.filename
        needs_download = not dest.exists()

        if dest.exists() and spec.name in manifest:
            actual = _sha256(dest)
            if actual != manifest[spec.name]:
                logger.warning("Checksum mismatch for {}; re-downloading.", spec.name)
                needs_download = True

        if needs_download:
            _download_atomic(spec, dest)
            manifest[spec.name] = _sha256(dest)

        paths[spec.name] = dest

    _save_manifest(manifest)
    return paths


def ensure_insightface_model() -> Path:
    """Trigger the InsightFace model-pack download into the models dir.

    InsightFace stores packs under ``<root>/models/<name>``. We initialise a
    ``FaceAnalysis`` object once which downloads on first use, then return the
    pack directory.
    """
    root = settings.models_path / "insightface"
    root.mkdir(parents=True, exist_ok=True)
    pack_dir = root / "models" / settings.insightface_model
    if pack_dir.exists() and any(pack_dir.glob("*.onnx")):
        logger.info("InsightFace pack '{}' already present.", settings.insightface_model)
        return pack_dir

    try:
        from insightface.app import FaceAnalysis

        logger.info("Provisioning InsightFace pack '{}' (CPU)...", settings.insightface_model)
        app = FaceAnalysis(
            name=settings.insightface_model,
            root=str(root),
            providers=settings.providers,
        )
        app.prepare(ctx_id=-1, det_size=(settings.det_size, settings.det_size))
        logger.success("InsightFace pack ready: {}", pack_dir)
    except Exception as exc:  # noqa: BLE001
        logger.error("InsightFace provisioning failed: {}", exc)
        raise
    return pack_dir


def ensure_all_models() -> dict[str, Path]:
    """Provision every model required by the system."""
    paths = ensure_mediapipe_models()
    paths["insightface"] = ensure_insightface_model()
    return paths


def main() -> None:
    logger.info("Provisioning all models into {}", settings.models_path)
    paths = ensure_all_models()
    for name, path in paths.items():
        logger.info("  {:<22} {}", name, path)
    logger.success("All models provisioned.")


if __name__ == "__main__":
    main()
