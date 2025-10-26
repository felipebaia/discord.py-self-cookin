#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV_PATH="${REPO_DIR}/.venv/bin/activate"
if [[ ! -f "${VENV_PATH}" ]]; then
  echo "Virtual environment not found at ${VENV_PATH}" >&2
  exit 1
fi

source "${VENV_PATH}"

python "${REPO_DIR}/src/discord_server/selfbot_relay.py" "$@"
