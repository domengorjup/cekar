# Cekar

Household shopping lists and shared expenses, as a Home Assistant add-on (Ingress) or a standalone Docker container. Early skeleton: the features are not built yet.

Cekar shares its stack with its sibling projects: FastAPI, SQLite, Jinja2 templates in the Home Assistant look, no CDN.

## Install as a Home Assistant add-on

1. Settings, Add-ons, Add-on store, menu, Repositories: add this repository's URL.
2. Install "Cekar". The image is built locally on the HA host from `addon/cekar/Dockerfile`.
3. Start it and enable "Show in sidebar".

Options and details: [addon/cekar/DOCS.md](addon/cekar/DOCS.md).

## Run standalone

```sh
docker build -t cekar .
docker run -d --name cekar -p 8080:8080 -v ./data:/data cekar
```

Open `http://localhost:8080/`. The container runs as UID 1000, so the data folder must be writable by it (`chown 1000 ./data`, or `--user "$(id -u):$(id -g)"`). On SELinux hosts append `:Z` to the volume option.

| Variable | Default | Meaning |
|---|---|---|
| `CEKAR_MODE` | `standalone` | `standalone` or `addon` (behind HA Ingress, no login) |
| `CEKAR_HOST` | `0.0.0.0` | Bind address |
| `CEKAR_PORT` | `8080` (`8099` in addon mode) | Listen port |
| `DATA_DIR` | `/data` | Folder holding the SQLite database |
| `CEKAR_PASSWORD` | unset | Enables the login (standalone) |
| `CEKAR_API_TOKEN` | unset | Bearer token for `/api/v1` (standalone); in add-on mode the `api_token` option |
| `CEKAR_API_PORT` | `8100` in addon mode | Port of the add-on API listener |
| `CEKAR_SECRET` | unset | Key for signing session cookies |
| `BASE_PATH` | empty | URL prefix when served behind a reverse proxy |

## Development

See `docs/dev/development.md`. Released under the MIT licence, see [LICENSE](LICENSE).
