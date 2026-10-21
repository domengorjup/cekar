# Architecture

Cekar is one Python app (FastAPI) that serves server-rendered HTML pages from one process, on top of a SQLite database. The decisions behind it are in `openspec/changes/add-cekar-v1/design.md`.

## Layers

| Layer | Role |
|---|---|
| `web/` | HTML routes, Jinja2 templates, vendored static files. Forms work through normal POST requests; JavaScript only enhances them (suggestions while typing, dialogs, polling for changes). Routes never write to the database themselves. |
| `identity.py`, `auth.py` | Who is asking: the Ingress source check, the HA user headers, the "Who are you?" cookie, the standalone password. |
| `services/` | Every create, update and delete, with validation: `members`, `lists`, `suggestions`, `expenses`, `balances`, `trips`. `sync.py` stamps every write with timestamps and a change number. |
| `i18n.py`, `i18n/*.toml`, `web/formatting.py` | English and Slovenian texts, plural rules, amount and date formatting. |
| `db.py`, `models.py`, `migrations/` | SQLAlchemy models, Alembic migrations run at startup. |
| `api/v1.py` | Optional token-protected API; only a health check in v1. |

## Request flow (add-on mode)

```text
phone / browser -> HA frontend (login) -> Supervisor Ingress proxy (172.30.32.2)
   adds X-Ingress-Path and X-Remote-User-Id / -Name / -Display-Name
-> cekar :8099
   auth: source address must be the proxy, else 403
   identity: user from the headers (registered on first visit), else the picker cookie
   i18n: the user's language, else Accept-Language, else English
-> web route -> services -> SQLite
```

All templates build URLs through `urls.url(request, path)` so the Ingress prefix is always applied. The identity headers can be trusted only because nothing but the proxy can reach port 8099.

## Modes

- **Add-on** (`CEKAR_MODE=addon`): port 8099, Ingress only, no login. Optional second listener on 8100 for `/api/v1` with a Bearer token, started only when a token of 16+ characters is set.
- **Standalone** (default): port 8080 at root, optional password login, identity by the "Who are you?" picker.

## Data model

| Table | Holds |
|---|---|
| `user` | Everyone who used the app: HA user id (if any), names, `is_member`, `member_since`, `language`. |
| `user_preference` | Per-user values such as the last opened list. |
| `shopping_list` | Name and position. |
| `item` | Name, normalised name for suggestions, free-text quantity, for whom, added by, position, checked and cleared times. Suggestions are computed from these rows (cleared items count, deleted ones do not); there is no separate history table. |
| `expense` | Title, amount in cents, date, payer, split method (`equal`, `exact`, `for_other`, `personal`), optional trip. |
| `expense_share` | Who carries how many cents of an expense. Always sums to the expense amount. |
| `payment` | Settle-up payments between two members. |
| `shopping_trip` | One "Done shopping": list, payer, receipt total, date; its expenses point to it. |
| `change_counter` | The single global change number. |
| `setting` | App-wide values (e.g. the generated signing secret). |

Balances are not stored: they are sums over shares and payments, computed per pair of users.

## Sync-readiness fields

Every user-data table has a UUID text primary key and `created_at`, `updated_at`, `deleted_at`, `seq`. Deletes only set `deleted_at`; queries skip such rows. Every write takes the next value of the change counter into `seq`, so "what changed since N" is `seq > N`. In v1 this already drives the near-live list updates: a list's version is the largest `seq` among the list and its items, and open pages poll it every few seconds. The later offline app is described in `offline.md`.

## Money

EUR only, integer cents. Equal splits give everyone the rounded-down share; leftover cents go to the payer first, then to the other members in the order they became members.

## Database

SQLite at `$DATA_DIR/cekar.db`, WAL mode. Alembic runs `upgrade head` at startup, so upgrades need no manual step.
