#!/usr/bin/env bash
# install.sh — kb-extract macOS / Linux 端安装脚本
set -euo pipefail

VENV_ROOT="${HOME}/.kb-extract"
VENV_PATH="${VENV_ROOT}/venv"

command -v uv >/dev/null 2>&1 || {
    echo "未找到 uv。请先安装：curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
}

if [ ! -d "${VENV_PATH}" ]; then
    echo "正在 ${VENV_PATH} 创建 venv ..."
    uv venv "${VENV_PATH}" --python 3.11
fi

REPO="$(cd "$(dirname "$0")" && pwd)"
echo "正在从 ${REPO} 安装 kb-extract ..."
uv pip install --python "${VENV_PATH}/bin/python" -e "${REPO}"

echo "预下载 docling 模型中（首次可能需要几分钟）..."
export DOCLING_ARTIFACTS_PATH="${VENV_ROOT}/docling-models"
"${VENV_PATH}/bin/python" -c "import docling; print('docling import ok')"

echo ""
echo "安装完成。请把以下目录加入 PATH（一次性）："
echo "  echo 'export PATH=\"${VENV_PATH}/bin:\$PATH\"' >> ~/.bashrc"
echo ""
echo "之后运行：kb --version"
