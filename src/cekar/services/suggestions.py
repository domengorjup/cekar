"""
Item-name suggestions from history (design D8). FROZEN SIGNATURES;
implemented in group 4.

Source: all live item rows of all lists (cleared items count, deleted ones do
not), grouped by ``name_key``. Each row is one use, dated by its
``created_at``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

SUGGESTION_LIMIT = 8
HALF_LIFE_DAYS = 30


@dataclass(frozen=True)
class Suggestion:
    """One suggested name: the most recently used spelling and its key."""

    name: str
    name_key: str


def suggest(
    session: Session,
    list_id: str,
    query: str,
    now: datetime | None = None,
    limit: int = SUGGESTION_LIMIT,
) -> list[Suggestion]:
    """
    Return at most ``limit`` names matching ``query`` for the add field.

    Matching is on ``normalise_name(query)`` against ``name_key``. Names that
    start with it come before names that only contain it; within each group
    by score ``uses * 0.5 ** (days_since_last_use / HALF_LIFE_DAYS)``,
    descending, then by name. Names unchecked on ``list_id`` are left out.
    A blank query gives ``[]``. ``now`` (naive UTC) defaults to the current
    time; tests pass a fixed value.
    """
    raise NotImplementedError
