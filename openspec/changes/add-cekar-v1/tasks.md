## How to run this change in parallel

- **Group 0** (verify assumptions on `haos-test`) runs first and is quick. Its answers decide whether the identity picker (design D2) is the fallback or the main path. Groups 1 and 2 may start before it finishes; group 3 may not.
- **Group 1** (foundation) runs next, by one agent. It freezes `models.py`, `services/sync.py`, the `i18n.py` and `web/formatting.py` signatures and every function signature in `services/*.py`. The code skeleton (app factory, `auth.py`, `urls.py`, the API listener, static assets, add-on folder) already exists; group 1 extends it rather than rewriting it.
- **Group 2** (UI mockup) runs in parallel with group 1. The user has approved `.mockups/ui-v1/` (see its `NOTES.md`); it is the reference for the UI tasks, and group 8 follows it. Further mockup changes are recorded in its `NOTES.md`.
- **Groups 3–7 and 9** then run in parallel. Each owns the files listed in its heading and touches no others:
  - 3: identity, access and members;
  - 4: shopping lists and suggestions;
  - 5: expenses, balances and payments;
  - 6: shopping trip;
  - 7: i18n machinery (English only) and formatting;
  - 9: add-on packaging.
  Group 6 codes against the frozen signatures of groups 4 and 5; its tests only pass once those have landed.
- **Group 8** (web UI) needs groups 1 and 2; it can start against the service stubs, and its tests pass once groups 3–7 have landed.
- **Group 10** (user docs) can start after group 2 and finishes after group 8 (screenshots).
- **Group 11** integrates, releases and verifies.
- **Catalog rule:** v1.0 ships English only. Group 1 creates `i18n/en.toml` with the error-message keys the services raise. After that, group 8 owns `i18n/en.toml` and adds every UI key; group 7 owns only `i18n.py` and its tests. The key-usage test (7.4) keeps code and catalog in step. There is no `sl.toml` in v1.0.
- **Shared rules:** no real personal data in git; fixtures use invented names (Ana, Bor, Cene). Code, templates, user docs and the README name no other projects. Every group ends with the full test suite green.

## 0. Verify assumptions on the test HA instance (before group 3; owns nothing in the repo except notes in `design.md` Q1/Q2)

