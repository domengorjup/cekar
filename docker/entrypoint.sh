#!/bin/sh
# Pick defaults from CEKAR_MODE, then start the app.
# standalone (default): port 8080. addon: HA ingress port 8099 (+ API port 8100 when api_token is set), data in /data.
set -eu

case "${CEKAR_MODE:-standalone}" in
  addon)
    export CEKAR_PORT="${CEKAR_PORT:-8099}"
    export CEKAR_API_PORT="${CEKAR_API_PORT:-8100}"
    export DATA_DIR="${DATA_DIR:-/data}"
    ;;
  standalone)
    export CEKAR_PORT="${CEKAR_PORT:-8080}"
    export DATA_DIR="${DATA_DIR:-/data}"
    ;;
  *)
    echo "Unknown CEKAR_MODE: ${CEKAR_MODE}" >&2
    exit 1
    ;;
esac
export CEKAR_HOST="${CEKAR_HOST:-0.0.0.0}"

exec cekar "$@"
