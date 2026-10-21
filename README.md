<p align="center"><img src="addon/cekar/icon.png" alt="Cekar" width="96" height="96"></p>

# Cekar

**Self-hosted shopping lists and shared expenses for one household.**

*In development: v1.0 not released yet.*

[![Tests](https://github.com/domengorjup/cekar/actions/workflows/tests.yml/badge.svg)](https://github.com/domengorjup/cekar/actions/workflows/tests.yml)
[![Docs](https://github.com/domengorjup/cekar/actions/workflows/docs.yml/badge.svg)](https://github.com/domengorjup/cekar/actions/workflows/docs.yml)
[![Licence: MIT](https://img.shields.io/github/license/domengorjup/cekar)](LICENSE)
[![Latest release](https://img.shields.io/github/v/tag/domengorjup/cekar?label=release)](https://github.com/domengorjup/cekar/tags)

<p align="center"><a href="https://domengorjup.github.io/cekar/"><img src="https://img.shields.io/badge/Read_the_documentation-03a9f4?style=for-the-badge&logo=materialformkdocs&logoColor=white" alt="Read the documentation"></a></p>

<!-- Screenshots: add 2-3 captioned screenshots from docs/assets/screenshots once the UI is built, in this form:
![Shopping list](docs/assets/screenshots/<file>.png)
*Caption.*
-->

Cekar is a self-hosted replacement for a shared Google Keep shopping list and Splitwise, for one household. It uses Home Assistant users, so nobody needs a separate account.

## Features

- Several shopping lists. Items have a name, an optional quantity, who added them and, if wanted, who they are for. Suggestions from history appear while you type.
- Checked items move to a collapsed section; "Clear checked" removes them. Changes from other household members show up within seconds.
- Shared expenses in euro: split equally or by exact amounts, or use the one-tap options "For <person>" and "Personal". One payer per expense.
- Balances per pair of members, and "Settle up" for a full or partial payment.
- "Done shopping" turns the checked items and the receipt total into expenses. Items marked "for <person>" are charged to that person; the rest is split equally.
- Uses the Home Assistant user, with no separate login in the add-on. A "Who are you?" picker is the fallback and is used in standalone mode.
- You choose which users take part in shared expenses (children, guests and tablet accounts can stay out).
- Looks like Home Assistant and opens in the sidebar through Ingress. English only in v1.0.
- Runs as a Home Assistant add-on or as a standalone Docker container; the data is one SQLite file.

### Planned

Not part of v1.0. These come in v1.1 or later:

- Editable expense categories with statistics and filters.
- Recurring expenses.
- Receipt photo and note.
- CSV export and Splitwise history import.
- Price memory per item.
- Notifications through Home Assistant.
- A Lovelace dashboard card.
- Slovenian translation.

## Install as a Home Assistant add-on

Requires Home Assistant Supervisor 2026.10.3 or later. Older versions let a logged-in user forge another person's identity.

[![Add the repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fdomengorjup%2Fcekar)

Press the button, or add the repository by hand: **Settings > Add-ons > Add-on store > menu (three dots) > Repositories**, paste `https://github.com/domengorjup/cekar` and click **Add**. In Home Assistant 2026.6 and later add-ons are called apps: **Settings > Apps > Install app > menu > Repositories**.

Then install **Cekar** (the image is built on your Home Assistant host, so the first install takes a few minutes), start it and enable **Show in sidebar**.

Options and details: [addon/cekar/DOCS.md](addon/cekar/DOCS.md).

## Run standalone

```sh
docker build -t cekar .
docker run -d --name cekar -p 8080:8080 -v ./data:/data cekar
```

Open `http://localhost:8080/`. The container runs as UID 1000, so the data folder must be writable by it. Either `chown 1000 ./data` or add `--user "$(id -u):$(id -g)"`. On SELinux hosts (Fedora) append `:Z` to the volume option.

### Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `CEKAR_MODE` | `standalone` | `standalone` or `addon` (behind HA Ingress, no login) |
| `CEKAR_HOST` | `0.0.0.0` | Bind address |
| `CEKAR_PORT` | `8080` (`8099` in addon mode) | Listen port |
| `DATA_DIR` | `/data` | Folder holding the SQLite database |
| `CEKAR_PASSWORD` | unset | Enables the login (standalone) |
| `CEKAR_API_TOKEN` | unset | Bearer token for `/api/v1` (standalone). In add-on mode it is the `api_token` option and enables the extra API port, see the add-on `DOCS.md` |
| `CEKAR_API_PORT` | `8100` in addon mode | Port of the add-on API listener (`/api/v1` only, Bearer token, started only when a token of 16+ characters is set) |
| `CEKAR_SECRET` | unset | Key for signing session cookies |
| `BASE_PATH` | empty | URL prefix when served behind a reverse proxy |

Without `CEKAR_PASSWORD` there is no login: put a reverse proxy in front if the port is reachable by others.

## Backup and restore

In the add-on, `/data` (the SQLite database) is included in Home Assistant backups; restoring a backup restores it. A CSV export is planned for v1.1.

## Licence

Released under the MIT licence, see [LICENSE](LICENSE).

Home Assistant, Google Keep and Splitwise are trademarks of their respective owners; this project is not affiliated with or endorsed by them.

## Disclaimer

Cekar was developed with the assistance of AI (large language models). It is provided "as is", without warranty of any kind, express or implied. The authors accept no responsibility or liability for any damage, data loss or other consequences arising from its use. See the MIT licence for the full terms.
