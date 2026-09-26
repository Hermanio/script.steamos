#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
The test runner for Boot into SteamOS.

  ./run-tests.sh              static + unit tests                  (~1s)
  ./run-tests.sh firmware     this machine's real UEFI variables   (needs root)
  ./run-tests.sh check        build the zip, run kodi-addon-checker (network)
  ./run-tests.sh all          every level, in that order

The first run creates .venv and installs tests/requirements.txt. The
firmware level reads real variables and never writes them.
EOF
}

ADDON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ADDON_DIR}/.venv"
PY="${VENV}/bin/python"

if [[ ! -x "${VENV}/bin/kodi-addon-checker" ]]; then
    echo "==> installing test dependencies into ${VENV}"
    python3 -m venv "${VENV}"
    "${VENV}/bin/pip" install -q -r "${ADDON_DIR}/tests/requirements.txt"
fi

cd "${ADDON_DIR}"
pytest() { "${PY}" -m pytest tests -q "$@"; }

case "${1:-fast}" in
    fast) pytest -m 'not firmware and not compliance' ;;
    firmware) pytest -m firmware ;;
    check) pytest -m compliance ;;
    all)
        pytest -m 'not firmware and not compliance'
        pytest -m firmware
        pytest -m compliance
        ;;
    -h|--help) usage ;;
    *) usage >&2; exit 2 ;;
esac
