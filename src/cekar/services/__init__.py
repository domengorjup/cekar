"""
Service layer: every create, update and delete goes through here (design D12).

Conventions for all modules in this package (FROZEN):

- Functions take a SQLAlchemy ``Session`` first. Writes then take
  ``actor_id`` (the acting user's id) and plain values. They ``flush`` but do
  not commit; the caller (``db.get_session``) commits.
- Every written row is stamped with ``sync.touch`` (``updated_at`` and
  ``seq``). Deletes are soft (``sync.soft_delete``), undo is ``sync.restore``.
- Reads exclude tombstones (``sync.live``) unless stated otherwise.
- Create functions accept an optional ``row_id``. If a row with that id
  already exists (live or deleted), it is returned unchanged and nothing is
  written, so a repeated create from a later offline client is harmless.
- Invalid input raises ``ServiceError(key, **params)`` where ``key`` is a
  message key in ``i18n/en.toml``. Money parameters are integer cents and
  their names end in ``_cents``; ``web.common.error_text`` formats them.
- Every function checks all its input before its first write, so a
  ``ServiceError`` never leaves partial changes behind. Any other exception
  is a bug: let it propagate so ``db.get_session`` rolls back.
- An unknown or deleted id raises ``ServiceError("error.not_found")``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class ServiceError(Exception):
    """
    Invalid input or state, as a catalog message key with parameters.

    Parameters
    ----------
    key : str
        Message key, e.g. ``"error.amount.not_positive"``.
    **params
        Placeholder values for the message. Money values are cents in
        parameters named ``*_cents`` (shown as ``{name}`` without the suffix).
    """

    def __init__(self, key: str, **params: object) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


@dataclass(frozen=True)
class ServiceWarning:
    """
    A non-blocking notice the user should confirm (e.g. an over-payment).

    Same ``key`` / ``params`` conventions as ``ServiceError``.
    """

    key: str
    params: dict[str, object] = field(default_factory=dict)
