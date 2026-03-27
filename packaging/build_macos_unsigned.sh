#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[1/4] Upgrade pip"
"${PYTHON_BIN}" -m pip install --upgrade pip || true

echo "[2/4] Install dependencies"
"${PYTHON_BIN}" -m pip install -r requirements.txt -r requirements2.txt pyinstaller

echo "[3/4] Build Pointer.app with PyInstaller"
"${PYTHON_BIN}" -m PyInstaller packaging/pyinstaller/pointer.spec --noconfirm --clean

echo "[4/4] Build unsigned DMG"
chmod +x packaging/macos/create_dmg.sh
packaging/macos/create_dmg.sh "dist/Pointer.app" "dist/Pointer.dmg"

echo "Done: dist/Pointer.app and dist/Pointer.dmg"
