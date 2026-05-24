# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
project_root = Path(SPECPATH).resolve()

datas = [
    (str(project_root / "panel" / "templates" / "index.html"), "panel/templates"),
    (str(project_root / "data" / "mensagens_aquecimento.json"), "data"),
    (str(project_root / "data" / "ia_comercial_config.json"), "data"),
]

hiddenimports = []
for module_name in ("openpyxl", "psycopg", "dotenv"):
    hiddenimports.extend(collect_submodules(module_name))

a = Analysis(
    ["launcher.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ZAP_ENGINE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
