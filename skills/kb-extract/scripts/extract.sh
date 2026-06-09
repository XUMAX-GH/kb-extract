#!/usr/bin/env bash
set -euo pipefail

PATH_ARG="${1:?用法: extract.sh <路径> [--force] [--dry-run]}"
shift

# 1. 确认 CLI 已安装。
if ! kb adapters --json >/dev/null 2>&1; then
    echo "未找到 kb CLI。请先在 kb-extract 仓库根目录运行 install.sh。" >&2
    exit 1
fi

# 2. 调用 extract。
kb extract "${PATH_ARG}" --json "$@"
