# Cekar

Shared shopping lists and shared expenses for one household. Cekar replaces a shared Google Keep list and Splitwise, and links the two: "Done shopping" turns the checked items and the receipt total into expenses.

## Features

- **Shopping lists:** several lists; items with an optional quantity and an optional "for" person; suggestions from history while typing; checked items move to a collapsed section and can be cleared. Changes from other household members appear within a few seconds.
- **Expenses:** amounts in euros. Split equally or by exact amounts, or use "For <person>" (they owe the full amount) or "Personal" (nobody owes). One payer per expense, chosen from a dropdown.
- **Balances and settle up:** a balance for each pair of members; "Settle up" records a full or partial payment.
- **Done shopping:** the checked items of a list and the receipt total become expenses; items marked for a person can be priced and are charged to that person. The checked items are then cleared.
- **Undo:** deleted items, lists, expenses and payments can be restored with the Undo button that follows a delete.
- **Household members:** Home Assistant users are registered the first time they open the app. In Settings the household ticks who takes part in shared expenses (children, guests and tablet accounts can stay out and still use the lists).

The app is in English. Money is in euros only.

## Installation

1. In Home Assistant open Settings, Add-ons, Add-on store, menu (three dots), Repositories. In newer versions add-ons are called apps: Settings, Apps, Install app, menu, Repositories.
2. Add the repository URL `https://github.com/domengorjup/cekar` and close the dialog.
3. Select Cekar, then Install. The image is built on your Home Assistant host, so the first install takes a few minutes.
4. Start the add-on, then switch on **Show in sidebar** on its Info page (it is off after a fresh install). The panel "Cekar" opens the app through Ingress and is visible to all Home Assistant users, not only administrators.

Home Assistant Supervisor 2026.10.3 or later is required. Older versions let a logged-in user forge another person's identity.

## Who is who

Cekar takes the acting person from the user that Home Assistant passes through Ingress; nobody logs in to the app. If a client does not pass the user, the app shows a "Who are you?" picker and remembers the choice in a cookie. Open Settings first and tick the people who share expenses.

## Options

Options are written by Home Assistant to `/data/options.json` and read when the add-on starts. Restart the add-on after changing them.

| Option      | Default | Description |
|-------------|---------|-------------|
| `api_token` | unset   | Bearer token for the optional API port (at least 16 characters; shorter values stop the add-on with an error). Leave empty to keep the API off. |

## API

Through Ingress the API (`/api/v1`) is only reachable from the sidebar. To use it from another client:

1. Set `api_token` in the add-on options to a random string of 16 or more characters.
2. In the add-on Network section, set a host port for `8100/tcp`. The port is off by default.
3. Restart the add-on. If the port is mapped but no token is set, the API port does not start and the log says why.

The port serves only `/api/v1/*`, only with `Authorization: Bearer <token>`; every other path returns 404. It is plain HTTP, so use it only on a network you trust. In this version the only endpoint is `GET /api/v1/health`, which reports that the app is up.

## Data and backups

The SQLite database (`cekar.db`) and the generated secret are stored in the add-on's `/data` folder, which survives restarts and upgrades and is included in Home Assistant backups. Database migrations run automatically at startup.

## Known limitations

- The web app is only reachable through Ingress (no app login). Anyone who can open the Home Assistant sidebar entry can use the app.
- One household, euros only, English only.
- Only the `amd64` and `aarch64` architectures are supported.

## Support

Report problems in the project's issue tracker: https://github.com/domengorjup/cekar/issues

## Disclaimer

Cekar was developed with the assistance of AI (large language models). It is provided "as is", without warranty of any kind, express or implied. The authors accept no responsibility or liability for any damage, data loss or other consequences arising from its use. See the MIT licence for the full terms.
