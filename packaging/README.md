# Packaging Guide

This project can be distributed as installers for macOS and Windows.

Current status: installers are built **without code signing/notarization**.

## One-command local builds (unsigned)

From repo root:

- macOS:
```bash
chmod +x packaging/build_macos_unsigned.sh
packaging/build_macos_unsigned.sh
```

- Windows (PowerShell):
```powershell
.\packaging\build_windows_unsigned.ps1
```

## 1) Build app binaries with PyInstaller

From repo root:

```bash
pip install pyinstaller
pyinstaller packaging/pyinstaller/pointer.spec --noconfirm --clean
```

Expected outputs:

- macOS: `dist/Pointer.app`
- Windows: `dist/Pointer/Pointer.exe`

## 2) Build macOS installer (`.dmg`)

```bash
chmod +x packaging/macos/create_dmg.sh
packaging/macos/create_dmg.sh "dist/Pointer.app" "dist/Pointer.dmg"
```

## 3) Build Windows installer (`.exe`)

Install Inno Setup first, then:

```powershell
iscc packaging/windows/pointer.iss
```

Expected output:

- `dist/Pointer-Setup.exe`

## Runtime notes

- Annotation service stays external. Configure `COMPUTER_ANNOTATE_API_BASE` via `.env` or environment variables.
- Do not package repository `.env` into release artifacts.
- On macOS, users must grant Screen Recording and Accessibility permissions to the installed app for computer-use actions.
- Because the app is unsigned for now:
  - macOS may show "unidentified developer" warning on first launch.
  - Windows SmartScreen may show a reputation warning.
