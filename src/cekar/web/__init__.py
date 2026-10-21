"""HTML routes."""

from __future__ import annotations

import importlib

from fastapi import APIRouter

# Route modules, in the order their routes are matched. Fixed paths such as
# ``/lists/new`` must come before ``/lists/{list_id}``, so each module is
# internally ordered and the modules do not share path prefixes.
MODULES = ("identity", "lists", "trips", "expenses", "balances", "settings")


def build_router() -> APIRouter:
    """Import the route modules and return one router with all routes."""
    importlib.import_module("cekar.web.ui")
    router = APIRouter()
    for name in MODULES:
        module = importlib.import_module(f"cekar.web.{name}")
        router.include_router(module.router)
    return router


def __getattr__(name: str) -> APIRouter:
    # ``from cekar.web import router`` builds the router on first use. The
    # route modules import ``cekar.identity``, and ``cekar.identity`` imports
    # ``cekar.web.common``; building lazily keeps both import orders working.
    if name == "router":
        global router
        router = build_router()
        return router
    raise AttributeError(name)
