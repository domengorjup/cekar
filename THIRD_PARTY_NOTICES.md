# Third-party notices

Cekar itself is released under the MIT licence (see `LICENSE`). This file lists third-party material that is bundled with it.

## Vendored front-end assets

Located in `src/cekar/web/static/`. Licence texts sit next to the files (see `VENDORED.md`).

| Asset | Version | Licence | Copyright |
|---|---|---|---|
| Material Design Icons (`icons.svg`, 13 icons from `@mdi/svg`, paths unmodified) | 7.4.47 | Apache-2.0 via the Pictogrammers Free License (`LICENSE-mdi.md`) | No per-icon copyright line in the package |

## Python dependencies

Python dependencies (FastAPI, Uvicorn, SQLAlchemy, Alembic, Jinja2, python-multipart, itsdangerous and their dependencies) are not vendored. They are installed from PyPI at image build time, and each package ships its own licence file in its `*.dist-info` directory inside the image.

## Icons

`addon/cekar/icon.png` and `addon/cekar/logo.png` (once added) are covered by the project licence.

## Trademarks

Home Assistant is a trademark of its owner. This project is not affiliated with or endorsed by them.
