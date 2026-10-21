# Cekar

Household shopping lists and shared expenses for Home Assistant. This is an early skeleton: the features are not built yet.

## Options

Options are written by Home Assistant to `/data/options.json` and read when the add-on starts. Restart the add-on after changing them.

| Option      | Default | Description |
|-------------|---------|-------------|
| `api_token` | unset   | Bearer token for the optional API port (at least 16 characters; shorter values stop the add-on with an error). Leave empty to keep the API off. |

## API

Through Ingress the API (`/api/v1`) is only reachable from the sidebar. To use it from another client, set `api_token`, then set a host port for `8100/tcp` in the add-on Network section and restart. The port serves only `/api/v1/*`, only with `Authorization: Bearer <token>`. It is plain HTTP, so use it only on a network you trust. `GET /api/v1/health` reports that it is up.

## Data and backups

The SQLite database is stored in the add-on's `/data` folder, which survives restarts and upgrades and is included in Home Assistant backups.

## Known limitations

- The web app is only reachable through Ingress (no app login). Anyone who can open the Home Assistant sidebar entry can use the app.
- Only the `amd64` and `aarch64` architectures are supported.

## Disclaimer

Cekar was developed with the assistance of AI (large language models). It is provided "as is", without warranty of any kind, express or implied. The authors accept no responsibility or liability for any damage, data loss or other consequences arising from its use. See the MIT licence for the full terms.
