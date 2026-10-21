# Project: cekar

## Purpose
A self-hosted Home Assistant add-on for one household: shared shopping lists and shared expenses. It replaces a shared Google Keep list and Splitwise (de-googling), and links the two: "Done shopping" turns the checked items and the receipt total into expenses.

The name is the Slovenian word "cekar" (a shopping bag or basket). English speakers may read it as "checker"; that is accepted.

## Key constraints
- Runs as a Home Assistant OS add-on: Docker container, web UI served through HA Ingress (sidebar panel, visible to all HA users), data in a SQLite database under `/data`. Also runs standalone (Docker, port 8080, optional password).
- Identity comes from Home Assistant (Ingress user headers), with a "Who are you?" picker as fallback and in standalone mode. No app logins in add-on mode.
- One household, EUR only (integer cents). English only in v1.0 (i18n machinery kept; Slovenian later).
- Python backend; dependencies managed with `uv` (`pyproject.toml`).
- Scope is the v1 feature set in `openspec/changes/add-cekar-v1/`; v1.1 items are listed there as follow-ups. No feature creep. Never: voice input, Google Keep import, multiple currencies, multiple households.
- The data model stays ready for a later offline app (UUID keys, `updated_at`, `deleted_at` tombstones, global change sequence, writes only through `services/`). See `docs/dev/offline.md`.
- Never commit real personal data (names, receipts, exports); tests use invented people (Ana, Bor, Cene).

## Git
- Remote: `git@github.com:domengorjup/cekar.git` (not created yet).
- Release procedure: bump the version in `addon/cekar/config.yaml`, `pyproject.toml` (then `uv lock`) and `SOURCE_REF=v<version>` in `addon/cekar/Dockerfile`, add a CHANGELOG entry, commit, tag `v<version>`, push `master` and the tag. Details in `docs/dev/release.md`.
- Standing permission: commit locally at sensible checkpoints (after the foundation, after each completed task group, after final checks).
- Standing permission: push `master` and release tags to `origin` (github.com/domengorjup/cekar) after tests pass. Never force-push or rewrite published history without asking.

## Workflow
- Disclaimer: the README, the add-on `DOCS.md` and every docs page (MkDocs `copyright` footer) carry the notice that the project was made with AI assistance and is provided "as is" without warranty or liability. Keep it on new user-facing documents; the sibling project (Glovebox) uses the same wording.
- README: keep `README.md` in this layout, in this order: (1) centred icon (`addon/cekar/icon.png`); (2) title; (3) bold one-line tagline; (4) status line ("In development: v1.0 not released yet."); (5) badges: Tests, Docs, Licence, Latest release; (6) the "Read the documentation" button; (7) 2-3 captioned screenshots from `docs/assets/screenshots`; (8) Features, then a short "Planned" list; (9) Install as a Home Assistant add-on (add-repository badge, manual path, apps note, minimum Supervisor); (10) Run standalone, with the environment-variable table (only variables that exist in `config.py`); (11) Backup and restore; (12) Licence, with the trademarks line; (13) Disclaimer. Keep it in step with the shipped features at every release. When v1.0 is released, replace the screenshots placeholder with real screenshots and remove the status line. Glovebox's README is the model.
- OpenSpec (`openspec/`) is for behaviour, API and data-model changes. UI/layout work is done as design iterations without OpenSpec: clickable mockup or the running app, screenshots via headless browser, user feedback, repeat. Mockups live in `.mockups/` (locally excluded from git). `.mockups/ui-v1/` is the living UI mockup the user checks at will (open `index.html` directly, no server): design changes land there first, are recorded in its `NOTES.md` changelog, then go into the app.
- UI design language: `docs/dev/design.md` lists the tokens and standard elements (with class names and snippets). Reuse an element from there before making a new one; follow Home Assistant / Material conventions and only make our own element if it is significantly simpler than the standard one; add every new repeated element to that document. No plain text links for in-app navigation (use buttons, icon buttons, list rows, tabs or chips).
- Every user-visible string goes through the catalog (`src/cekar/i18n/en.toml`, English only in v1.0) with `t()`/`tn()`; no hard-coded text. Slovenian (`sl.toml`, language switch, per-user preference) is a later follow-up, not v1.0. Money shows as `€42.10`; amount input accepts a decimal comma or point.
- UI structure (confirmed): list switcher as chips; tabs Lists / Expenses / Settings (bottom nav on phone); Stats (v1.1) is a "List | Stats" sub-view of Expenses; the add field takes the name plus inline quantity and "for" toggle, the edit dialog holds the full fields; trip expenses show as one collapsed row. `.mockups/ui-v1/` (with its `NOTES.md`) is the approved mockup and the reference for UI work.
- Test HA instance: HAOS VM `haos-test` in the user's restricted Incus project on `linux-turbo` (reach via SSH tunnel; HA UI is on VM port 80). It is shared with the sibling project. Credentials for it live outside the repo in `~/.config/cekar-test/ha.env`; never print or commit them.

