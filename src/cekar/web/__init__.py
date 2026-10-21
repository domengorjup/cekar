"""HTML routes."""

from __future__ import annotations

from fastapi import APIRouter

from cekar.web import index

router = APIRouter()
for module in (index,):
    router.include_router(module.router)
