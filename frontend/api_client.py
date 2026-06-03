"""Thin HTTP client for the verification backend.

Centralises the backend URL and request construction so every Streamlit page
shares the same logic and error handling.
"""
from __future__ import annotations

import os
from typing import Any

import requests

try:  # Allow running the frontend without a configured backend package import.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001
    pass

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
API_PREFIX = os.environ.get("API_PREFIX", "/api/v1")
TIMEOUT = 120


def _url(path: str) -> str:
    return f"{BACKEND_URL}{API_PREFIX}{path}"


def health() -> dict[str, Any]:
    resp = requests.get(_url("/health"), timeout=10)
    resp.raise_for_status()
    return resp.json()


def capture_check(files: list[tuple], data: dict[str, str]) -> dict[str, Any]:
    resp = requests.post(_url("/capture-check"), files=files, data=data, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def identity_check(reference: bytes, probe: bytes) -> dict[str, Any]:
    files = [
        ("reference", ("reference.jpg", reference, "image/jpeg")),
        ("probe", ("probe.jpg", probe, "image/jpeg")),
    ]
    resp = requests.post(_url("/identity-check"), files=files, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def liveness_check(files: list[tuple], data: dict[str, str]) -> dict[str, Any]:
    resp = requests.post(_url("/liveness-check"), files=files, data=data, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def verify(files: list[tuple], data: dict[str, str]) -> dict[str, Any]:
    resp = requests.post(_url("/verify"), files=files, data=data, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def score(payload: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(_url("/score"), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def backend_label() -> str:
    return f"{BACKEND_URL}{API_PREFIX}"
