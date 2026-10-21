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

from sqlalchemy import select
from sqlalchemy.orm import Session

from cekar.models import Item, utc_now
from cekar.services import sync
from cekar.services.lists import normalise_name

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
    key = normalise_name(query)
    if not key:
        return []
    now = now or utc_now()
    on_list = set(
        session.scalars(
            sync.live(
                select(Item.name_key).where(
                    Item.list_id == list_id,
                    Item.checked_at.is_(None),
                    Item.cleared_at.is_(None),
                )
            )
        )
    )
    rows = session.execute(
        sync.live(
            select(Item.name, Item.name_key, Item.created_at).where(
                Item.name_key.contains(key, autoescape=True)
            )
        ).order_by(Item.created_at)
    )
    # name_key -> [uses, last use, most recently used spelling]
    groups: dict[str, list] = {}
    for name, name_key, created_at in rows:
        if name_key in on_list:
            continue
        group = groups.setdefault(name_key, [0, created_at, name])
        group[0] += 1
        if created_at >= group[1]:
            group[1] = created_at
            group[2] = name

    def rank(name_key: str) -> tuple[int, float, str]:
        uses, last_use, name = groups[name_key]
        days = max((now - last_use).total_seconds() / 86400, 0)
        score = uses * 0.5 ** (days / HALF_LIFE_DAYS)
        return (0 if name_key.startswith(key) else 1, -score, name)

    ordered = sorted(groups, key=rank)
    return [Suggestion(name=groups[k][2], name_key=k) for k in ordered[:limit]]
