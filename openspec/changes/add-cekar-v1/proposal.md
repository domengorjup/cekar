## Why

The user's household keeps its shopping list in a shared Google Keep note and splits costs in Splitwise. Both are cloud services the household wants to leave (de-googling), and neither knows about the other: after shopping, the receipt is typed into Splitwise by hand. cekar v1 is a small, self-hosted replacement that runs on the home server as a Home Assistant add-on. It covers what the household actually uses, for one household, and links the two halves: a finished shopping trip becomes an expense.

## What Changes

- New web application (Python, SQLite), shipped as a Docker image. It runs behind Home Assistant Ingress (under a path prefix) or standalone (at root, optional password), like its sibling glovebox.
- New Home Assistant add-on and add-on repository layout. Sidebar panel visible to all HA users (`panel_admin: false`); data in `/data`, included in HA backups.
- **Identity from Home Assistant:** no app login in add-on mode. The acting person comes from the Ingress user headers (to be verified on the test instance); users are registered automatically on first visit. Fallback, and standalone identity: a "Who are you?" picker stored in a cookie.
- **Household members:** Settings lets the household tick which users take part in shared expenses (kids, guests and tablet accounts stay out). Everyone can use the lists.
- **Shopping lists:** several lists; items with name, optional free-text quantity, who added it (automatic) and optionally for whom. Suggestions from history while typing. Checked items move to a collapsed section at the bottom; "Clear checked" removes them. Changes from other household members appear within seconds (polling).
- **Expenses:** EUR in integer cents. Split equally or by exact amounts, plus two one-tap options on the add form: "For <other person>" (they owe the full amount) and "Personal" (nobody owes, still recorded). "Paid by" is always a dropdown, defaulting to the current user. One payer per expense.
- **Balances and settle up:** balances per pair of members; "Settle up" records a full or partial payment.
- **Done shopping:** turns a list's checked items and the receipt total into expenses. Items marked "for <person>" can be priced and are charged to that person (or recorded as personal for the payer); the rest is split equally. The checked items are then cleared.
- **English and Slovenian,** switchable per user, with the default taken from the browser language.
- Optional API listener (port 8100, Bearer token, off by default), kept from the shared skeleton; in v1 it serves only a health check, ready for the later dashboard card and offline app.
- **Ready for a later offline app:** UUID keys, `updated_at` and `deleted_at` on every row, a global change sequence, and all writes through a service layer.

## Non-goals

- **Later (v1.1, separate changes):** expense categories with stats and filters (each list with a default category), recurring expenses, receipt photo and note, CSV import/export including Splitwise history import, price memory per item (estimated list total), notifications via HA notify, a Lovelace dashboard card.
- **Not planned for v1:** multiple payers per expense, debt simplification across more than two members, the offline app (stage 2, see `docs/dev/offline.md`).
- **Never:** voice input, Google Keep import, multiple currencies, multiple households.

## Capabilities

### New Capabilities
- `ha-addon`: add-on packaging, repository layout, Ingress panel for all users, persistent data, standalone image.
- `web-access`: serving under the Ingress prefix or at root, add-on source check, standalone password login, identity of the acting person (Ingress headers or picker).
- `household-members`: automatic user registration, member flag, Settings page.
- `shopping-lists`: lists, items, check/clear, suggestions, near-live updates.
- `expenses`: expense records, the four split methods, rounding.
- `balances-settlement`: pair balances and payments.
- `shopping-trip`: "Done shopping", from checked items to expenses.
- `i18n`: English and Slovenian, per-user language, locale formatting.
- `sync-readiness`: UUID keys, timestamps, tombstones, change sequence, service-layer writes.

### Modified Capabilities
<!-- None: this is the first change in the project. -->

## Impact

- New codebase: Python package `cekar` (FastAPI app, SQLAlchemy models, Alembic migrations, services, Jinja2 templates, vendored static assets, TOML message catalogs), plus `Dockerfile`, `addon/cekar/` and `repository.yaml`.
- Dependencies (via `uv add`): fastapi, uvicorn, sqlalchemy, alembic, jinja2, python-multipart, itsdangerous. Dev: pytest, httpx. No i18n library (catalogs are read with the standard library `tomllib`).
- Vendored front-end assets only (no CDN): own CSS and JavaScript, used Material Design Icons as an SVG sprite.
- No external services; data stays in `/data/cekar.db`.
