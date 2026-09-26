#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Build an installable Kodi add-on zip for Boot into SteamOS: one top-level
directory named after the add-on id, holding the add-on and nothing else.

  ./package.sh                 -> dist/script.steamos-<version>.zip
  ./package.sh /tmp/out        write the zip somewhere else
EOF
}

case "${1:-}" in -h|--help) usage; exit 0 ;; esac

ADDON_ID="script.steamos"
SHIPPED=(addon.py addon.xml LICENSE.txt resources)
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$(mkdir -p "${1:-${SRC_DIR}/dist}" && cd "${1:-${SRC_DIR}/dist}" && pwd)"

VERSION="$(tr '\n' ' ' < "${SRC_DIR}/addon.xml" \
    | sed -n 's/.*<addon[^>]*[[:space:]]version="\([0-9][^"]*\)".*/\1/p')"
if [[ -z "${VERSION}" ]]; then
    echo "error: could not parse version from addon.xml" >&2
    exit 1
fi
ZIP_PATH="${OUT_DIR}/${ADDON_ID}-${VERSION}.zip"

STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT
mkdir "${STAGE}/${ADDON_ID}"
( cd "${SRC_DIR}" && cp -a "${SHIPPED[@]}" "${STAGE}/${ADDON_ID}/" )
find "${STAGE}" -name '__pycache__' -type d -prune -exec rm -rf {} +

rm -f "${ZIP_PATH}"
( cd "${STAGE}" && zip -r -q -X "${ZIP_PATH}" "${ADDON_ID}" )

echo "Built ${ZIP_PATH}"
echo "  sha256: $(sha256sum "${ZIP_PATH}" | cut -d' ' -f1)"
