# Testing

Run everything with `uv run pytest`.

- `tests/conftest.py` provides a migrated in-memory `engine`, a `session`, a `settings` and a `client` fixture, plus helpers for the household:
    - `add_user(name, member=True, ha_user_id=None)` writes a user directly and commits. Members get a `member_since` one minute apart, so the call order is the display order.
    - `people` gives the members Ana, Bor and Cene (`people.ana`, `.bor`, `.cene`, `.order`); `two_people` gives only Ana and Bor.
    - `client_for(host=..., mode=...)` builds another client (extra keyword arguments go to `Settings`); it does not follow redirects. Use `host="172.30.32.2"` and `mode=Mode.ADDON` for an Ingress user, then set the `X-Remote-User-Id` and `X-Remote-User-Display-Name` headers.
- `tests/test_smoke.py` checks that the app starts, serves the start page and the health endpoint.
- `tests/test_auth.py` covers the Ingress-only rule, base path handling, the standalone login and the Bearer token.
- `tests/test_web_pages.py` renders every screen at the root and under an Ingress prefix (all URLs prefixed, none external), checks the dialog layout and parses `web/` to make sure it never calls `session.add`, `delete` or `commit` (writes go through services).
- `tests/test_e2e.py` drives the app over HTTP: add items, check, done shopping, balances, settle up, delete and undo.
- API responses are pinned by tests, because field names are stable within v1.

Add tests next to the feature they cover, and drive web forms through the test client without monkeypatching.

## Fixtures

Files in `tests/fixtures/` (none yet) must be hand-made or fully anonymised. Never commit a real export that contains personal data.
