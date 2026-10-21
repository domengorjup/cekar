## Context

The user's household (two adults, possibly kids, guests and a wall tablet as extra Home Assistant users) shares one shopping list in Google Keep and splits costs in Splitwise. The goal is to leave both Google and Splitwise and run the same thing on the home server, inside Home Assistant.

cekar is a sibling of glovebox (`/mnt/data/workspace/autotracker_app`). It reuses glovebox's stack, add-on packaging, Ingress handling, design language and release procedure. Where glovebox already made a decision (D1 stack, D9 web access, D11 packaging in glovebox's `add-autotracker-v1`), cekar follows it and this document only records the differences.

Constraints:
- Python backend; dependencies managed with `uv`.
- Runs behind HA Ingress (per-install path prefix; HA has already authenticated the user) or standalone.
- One household, low data volume (thousands of rows per year).
- Money is EUR only.
- A later stage 2 adds an installable offline app (see `docs/dev/offline.md`). v1 does not build it, but its data model must not block it.

## Goals / Non-Goals

**Goals:**
- Replace the shared Keep list: several lists, fast adding with suggestions from history, Keep-style checked section, near-live updates between phones.
- Replace Splitwise for one household: equal and exact splits, one-tap "for the other person" and "personal", balances per pair, settle up.
- Close the loop between the two: "Done shopping" turns the checked items and the receipt total into expenses.
- English and Slovenian from day one.
- A data model that a later offline client can sync against.

**Non-Goals (v1.0):**
- Expense categories, stats and filters; recurring expenses; receipt photos and notes; CSV import/export (including Splitwise history import); price memory per item; HA notifications; a Lovelace card. These are v1.1 follow-ups (see "Follow-ups"); the data model leaves room for each.
- Multiple payers on one expense.
- Debt simplification across more than two members (balances are shown per pair).
- The offline app itself (stage 2).

**Never:**
- Voice input, Google Keep import, multiple currencies, multiple households.

## Decisions

### D1. Stack: same as glovebox
FastAPI, SQLAlchemy 2, Alembic (run at startup), Jinja2 server-rendered pages, vanilla JavaScript only as enhancement, vendored assets (no CDN), SQLite in WAL mode under `DATA_DIR`. Same reasons as glovebox D1. The CSS tokens and standard elements come from glovebox's `docs/dev/design.md`; cekar keeps its own copy in `docs/dev/design.md` and adds its own elements there.

### D2. Identity from Home Assistant Ingress headers (to verify, Q1)
- **Add-on mode:** the Supervisor's Ingress proxy is believed to add `X-Remote-User-Id`, `X-Remote-User-Name` and `X-Remote-User-Display-Name` to every proxied request. cekar reads them on every request and treats `X-Remote-User-Id` as the stable identity. This is not yet confirmed for the user's HA version; task 0.1 checks it on `haos-test` before anything depends on it.
- **Why the headers can be trusted:** the Ingress listener only accepts connections from the Supervisor proxy address (`172.30.32.2`, as in glovebox D9). Nothing else can reach the port, so nothing else can forge the headers.
- **Auto-registration:** the first request from an unknown `X-Remote-User-Id` creates a `user` row with the name and display name from the headers. Later requests update the display name if it changed in HA. New users are **not** expense members until someone ticks them in Settings (D3).
- **Fallback if the headers are absent** (older Supervisor, or a client that strips them): a "Who are you?" picker listing the known people (and a field to add one). The choice is stored in a signed cookie (`itsdangerous`, same secret as the session) for one year. A "Switch person" entry in the user menu clears it. The same picker is the identity mechanism in standalone mode.
- **Recommendation:** use the headers when present and the picker only as fallback. The headers give real per-person identity with zero setup and no way to pick the wrong person on a shared tablet. The picker is weaker (anyone can choose anyone) but acceptable inside one trusting household, and it keeps the app usable if the headers turn out to be missing.
- **Header present but user unknown and the picker cookie set:** headers win; the cookie is ignored.
- **Alternatives considered:**
  - Asking the HA Core API for the current user: the add-on does not see the user's HA token, so this cannot work from inside the add-on.
  - App-level accounts and passwords: duplicate login for something HA already did; rejected.

