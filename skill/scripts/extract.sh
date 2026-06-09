#!/usr/bin/env bash
set -euo pipefail

PATH_ARG="${1:?usage: extract.sh <path> [--force] [--dry-run]}"
shift

# 1. Verify CLI installed.
if ! kb adapters --json >/dev/null 2>&1; then
    echo "kb CLI not found. Run install.sh from the kb-extract repo first." >&2
    exit 1
fi

# 2. Invoke extract.
kb extract "${PATH_ARG}" --json "$@"
