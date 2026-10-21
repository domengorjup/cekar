"""
API under ``/api/v1`` (read-only JSON, Bearer token outside Ingress).

Feature endpoints are added here as the app grows.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["api-v1"])


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the API is up."""
    return {"status": "ok"}
