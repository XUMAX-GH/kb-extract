#!/usr/bin/env bash
set -euo pipefail
VENV_ROOT="${HOME}/.kb-extract"
if [ -d "${VENV_ROOT}" ]; then
    echo "Removing ${VENV_ROOT} ..."
    rm -rf "${VENV_ROOT}"
    echo "Done."
else
    echo "Nothing to uninstall."
fi