## Sibling project
glovebox (`/mnt/data/workspace/autotracker_app`, car running costs) shares this project's stack, design language, add-on packaging, release procedure and test VM. Cross-cutting approaches are documented in `docs/dev/` of each project: offline app (`offline.md`), HA user identity and i18n (`architecture.md` here, design D2 and D10 of `add-cekar-v1`). Read the sibling's doc on a topic before designing it here, and keep the two in step. Never edit the sibling's files. Code, templates, user docs and the README describe this app on its own and do not mention the sibling; developer notes (`openspec/`, `docs/dev/`) may cite it where a decision is reused from it.

## Autonomous implementation–review loop
Used when the user asks Claude to work without prompting them.
1. **Plan:** the coordinating session splits work into independent tasks with clear file ownership (see "How to run this change in parallel" in the change's `tasks.md`) and dispatches subagents (parallel where files don't overlap).
2. **Implement:** each subagent implements, runs the full test suite, and for UI work captures headless-browser screenshots (desktop 1400x900, phone 390x844, light and dark).
3. **Review:** the coordinator reviews every result: tests green, diff scope matches the task, screenshots compared against the approved mockup, docs build with `--strict`, catalog keys all present, no references to other projects outside `openspec/` and `docs/dev/`, no secrets or personal data. Findings go back to the same subagent as concrete fix requests; repeat until clean (cap ~3 rounds per task; if still blocked, note it for the user instead of asking).
4. **Integrate:** commit, push `master`; release (`.dev/release_deploy.py release`), deploy to the test HA (`deploy`), screenshot inside HA (`screenshot`) and review again. On the test HA, check with two different HA users (one admin, one not).
5. **Report:** a concise summary for the user at the end, including anything left open.

Standing permissions for this loop: anything on the test VM `haos-test` (start/stop/restart, updates, its image and downloads), without disturbing the sibling's add-on there beyond what a test needs; repo changes within the current scope (including deleting superseded files, a CI test workflow and publishing the MkDocs site on GitHub Pages). Nothing that could affect the user's own machine setup or other people's work on `linux-turbo`; ask only if something outside this is truly necessary.

## Next steps
- **Implement v1** (OpenSpec change `add-cekar-v1`): start with task group 0 (verify on `haos-test` that Ingress passes `X-Remote-User-Id` / `-Name` / `-Display-Name`, and what `Accept-Language` arrives), then the foundation, the mockup (needs the user's approval before the templates), and the parallel groups. Open questions Q1–Q4 are in its `design.md`.
- **Create the GitHub repository** `domengorjup/cekar` (ask the user first), then the first push.
- **v1.1 (separate OpenSpec changes, after v1 has been used for a while; decisions are settled in the change's `design.md` Follow-ups):** editable expense categories (5 defaults, managed in Settings, a default category per list) with a Stats sub-view and filters; CSV export and Splitwise CSV import with preview and undo under Settings > Data; recurring expenses; receipt photo and note; price memory per item (estimated list total); notifications via HA notify (needs `homeassistant_api`); a Lovelace card (probably a companion integration with a to-do entity per list; decide later).
- **Later:** Slovenian catalog, language switch, per-user language preference and `Accept-Language` default (after or with v1.1).
- **Stage 2: offline installable app** (design note `docs/dev/offline.md`, shared with the sibling). Not before v1 is in use.

## Structure
- `src/cekar/`: `app.py` (factory `create_app`, `create_api_app`, `main`), `config.py`, `db.py`, `models.py` (planned), `auth.py` (add-on source check, standalone login/token), `urls.py` (`url(request, path)` base-path helper), `migrations/` (Alembic, run at startup), `api/v1.py` (health only in v1), `web/` (`common.py`, `templating.py`, `formatting.py`, `index.py`, `templates/`, `static/` = `app.css`, `app.js`, `theme.js`, `icons.svg` + `LICENSE-mdi.md`, `VENDORED.md`).
- Planned (change `add-cekar-v1`): `identity.py`, `i18n.py` + `i18n/en.toml`, `services/{sync,members,lists,suggestions,expenses,balances,trips}.py`, `web/{lists,expenses,balances,trips,settings,identity}.py`.
- `addon/cekar/` (HA add-on files), `Dockerfile`, `docker/entrypoint.sh`, `repository.yaml`, `.dev/release_deploy.py` (release, deploy to the test HA, screenshots).
- `tests/`: `conftest.py` (migrated in-memory `engine`, `session`, `client` fixtures), `test_smoke.py`, `test_auth.py`; `fixtures/` (invented data only).
- `docs/`: MkDocs site; `docs/dev/` = `architecture.md`, `design.md` (read before touching templates or `app.css`), `offline.md`, `development.md`, `testing.md`, `release.md`; `docs/user/` = user guide.
- `openspec/`: `changes/add-cekar-v1/` (v1 proposal, design, tasks, delta specs); `specs/` fills when a change is archived (via the `openspec-archive` skill).
- Run: `uv run cekar` (env: `CEKAR_MODE`, `DATA_DIR`, `CEKAR_PORT`, `CEKAR_PASSWORD`, ...). Test: `uv run pytest`.
