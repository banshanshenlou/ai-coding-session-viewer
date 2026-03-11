#!/usr/bin/env bash
set -euo pipefail

find_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi

  return 1
}

if ! PYTHON_BIN="$(find_python)"; then
  echo "[错误] 未检测到 Python，请先安装 Python 3。"
  exit 1
fi

if ! "${PYTHON_BIN}" -m pip --version >/dev/null 2>&1; then
  echo "[错误] 已检测到 Python，但当前环境不可用 pip。"
  echo "[提示] 请先执行 ${PYTHON_BIN} -m ensurepip，或重新安装带 pip 的 Python。"
  exit 1
fi

VIEWER_URL="${OPENCODE_VIEWER_URL:-http://localhost:8765}"

echo "Installing dependencies..."
"${PYTHON_BIN}" -m pip install -r requirements.txt

echo
echo "Starting OpenCode Session Viewer..."
echo "Open ${VIEWER_URL} in your browser"
echo

exec "${PYTHON_BIN}" app.py
