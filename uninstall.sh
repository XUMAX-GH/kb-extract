#!/usr/bin/env bash
set -euo pipefail
VENV_ROOT="${HOME}/.kb-extract"
if [ -d "${VENV_ROOT}" ]; then
    echo "正在移除 ${VENV_ROOT} ..."
    rm -rf "${VENV_ROOT}"
    echo "完成。"
else
    echo "没有需要卸载的内容。"
fi
