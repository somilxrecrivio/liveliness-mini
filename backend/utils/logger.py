"""Production-grade logging configuration built on Loguru.

Provides a single ``logger`` instance and a ``configure_logging`` helper that
sets up console + rotating file sinks. Import ``logger`` everywhere instead of
the standard library ``logging`` module.
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from backend.config import PROJECT_ROOT, settings

_CONFIGURED = False


def configure_logging() -> None:
    """Configure Loguru sinks. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logger.remove()

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=fmt,
        colorize=True,
        backtrace=False,
        diagnose=False,
    )

    log_dir: Path = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "liveness_{time:YYYY-MM-DD}.log",
        level=settings.log_level.upper(),
        format=fmt,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    _CONFIGURED = True
    logger.debug("Logging configured (level={})", settings.log_level.upper())


configure_logging()

__all__ = ["logger", "configure_logging"]