- [ ] 0.1 On `haos-test`, install a throwaway add-on (or a debug build of cekar's skeleton) that logs the request headers it receives through Ingress: `X-Remote-User-Id`, `X-Remote-User-Name`, `X-Remote-User-Display-Name`, `Accept-Language` and `X-Forwarded-For`. Open the panel as an admin user and as a non-admin user, from a desktop browser and from the HA companion app. Record whether the three identity headers are present and stable. Also send a forged lower-case `x-remote-user-id` from a logged-in session and record whether it reaches the app. Record the Supervisor version. Update design D2 and Q1 with the result.
- [ ] 0.2 From the same log, record the `Accept-Language` header sent by the browser and by the companion app. Confirm that no header or cookie carries HA's profile language. Note the result in design D10 and Q2 for the later Slovenian work (not used in v1.0).
- [ ] 0.3 Check that a 4-second polling `fetch` through Ingress works from the companion app (no auth prompts, no session expiry within an hour of idle). Note the result in design D9.

## 1. Foundation (sequential; owns `pyproject.toml`, `config.py`, `db.py`, `models.py`, `migrations/`, `services/sync.py`, `web/formatting.py`, `i18n.py` (stub), `i18n/en.toml` (initial), `services/*.py` (stubs), `app.py`, `urls.py`, `web/common.py`, `web/templating.py`, `templates/base.html`, `tests/conftest.py`)

- [ ] 1.1 Check `pyproject.toml` (from the skeleton): `src/cekar` package; dependencies fastapi, uvicorn, sqlalchemy, alembic, jinja2, python-multipart, itsdangerous; dev dependencies pytest, httpx. Add anything missing with `uv add`.
- [ ] 1.2 Check `config.py` (from the skeleton: `CEKAR_MODE`, `BASE_PATH`, `DATA_DIR`, `CEKAR_PORT`, `CEKAR_PASSWORD`, `CEKAR_API_TOKEN`, `CEKAR_API_PORT`, `CEKAR_SECRET`). Make sure a missing secret is generated once and stored under `DATA_DIR`, so identity cookies survive restarts.
- [ ] 1.3 Implement `db.py`: SQLite under `DATA_DIR/cekar.db`, WAL mode, session factory.
- [ ] 1.4 Implement `models.py` per design D13 with the sync fields of D12 (UUID text keys, `created_at`, `updated_at`, `deleted_at`, indexed `seq`) as a shared mixin; `change_counter` and `setting` tables; indexes on `item (list_id, deleted_at, cleared_at)`, `item (deleted_at, name_key)`, `expense_share (user_id)`.
- [ ] 1.5 Replace the skeleton's empty `0001_initial` migration with the D13 schema (nothing is released yet, so no second migration is needed). `upgrade head` runs at startup.
- [ ] 1.6 Implement `services/sync.py`: `next_seq(session)`, `touch(row, session)` (sets `updated_at` and `seq`), `soft_delete(row, session)` (stamps the row and its cascaded children with one shared `deleted_at`), `restore(row, session)` (clears `deleted_at` on the row and on children with the same `deleted_at`; sets `updated_at` and a new `seq`), `live(query)` (adds `deleted_at IS NULL`), `new_id()`.
- [ ] 1.6a Add `restore` tests to the `sync.py` unit tests: same-`deleted_at` children come back, earlier-deleted children do not, `updated_at` and `seq` advance.
- [ ] 1.7 Add `parse_amount(text) -> int` to `web/formatting.py` (design D5 input rules, raising a keyed validation error) and implement `split_equal(amount, participants, payer, order) -> dict[user_id, int]` in `services/expenses.py` (D5 rounding; the rest of that module stays a stub).
- [ ] 1.8 Write the stub `i18n.py` (`t`, `tn`, `money`, `date`) and initial `i18n/en.toml` with the validation-error keys.
- [ ] 1.9 Write the stub signatures with docstrings for `services/members.py`, `lists.py`, `suggestions.py`, `expenses.py`, `balances.py`, `trips.py`. Every write takes `actor_id` and plain values; errors are `ServiceError(key, **params)`.
- [ ] 1.10 Create the app skeleton: `create_app`, `main`, router mounting, `url(request, path)` honouring `X-Ingress-Path`, then `BASE_PATH`, then `/`; `base.html` using the helper and `t()`.
- [ ] 1.11 Set up the pytest scaffold: migrated in-memory engine, session, client fixtures; a fixture that creates members Ana, Bor, Cene. Unit tests for `sync.py`, `parse_amount` and `split_equal` (every rounding scenario in the expenses spec). Commit (checkpoint).

## 2. UI mockup and design language (parallel with 1; owns `.mockups/ui-v1/`, `docs/dev/design.md`)

- [ ] 2.1 Copy glovebox's design tokens and the standard elements that apply into `docs/dev/design.md` (adapted names; the skeleton already has a first copy, so check and extend it).
- [ ] 2.2 Build a clickable static mockup in `.mockups/ui-v1/` (open `index.html` directly, no server): list page with add field and suggestions, checked section, list switcher; add-expense form with the four split choices and paid-by dropdown; expense list with a collapsed trip row; balances with settle up; "Done shopping" form; Settings with member switches; "Who are you?" picker; user menu (switch person, no language switch). English only.
- [ ] 2.3 Screenshot it headless (desktop 1400x900, phone 390x844, light and dark). Record decisions in `.mockups/ui-v1/NOTES.md`.
- [ ] 2.3a Add the delete snackbar ("Deleted <thing> · Undo", about 10 s, plus the no-JS Undo `post_button` on the redirect target) to the mockup and to `docs/dev/design.md` as a new repeated element.
- [ ] 2.4 (done: the user approved `.mockups/ui-v1/`; any later change is recorded in its `NOTES.md`.) Get the user's feedback, iterate, and mark the approved version in `NOTES.md`. Add every new repeated element to `docs/dev/design.md`.

## 3. Identity, access and members (needs 0 and 1; owns `identity.py`, `auth.py`, `services/members.py`, `tests/test_identity.py`, `tests/test_members.py`)

- [ ] 3.1 Implement `auth.py`: add-on source check (Ingress proxy only, else 403; record the HA doc source in a comment), standalone password login with signed session cookie, startup warning without password.
- [ ] 3.2 Implement `identity.py` per design D2: headers first, then the signed identity cookie, else redirect to the picker; auto-registration and display-name update through `services/members.py`.
- [ ] 3.3 Implement `services/members.py`: register/update HA users, add a person by name, set membership (records `member_since`), list members in display order, user preferences (`last_list_id`), the open-balance check used by the "remove member" warning (calls `balances.pair_balances`).
- [ ] 3.4 Write tests for every scenario in the web-access and household-members specs.

## 4. Shopping lists and suggestions (needs 1; owns `services/lists.py`, `services/suggestions.py`, `tests/test_lists.py`, `tests/test_suggestions.py`)

- [ ] 4.1 Implement list CRUD, reorder, soft delete with item tombstones, `restore_list` and `restore_item` (undo, via `sync.restore`), default list on first use.
- [ ] 4.2 Implement item add/edit/delete, check/uncheck, reorder, clear checked, `name_key` normalisation (case-fold, strip accents, collapse spaces), the re-add rules (no duplicate unchecked; uncheck a checked one).
- [ ] 4.3 Implement `list_version(list_id)` (largest `seq` over the list and its items, including tombstones).
- [ ] 4.4 Implement suggestions per design D8 (ranking, 30-day half-life, limit 8, excluding unchecked names on the list); `now` is a parameter for testability.
- [ ] 4.5 Write tests for every scenario in the shopping-lists spec (service level), including undo of a list that leaves an earlier-deleted item deleted, and the sync-readiness scenarios that touch items.

## 5. Expenses, balances and payments (needs 1; owns `services/expenses.py`, `services/balances.py`, `tests/test_expenses.py`, `tests/test_balances.py`)

- [ ] 5.1 Implement expense create/edit/delete for the four split methods (design D6), materialising shares; validation keys for amount, exact-sum mismatch, payer and participants must be members, at least two members.
- [ ] 5.1a Implement `restore_expense` (expense and its shares, via `sync.restore`).
- [ ] 5.2 Implement payments create/edit/delete, with `restore_payment`, with the over-payment check returned as a warning (not an error).
- [ ] 5.3 Implement `pair_balances()`, `user_total(user_id)`, and `expenses_version()` (largest `seq` over expenses, shares and payments) per design D7.
- [ ] 5.4 Implement the expense-list query: expenses and payments newest first, grouped by month and by trip, with the viewer's part.
- [ ] 5.5 Write tests for every scenario in the expenses and balances-settlement specs, including former members with open balances, undo of an expense (balances return) and undo of a payment.

## 6. Shopping trip (needs 1; codes against 4 and 5; owns `services/trips.py`, `tests/test_trips.py`)

- [ ] 6.1 Implement `trip_form_data(list_id)` (checked items with and without "for whom") and `complete_trip(...)` per design D11, in one transaction: trip row, the for-other, personal and equal expenses (none with zero amount), then clear checked items.
- [ ] 6.2 Implement the fewer-than-two-members path (clear only).
- [ ] 6.3 Write tests for every scenario in the shopping-trip spec, including the rollback when a step fails.

## 7. i18n machinery and formatting (needs 1; owns `i18n.py`, `web/formatting.py`, `tests/test_i18n.py`, `tests/test_formatting.py`)

- [ ] 7.1 Implement catalog loading (`tomllib`), `t` with placeholder substitution, and a generic `tn` with a per-language plural rule table holding only the English rule now (design D10).
- [ ] 7.2 Implement `money(cents)` (`€42.10`) and `date(d)` (`21 Oct 2026`) in `web/formatting.py` per the i18n spec; month names come from the catalog.
- [ ] 7.3 Bind `t`, `tn`, `money` and `date` as Jinja2 globals.
- [ ] 7.4 Write the catalog tests: every key used in `templates/` and `src/` exists (scan for `t("...")`/`tn("...")`), plural keys have `one` and `other`, placeholders match. Plus tests for every i18n spec scenario.

## 8. Web UI (needs 1 and the approved mockup from 2; owns `web/*.py` except `common.py`/`templating.py` after group 1, `templates/`, `static/`, `i18n/en.toml`, `tests/test_web_*.py`, `tests/test_e2e.py`)

- [ ] 8.0 Build the app shell per design D18: tabs Lists / Expenses / Settings (bottom navigation on phones), following `.mockups/ui-v1/` and its `NOTES.md`. Stats (v1.1) is not built.
- [ ] 8.1 Vendor static assets: own `app.css` (HA-named variables), `app.js`, `theme.js` (HA theme inheritance as in the design doc), `icons.svg` with the used MDI icons and their licence. Test: no external hosts in any page.
- [ ] 8.2 Build the "Who are you?" picker, the standalone login page, the user menu (switch person; no language switch).
- [ ] 8.3 Build the list page: list switcher, add field with live suggestions (`/lists/{id}/suggest`), add field with the inline quantity box and "for" person toggle (tap cycles shared and members, picker with 3 or more members, both reset after each add), list switcher as chips (horizontal scroll), items with quantity and "for whom", one-tap check, collapsed checked section, clear checked, item edit dialog, drag reorder, polling `/lists/{id}/version` with Page Visibility (design D9).
- [ ] 8.4 Build the expense pages: add/edit form with paid-by dropdown and the four one-tap split choices (live "left" amount for exact), expense list with each trip as one collapsed row (badge, list name, trip total) that expands to its expenses, plus the viewer's part, delete without confirmation, the fewer-than-two-members hint.
- [ ] 8.4a Build the delete snackbar (about 10 s, Undo posts to the restore routes) and the no-JS fallback (Undo `post_button` on the redirect target page); confirm dialog only for deleting a whole list; apply to items, lists, expenses and payments. Follows the element added to `docs/dev/design.md` in 2.3a.
- [ ] 8.5 Build the balances page with pair rows, own total, settle-up form (prefilled, partial, over-payment warning).
- [ ] 8.6 Build the "Done shopping" form and its confirmation.
- [ ] 8.7 Build Settings: users with member switches (with the open-balance warning), add person (standalone/picker mode), list management.
- [ ] 8.8 Add every UI string to the English catalog, including the snackbar strings "Deleted <thing>" and "Undo" (with the thing: item, list, expense, payment) and the member-off warning with the amount.
- [ ] 8.9 Write template tests: every page renders under root and under an `X-Ingress-Path` prefix with all URLs prefixed, with English strings. Write `test_e2e.py` driving the real forms: add items, check, done shopping, balances, settle up. Write the "no session writes in `web/`" check. Capture screenshots (desktop/phone, light/dark) and compare with the approved mockup.

## 9. Add-on packaging (needs 1; owns `addon/cekar/`, `Dockerfile`, `docker/`, `repository.yaml`, `api/v1.py`, `tests/test_api.py`)

- [ ] 9.1 Check the skeleton's `Dockerfile` (Python 3.12, `uv` from the lockfile) and the entrypoint that reads the mode (8099 in add-on mode, 8080 standalone, API listener on 8100 when a token is set).
- [ ] 9.2 Check `addon/cekar/config.yaml` against design D14 (`panel_admin: false`, `mdi:basket`, `8100/tcp: null`, `api_token` the only option, no `homeassistant_api`). Finish `DOCS.md` and `CHANGELOG.md`; add `icon.png` and `logo.png`. Verify keys against the current HA add-on developer docs.
- [ ] 9.2a Write tests for the optional API listener scenarios in the web-access and ha-addon specs (token required, wrong token, only `/api/v1` served, no token means no listener, short token fails startup).
- [ ] 9.3 Docker smoke test: build, run standalone, create a list and an expense, restart, data still there.

## 10. User documentation (after 2; finishes after 8; owns `docs/user/`, `README.md`, `mkdocs.yml`)

- [ ] 10.1 Write `docs/user/` pages: install, first start (members in Settings), lists and suggestions, expenses and split choices, balances and settle up, done shopping.
- [ ] 10.2 Write the README: what it is, install as an add-on, run standalone, environment variables, backups.
- [ ] 10.3 Add real-app screenshots once group 8 has landed. `mkdocs build --strict` passes.

## 11. Integration, release and verification (after 3–10)

- [ ] 11.1 Run the full test suite; fix integration gaps between groups.
- [ ] 11.2 Release `v0.1.0` per the procedure in `CLAUDE.md` (version in `config.yaml`, `pyproject.toml` + `uv lock`, `SOURCE_REF` in the add-on Dockerfile, CHANGELOG, tag, push).
- [ ] 11.3 Install on `haos-test` from the repository URL. As two different HA users (one admin, one not): add items on one, see them appear on the other within ~5 s; tick members; record an equal, a for-other and a personal expense; done shopping; settle up partially; delete an item and an expense and undo both; check that no language switch is shown. Screenshot inside HA and review against the mockup.
- [ ] 11.4 Run `openspec validate add-cekar-v1 --strict` and update the artifacts to match what was built.
