#!/usr/bin/env bash
set -euo pipefail
PATH_ARG="${1:?usage: verify.sh <path> [--fail-fast]}"
shift
command -v kb >/dev/null 2>&1 || { echo "kb CLI not found. Run install.sh first." >&2; exit 1; }
kb verify "${PATH_ARG}" --json "$@"
