import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH).resolve().parents[1]
ENTRYPOINT = str(PROJECT_ROOT / "start_pointer.py")

hiddenimports = []
hiddenimports += collect_submodules("python.api")
hiddenimports += collect_submodules("python.websocket_handlers")
hiddenimports += collect_submodules("python.tools")
hiddenimports += collect_submodules("agents")

datas = [
    (str(PROJECT_ROOT / "webui"), "webui"),
    (str(PROJECT_ROOT / "conf"), "conf"),
    (str(PROJECT_ROOT / "agents"), "agents"),
    (str(PROJECT_ROOT / "prompts"), "prompts"),
    (str(PROJECT_ROOT / "python" / "api"), "python/api"),
    (str(PROJECT_ROOT / "python" / "websocket_handlers"), "python/websocket_handlers"),
    (str(PROJECT_ROOT / "python" / "tools"), "python/tools"),
    (str(PROJECT_ROOT / "LICENSE"), "."),
]

block_cipher = None


a = Analysis(
    [ENTRYPOINT],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Pointer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Pointer.app",
        icon=None,
        bundle_identifier="com.pointer.app",
    )
else:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="Pointer",
    )
