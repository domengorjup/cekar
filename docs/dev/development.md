# Local development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync                  # creates .venv and installs the project and dev tools
DATA_DIR=./data uv run cekar
```

Open `http://localhost:8080/`. Useful variables: `DATA_DIR`, `CEKAR_PORT`, `CEKAR_PASSWORD`, `CEKAR_API_TOKEN`.

## Tests

```sh
uv run pytest
```

## Documentation

```sh
uv run --group docs mkdocs serve          # live preview at http://127.0.0.1:8000
uv run --group docs mkdocs build --strict # build into site/ (git-ignored)
```

The docs dependencies are in the separate `docs` dependency group, so `uv sync` does not install them. The docs are published to GitHub Pages by `.github/workflows/docs.yml`.

## Dependencies

Add runtime dependencies with `uv add <package>`, and docs tooling with `uv add --group docs <package>`. Do not use `pip` directly.
