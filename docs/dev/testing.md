# Testing

Run everything with `uv run pytest`.

- `tests/conftest.py` provides a migrated in-memory `engine`, a `session`, a `settings` and a `client` fixture.
- `tests/test_smoke.py` checks that the app starts, serves the start page and the health endpoint.
- `tests/test_auth.py` covers the Ingress-only rule, base path handling, the standalone login and the Bearer token.
- API responses are pinned by tests, because field names are stable within v1.

Add tests next to the feature they cover, and drive web forms through the test client without monkeypatching.

## Fixtures

Files in `tests/fixtures/` (none yet) must be hand-made or fully anonymised. Never commit a real export that contains personal data.
