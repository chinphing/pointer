#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-dist/Pointer.app}"
DMG_NAME="${2:-Pointer.dmg}"
VOLUME_NAME="${3:-Pointer Installer}"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "App bundle not found: ${APP_PATH}"
  exit 1
fi

STAGE_DIR="$(mktemp -d)"
cp -R "${APP_PATH}" "${STAGE_DIR}/Pointer.app"
ln -s /Applications "${STAGE_DIR}/Applications"

hdiutil create \
  -volname "${VOLUME_NAME}" \
  -srcfolder "${STAGE_DIR}" \
  -ov \
  -format UDZO \
  "${DMG_NAME}"

rm -rf "${STAGE_DIR}"
echo "Created ${DMG_NAME}"