### D3. Users, members, and who may do what
- **`user`** is everyone who has used the app (or was added by hand in the picker / standalone Settings). **Member** is a flag on a user: only members can pay, owe, or appear in "for whom".
- Settings shows all users with a "Member of shared expenses" switch. Kids, guests and tablet accounts stay non-members but can still use every list.
- **Everyone may change Settings**, including membership. One trusting household; `panel_admin: false` so non-admin HA users see the panel. Rejected: admin-only Settings, because HA's admin flag is not reliably passed through Ingress and the household does not need it.
- **Removing a member** keeps all their past shares and payments. Balances that involve a former member stay visible until settled (D16). A non-member can be ticked again at any time.
- The expense form needs at least two members; with fewer it shows a short hint pointing to Settings.

### D4. Standalone mode
Same as glovebox D9: listens on 8080 at root, optional `CEKAR_PASSWORD` login with a signed session cookie, startup warning when no password is set; `/api/v1` is locked behind `CEKAR_API_TOKEN` or the login when either is set. Identity is the D2 picker of configured people. People are added in Settings (name only) and start as members.

### D5. Money and rounding
- **Currency:** EUR only, stored as integer cents. No currency setting.
- **Input:** amounts accept `12,50`, `12.50`, `12,5` and `12`; at most two decimals; no thousands separators. Zero and negative amounts are rejected.
- **Equal split rounding (deterministic):** for an amount `A` (cents) and `n` participants, everyone's base share is `A // n`; the remainder `r = A % n` cents go one each to the first `r` participants in this order: **the payer first (if the payer participates), then the other participants by the member display order** (order of becoming a member, stored as `member_since`, ties by user id). So in a two-person split the payer absorbs the odd cent and the other person never owes more than half. Shares always sum exactly to `A`.
- **Exact amounts:** the entered shares must sum exactly to the total; the form shows the difference live and refuses to save until it is zero. Shares of zero are allowed and not stored.
- **Display:** locale-formatted (D10): `12,50 €` in Slovenian, `€12.50` in English.

### D6. Split methods
Every expense has one payer (always a dropdown on the add and edit form, default the current user if a member, else the first member) and one `split` value:

| `split` | Shares stored | Meaning |
|---|---|---|
| `equal` | one per chosen participant (default: all members), D5 rounding | shared cost |
| `exact` | one per participant with a non-zero amount | uneven shared cost |
| `for_other` | one share, the full amount, for the other person | payer paid entirely for someone else; they owe all of it |
| `personal` | one share, the full amount, for the payer | payer's own expense; nobody owes anything, but it is recorded |

- **One-tap options:** the add form shows four choices as a segmented control right under the amount: **Split equally** (default), **For <name>**, **Personal**, **Exact amounts**. With exactly two members, "For <name>" names the member who is not the payer and changes when the payer changes. With more than two members it reads "For someone…" and opens a member choice (excluding the payer). Exact amounts expands the per-member amount fields; "Split equally" can be narrowed to a subset of members by toggling member chips.
- **Shares are materialised** (stored as rows) at save time, so balances are plain sums and later changes to the member list never rewrite old expenses.
- **Rejected:** percentages and shares-by-weight (Splitwise has them; the household does not use them).

### D7. Balances and settle up
- **Per pair:** for each expense with payer `P` and each share `(M, a)` with `M ≠ P`, `M` owes `P` the amount `a`. A payment from `X` to `Y` of `x` reduces what `X` owes `Y` by `x`. The net for each unordered pair is reported once, as "A owes B €x", with zero pairs hidden.
- **Summary per member:** the sum of their pair nets ("you are owed €x in total"). With two members this equals the single pair.
- **Settle up:** records a `payment` (from, to, amount, date). The form is prefilled with the full net amount of the chosen pair but any positive amount is accepted (partial payment). Paying more than owed is allowed with a warning; the direction of the pair then flips.
- **Personal expenses** produce no debt; `for_other` and shares of `equal`/`exact` do.
- **Simplify debts:** not in v1. With more than two members the pair list is shown as is. It is cheap to add later on top of the pair nets if ever wanted.

