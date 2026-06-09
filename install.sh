#!/usr/bin/env bash
# install.sh — kb-extract installer for macOS/Linux
set -euo pipefail

VENV_ROOT="${HOME}/.kb-extract"
VENV_PATH="${VENV_ROOT}/venv"

command -v uv >/dev/null 2>&1 || {
    echo "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
}

if [ ! -d "${VENV_PATH}" ]; then
    echo "Creating venv at ${VENV_PATH} ..."
    uv venv "${VENV_PATH}" --python 3.11
fi

REPO="$(cd "$(dirname "$0")" && pwd)"
echo "Installing kb-extract from ${REPO} ..."
uv pip install --python "${VENV_PATH}/bin/python" -e "${REPO}"

echo "Pre-downloading docling models (may take several minutes)..."
export DOCLING_ARTIFACTS_PATH="${VENV_ROOT}/docling-models"
"${VENV_PATH}/bin/python" -c "import docling; print('docling import ok')"

echo ""
echo "Install complete. Add to PATH (one-time):"
echo "  echo 'export PATH=\"${VENV_PATH}/bin:\$PATH\"' >> ~/.bashrc"
echo ""
echo "Then run: kb --version"
