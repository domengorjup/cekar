# Cekar image. Same image for standalone use and (once published) the HA add-on.
# Build from the repository root:  docker build -t cekar .
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CEKAR_MODE=standalone \
    DATA_DIR=/data
COPY --from=build /app/.venv /app/.venv
COPY LICENSE THIRD_PARTY_NOTICES.md /usr/share/doc/cekar/
COPY docker/entrypoint.sh /usr/local/bin/cekar-entrypoint
RUN chmod 755 /usr/local/bin/cekar-entrypoint \
    && useradd --uid 1000 --no-create-home cekar \
    && mkdir /data && chown cekar /data
# Non-root for standalone. The HA add-on image (addon/cekar/Dockerfile) runs as root
# because Supervisor mounts /data as root-owned.
USER cekar
VOLUME /data
EXPOSE 8080
ENTRYPOINT ["cekar-entrypoint"]
