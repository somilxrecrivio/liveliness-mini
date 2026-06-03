"""Central application configuration.

Loads settings from environment variables (and an optional ``.env`` file)
using pydantic-settings. Every tunable in the system is centralised here so
the services remain free of magic numbers.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of the ``backend`` package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Server ----
    app_name: str = Field(default="Enterprise Liveness Verification")
    app_version: str = Field(default="1.0.0")
    api_prefix: str = Field(default="/api/v1")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    # ---- Frontend ----
    backend_url: str = Field(default="http://localhost:8000")

    # ---- Models ----
    models_dir: str = Field(default="backend/models")
    insightface_model: str = Field(default="buffalo_l")
    ort_providers: str = Field(default="CPUExecutionProvider")
    det_size: int = Field(default=640)

    # ---- Decision bands (0-100) ----
    threshold_verified: float = Field(default=95)
    threshold_high: float = Field(default=90)
    threshold_medium: float = Field(default=80)
    threshold_review: float = Field(default=70)

    # ---- Identity ----
    # ArcFace (w600k_r50) cosine operating points tuned for KYC with aging
    # tolerance. Impostors typically score < 0.25, so these keep a wide margin.
    similarity_threshold_high: float = Field(default=0.40)
    similarity_threshold_low: float = Field(default=0.30)

    # ---- Final weights ----
    weight_capture: float = Field(default=0.20)
    weight_identity: float = Field(default=0.35)
    weight_liveness: float = Field(default=0.45)

    @property
    def models_path(self) -> Path:
        p = (PROJECT_ROOT / self.models_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def providers(self) -> list[str]:
        return [p.strip() for p in self.ort_providers.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()


settings = get_settings()
