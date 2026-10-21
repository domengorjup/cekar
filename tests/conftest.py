"""
Shared fixtures: in-memory migrated database, session, app and client, plus
invented household members (Ana, Bor, Cene).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from cekar.app import create_app
from cekar.config import Settings
from cekar.db import make_engine, make_session_factory, run_migrations
from cekar.models import User
from cekar.services import sync

# Fixed base time for member order: Ana joined first, then Bor, then Cene.
MEMBER_EPOCH = datetime(2026, 1, 1, 12, 0, 0)


@pytest.fixture
def engine() -> Iterator[Engine]:
    """In-memory SQLite engine with all migrations applied."""
    engine = make_engine()
    run_migrations(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Database session; uncommitted changes are rolled back at the end."""
    with make_session_factory(engine)() as session:
        yield session
        session.rollback()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Default standalone settings pointing at a temporary data dir."""
    return Settings(data_dir=tmp_path)


@pytest.fixture
def client(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    """Test client for the app (startup runs, sharing the in-memory engine)."""
    with TestClient(create_app(settings, engine)) as test_client:
        yield test_client


@pytest.fixture
def client_for(engine: Engine, tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    """
    Factory for extra clients: ``client_for(host="172.30.32.2", mode=Mode.ADDON)``.

    Keyword arguments other than ``host`` go to ``Settings``. Redirects are
    not followed, so tests can check ``Location``. All clients share the
    in-memory engine and are closed at the end of the test.
    """
    clients: list[TestClient] = []

    def make(*, host: str = "testclient", **settings_kw: object) -> TestClient:
        app = create_app(Settings(data_dir=tmp_path, **settings_kw), engine)
        test_client = TestClient(app, client=(host, 50000), follow_redirects=False)
        clients.append(test_client.__enter__())
        return test_client

    yield make
    for test_client in clients:
        test_client.__exit__(None, None, None)


@pytest.fixture
def add_user(session: Session) -> Callable[..., User]:
    """
    Factory that writes a user directly (services may still be stubs).

    ``add_user("Tablet", member=False, ha_user_id="abc")``; members get
    ``member_since`` one minute after the previous member, so the call order
    is the member display order. The session is committed, so clients see
    the user too.
    """
    count = 0

    def make(
        display_name: str,
        *,
        member: bool = True,
        ha_user_id: str | None = None,
        username: str | None = None,
    ) -> User:
        nonlocal count
        count += 1
        user = User(
            display_name=display_name,
            username=username,
            ha_user_id=ha_user_id,
            is_member=member,
            member_since=MEMBER_EPOCH + timedelta(minutes=count) if member else None,
        )
        sync.touch(user, session)
        session.commit()
        return user

    return make


@dataclass(frozen=True)
class People:
    """The invented test household, in member display order."""

    ana: User
    bor: User
    cene: User

    @property
    def order(self) -> list[str]:
        """User ids in member display order."""
        return [self.ana.id, self.bor.id, self.cene.id]


@pytest.fixture
def people(add_user: Callable[..., User]) -> People:
    """Members Ana, Bor and Cene, joined in that order."""
    return People(ana=add_user("Ana"), bor=add_user("Bor"), cene=add_user("Cene"))


@pytest.fixture
def two_people(add_user: Callable[..., User]) -> tuple[User, User]:
    """Only Ana and Bor as members (the common two-person household)."""
    return add_user("Ana"), add_user("Bor")
