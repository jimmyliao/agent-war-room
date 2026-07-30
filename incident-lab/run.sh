#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

exec python3 server.py --host "${INCIDENT_LAB_HOST:-127.0.0.1}" --port 8899
