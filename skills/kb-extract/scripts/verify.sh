#!/usr/bin/env bash
set -euo pipefail
PATH_ARG="${1:?用法: verify.sh <路径> [--fail-fast]}"
shift
command -v kb >/dev/null 2>&1 || { echo "未找到 kb CLI。请先运行 install.sh。" >&2; exit 1; }
kb verify "${PATH_ARG}" --json "$@"
