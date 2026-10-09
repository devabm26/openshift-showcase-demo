#!/usr/bin/env bash
# ==============================================================================
# run_local.sh — Run the thoughts dashboard from DevSpaces
#
# DevSpaces runs inside the cluster — the DB is reachable directly via
# its cluster DNS name. No port-forwarding needed.
#
# Usage:
#   ./scripts/run_local.sh
# ==============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
fi

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

echo "Starting Flask — http://0.0.0.0:8080"
echo "DB: ${DB_HOST}:${DB_PORT}/${DB_NAME}"

cd "$PROJECT_ROOT"
python -m flask --app src/app run --host 0.0.0.0 --port 8080 --debug