### D8. Shopping lists, items and suggestions
- **Lists:** any number, each with a name and a position. Everyone can create, rename, reorder and delete lists. The app remembers each user's last opened list (per user, server-side) and opens it on start.
- **Items:** `name` (required, trimmed, up to 100 characters), `quantity` (optional **free text**, up to 30 characters, e.g. `2`, `500 g`, `2 kg`, `a big one`), `for_whom` (optional member; blank means shared), `added_by` (set automatically), `checked_at`/`checked_by`, `cleared_at`.
  - **Free-text quantity** was chosen over number + unit: Keep users write quantities freely, a unit list would need translating and maintaining, and v1 does no maths on quantities. Price memory (v1.1) works per item name and does not need structured quantities.
- **Ordering:** unchecked items by position (newest at the bottom, drag to reorder on desktop and with a handle on phones); checked items in a collapsed "N checked items" section at the bottom, most recently checked first.
- **Check / uncheck** is one tap. **Clear checked** sets `cleared_at` on all checked items of the list, which hides them. **Delete** (from the item's edit dialog) sets `deleted_at`.
- **Suggestions** are derived from item rows, not kept in a separate table: all items of all lists that are not `deleted_at` (so cleared items count, deleted mistakes do not), grouped by case- and accent-insensitive name.
  - **Ranking:** names that start with the typed text before names that contain it; within each group by score `uses × 0.5^(days_since_last_use / 30)` (a 30-day half-life, so a weekly item beats something bought ten times two years ago); ties by name. At most 8 suggestions. Names already unchecked on the current list are left out.
  - **Display name:** the most recently used spelling.
  - **Tapping a suggestion** adds it. If the same name is already unchecked on the list, nothing is added and the existing item is highlighted; if it is checked (not yet cleared), it is unchecked instead of duplicated.
  - **Why derived:** one fewer table to keep in step, and household volume (a few thousand rows per year) makes the query cheap. An index on `(deleted_at, name_key)` keeps it fast; if it ever is not, a summary table can be added without changing behaviour.
  - **Server-side:** suggestions are fetched from `GET /lists/{id}/suggest?q=` as an HTML fragment while typing (debounced 150 ms); without JavaScript the add form still works.

### D9. Near-live updates: polling a change cursor
- **Choice:** while a list page is visible, the browser polls `GET /lists/{id}/version` every 4 seconds (and immediately when the tab becomes visible again). The response is the list's current change sequence (D12). If it differs from the one the page was rendered with, the page fetches the item fragment and swaps it in. Polling stops while the page is hidden (Page Visibility API).
- **Why polling over SSE or WebSockets:** it works through any proxy (HA Ingress, reverse proxies) without long-lived connections, needs no extra server machinery or library, survives the companion app suspending the page, and costs one tiny indexed query per poll. With a handful of users the load is negligible. A 4-second delay is fine for a shopping list. SSE through Ingress is probably possible but adds connection-lifetime and reconnection questions for no visible gain.
- The same mechanism refreshes the balances summary on the expenses page (one version for all expenses and payments).

### D10. Internationalisation: dict catalogs in TOML, no Babel
- **Languages:** English (`en`) and Slovenian (`sl`). English is the fallback.
- **Catalogs:** `src/cekar/i18n/en.toml` and `sl.toml`, flat dotted keys (`list.add_item`, `expense.split.equal`) with `{name}`-style placeholders. Loaded once at startup with `tomllib` (standard library).
- **API:** `t(key, **params)` and `tn(key, n, **params)` for plurals, exposed to Jinja2 as globals bound to the request's language. Plural keys hold one form per category: English `one`/`other`; Slovenian `one`/`two`/`few`/`other` (rule: `n % 100 == 1` one, `== 2` two, `3–4` few, else other).
- **Formatting:** `money(cents, lang)` and `date(d, lang)` in `web/formatting.py` (the skeleton's module, made language-aware) (decimal comma and `12,50 €` in Slovenian; `€12.50` in English; dates `21. 10. 2026` and `21 Oct 2026`, with month names from the catalog).
- **Language choice per user:** stored on the `user` row (`language`, nullable). When it is not set: best match of the request's `Accept-Language` header among `sl` and `en`, else `en`. A switch in the user menu sets it. HA's own profile language is probably not passed to add-ons (Q2); the browser or companion-app language is the best available default.
- **Service errors** are raised as message keys with parameters, never as English strings, so the web layer translates them.
- **Tests:** both catalogs have the same keys, the same placeholders per key and every plural category; every `t("...")` key used in templates and code exists.
- **Why not gettext/Babel:** gettext needs an extract and compile step (`.po` → `.mo`) and Babel as a dependency, which buys little for two languages and a few hundred strings. TOML catalogs need no tooling, are easy to diff and review, and tests catch the mistakes extraction would. **Rejected:** JSON (no comments), Python dicts (harder for a translator to edit).

### D11. Shopping trip: "Done shopping" turns a list into expenses
- **Entry:** a "Done shopping" button on a list with at least one checked item. It opens a form with: receipt total (required), date (today), paid by (dropdown, default current user), and one price field for each checked item that has a `for_whom`. Items without `for_whom` are listed, without price fields, as "shared".
- **Validation:** the sum of the entered item prices must not exceed the total. Blank price fields are allowed; that item is then treated as shared.
- **Result,** in one transaction, linked to one `shopping_trip` row (list, payer, total, date):
  - for each member `M ≠ payer` with priced items: one `for_other` expense for `M` with the sum of `M`'s item prices, titled "<list name>: <item names>";
  - if the payer has priced items for themselves: one `personal` expense with their sum;
  - the remainder `total − Σ prices`, if above zero: one `equal` expense among all members, titled with the list name;
  - then all checked items of the list are cleared (`cleared_at`), so they feed suggestions as usual.
- **Why several expenses instead of one mixed one:** each resulting expense has one ordinary split method, so balances, editing and later categories and stats treat trip expenses exactly like hand-entered ones. The trip row groups them in the expense list ("Shopping, 21 Oct: 3 expenses") and lets the user open them together.
- **Payer is not a member** (e.g. the tablet account pressed the button): the paid-by dropdown lists members only, so this cannot happen; the default falls back to the first member.
- **Fewer than two members:** the button still clears the checked items but skips the expense part, with a hint.
- **Undo:** none in v1 beyond deleting the created expenses individually; cleared items are not restored.

### D12. Sync readiness (stage 2 offline app)
These rules apply to every table that holds user data (`user`, `shopping_list`, `item`, `expense`, `expense_share`, `payment`, `shopping_trip`, `user_preference`).
- **Primary keys are UUIDs** (`uuid4`, stored as 36-character text). Generated by the server in v1; a later client may generate them, so creating the same row twice is idempotent.
- **`created_at`, `updated_at`** (UTC) on every row; `updated_at` changes on every write.
- **Soft deletes:** `deleted_at` instead of `DELETE`. Every query excludes tombstones by default. Child rows (items of a deleted list, shares of a deleted expense) get their own tombstones in the same transaction, with the same `deleted_at` value as the parent so that undo (D17) can tell them apart from children deleted earlier.
- **Change sequence:** one global integer counter (single-row `change_counter` table). Every write in the service layer takes the next value and stores it in the row's `seq` column (indexed). "Everything changed since cursor N" is then `WHERE seq > N` per table. v1 already uses it for D9 (a list's version is `max(seq)` over the list and its items).
- **All mutations go through `services/`**. Web routes never write to the session directly. The service functions take plain values and an acting user id, so a later sync endpoint can call the same functions.
- **No hard deletes** in v1, apart from the `change_counter` row itself never being deleted. A future purge of old tombstones is a stage-2 decision.
- **Rejected:** integer primary keys plus a separate public UUID (two ids per row, easy to mix up); per-table counters (one global cursor is simpler for clients).

### D13. Data model
- **`user`**: id, ha_user_id (unique, nullable for standalone/picker people), username, display_name, is_member, member_since (nullable), language (nullable), last_seen_at, sync fields.
- **`user_preference`**: id, user_id, key, value (e.g. `last_list_id`), sync fields. Unique `(user_id, key)`.
- **`shopping_list`**: id, name, position, sync fields.
- **`item`**: id, list_id, name, name_key (normalised for suggestions), quantity, for_whom_id (nullable), added_by_id, position, checked_at, checked_by_id, cleared_at, sync fields.
- **`expense`**: id, title, amount_cents, spent_on (date), payer_id, split (`equal`|`exact`|`for_other`|`personal`), trip_id (nullable), created_by_id, sync fields. v1.1 adds nullable `category_id` and `note`.
- **`expense_share`**: id, expense_id, user_id, amount_cents, sync fields. Unique `(expense_id, user_id)` among live rows; sum equals the expense amount (checked in the service layer).
- **`payment`**: id, from_user_id, to_user_id, amount_cents, paid_on, created_by_id, sync fields.
- **`shopping_trip`**: id, list_id, payer_id, total_cents, spent_on, created_by_id, sync fields.
- **`change_counter`**: single row, `value`.
- **`setting`**: key, value (app-wide: the cookie-signing secret if generated, schema notes). Not synced.
- Sync fields = `created_at`, `updated_at`, `deleted_at`, `seq`.

### D14. HA add-on packaging
Same as glovebox D11, with: name "Cekar", slug `cekar`, `panel_icon: mdi:basket`, `panel_title: Cekar`, `panel_admin: false`, `ingress_port: 8099`, archs `amd64` and `aarch64`, `init: true`, `backup: hot`, no `homeassistant_api` (v1.1 notifications will need it). The database is `/data/cekar.db`. The add-on Dockerfile clones the repository at `SOURCE_REF=v<version>`, as glovebox does, until a GHCR build exists.
- **Optional API listener, kept from the skeleton:** as glovebox D9a, a second listener on container port `8100/tcp` (host port `null`, so off by default), serving only `/api/v1/*` with `Authorization: Bearer <api_token>` (16+ characters in add-on mode), 404 for everything else. In v1 it serves only `GET /api/v1/health`. It costs nothing while off, and the v1.1 Lovelace card and the stage-2 offline app (see `docs/dev/offline.md`) both need a port outside Ingress, so the plumbing is kept rather than removed and re-added. No feature endpoints are added in this change. The `api_token` option is the only add-on option.

### D15. Code layout and parallel-work interfaces

```
src/cekar/
  app.py, config.py, db.py, models.py, urls.py
  identity.py          # D2: resolve the acting user from headers / picker cookie
  auth.py              # add-on source check, standalone password login
  i18n.py, i18n/{en,sl}.toml   # D10 catalogs, t/tn, resolve_language
  api/v1.py            # D14: /api/v1/health only in v1
  services/
    sync.py            # next_seq(), soft_delete(), restore(), base mixin for sync fields (D12)
    members.py         # users, membership, preferences (D3)
    lists.py           # lists, items, check/clear, version (D8, D9)
    suggestions.py     # D8 ranking
    expenses.py        # expenses and shares (D6), split_equal (D5)
    balances.py        # pair nets, payments (D7)
    trips.py           # D11
  migrations/          # Alembic
  web/                 # lists.py, expenses.py, balances.py, trips.py, settings.py, identity.py,
                       # common.py, templating.py, formatting.py (parse and locale-format
                       # amounts and dates, D5/D10), templates/, static/
addon/cekar/         # HA add-on folder; repository.yaml at repo root
```

- **Frozen interfaces:** `models.py`, `services/sync.py`, the `i18n.py` and `web/formatting.py` signatures (`t`, `tn`, `resolve_language`, `money`, `date`, `parse_amount`) and the function signatures in every `services/*.py` are written in task group 1 and then frozen.

### D16. Un-ticking a member with an open balance is allowed (Q3 resolved)
Turning off "Member of shared expenses" is never blocked. If the person's balance with anyone is not zero, Settings shows a warning with the amount before the switch is saved. After that their balance stays visible on the balances page and settle up keeps working until it is zero. Rejected: blocking the switch, because a guest who leaves with a debt would then have to stay a member.

### D17. Who may delete, and undo (Q4 resolved)
- **Everyone may delete** lists, items, expenses and payments (one trusting household, as in D3).
- **Every delete offers Undo.** Deletes are soft (D12), so undo clears `deleted_at`. `soft_delete` stamps the row and the children it cascades to with the same `deleted_at` value. `restore` clears `deleted_at` on the row and only on children whose `deleted_at` equals the parent's, so children deleted earlier (an item deleted before its list) stay deleted. Restore also sets `updated_at` and takes a new `seq`, so a polling client or a later sync sees it as a normal change.
- **UX:** after a delete, a snackbar "Deleted <thing> · Undo" is shown for about 10 seconds. Without JavaScript the redirect target page shows the same message with an Undo `post_button`. The snackbar is a new repeated element and goes into `docs/dev/design.md`.
- **Confirmation:** no confirm dialog for items, expenses and payments, since undo exists. Deleting a whole list keeps its confirm dialog and also offers Undo.
- **Limit:** undo is offered right after the delete only; v1 has no trash view. A deleted row stays restorable in the database until a future purge (D12).

## Follow-ups (v1.1, not in this change)
Listed so the v1 model does not block them:
- **Categories, stats and filters:** `category` table, nullable `expense.category_id`, a default category per list that trip expenses inherit. Personal expenses already count.
- **Recurring expenses:** a template row plus a generator; expenses keep their shape.
- **Receipt photo and note:** nullable `expense.note`, files under `/data/receipts/<expense id>`.
- **CSV import/export incl. Splitwise history:** expenses and shares are already explicit rows; Splitwise's per-person columns map onto `exact` shares.
- **Price memory per item:** item prices from trips (D11) are the data source; store them on the item (`price_cents`, nullable) when a trip prices it.
- **Notifications via HA notify** (list changed, expense added, you owe): needs `homeassistant_api: true`; the `seq` cursor tells what changed since the last notification.
- **Lovelace card:** probably via a companion integration exposing a to-do entity per list; to be decided.

## Risks / Trade-offs
- **Ingress identity headers may be missing** on the user's Supervisor version → task 0.1 checks first; the picker fallback (D2) keeps the app usable either way.
- **Polling costs requests** → one indexed query per 4 s per open page, paused when hidden; negligible for one household.
- **Free-text quantity** cannot be summed or converted → nothing in v1 or v1.1 needs that.
- **Derived suggestions** scan item rows → indexed and small; a summary table is a drop-in later.
- **Soft deletes everywhere** need discipline in every query → the service layer adds the `deleted_at IS NULL` filter in one helper, and tests cover that deleted rows never appear.
- **Everyone can change membership** → acceptable for one trusting household; changes are recorded with `updated_at`.

## Migration Plan
Greenfield. Alembic `upgrade head` at startup. Rollback via HA add-on backups of `/data`.

## Open Questions
- **Q1. Ingress identity headers.** Does the Supervisor on `haos-test` (current HAOS) pass `X-Remote-User-Id`, `X-Remote-User-Name` and `X-Remote-User-Display-Name` to the add-on, from the browser and from the companion app? Task 0.1 verifies it. If they are absent, the D2 picker becomes the main identity mechanism and Settings gains "add person".
- **Q2. Default language.** Is HA's profile language visible to the add-on in any way (header, cookie)? Assumed not; the default comes from `Accept-Language`. Task 0.2 records what the browser and companion app actually send.
- **Q3 — resolved: allow, with a warning.** Un-ticking a member with a non-zero balance is allowed; the warning shows the amount and the balance stays visible until settled. See D16.
- **Q4 — resolved: everyone may delete, with undo.** Confirm only when deleting a whole list. See D17.
