# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path


block_cipher = None
spec_dir = Path(SPECPATH)
project_root = spec_dir.parent
source_root = project_root / "src"

hiddenimports = collect_submodules("pystray")

tray = Analysis(
    [str(spec_dir / "tray_entry.py")],
    pathex=[str(project_root), str(source_root)],
    binaries=[],
    datas=[],
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

tray_pyz = PYZ(tray.pure, tray.zipped_data, cipher=block_cipher)

tray_exe = EXE(
    tray_pyz,
    tray.scripts,
    tray.binaries,
    tray.zipfiles,
    tray.datas,
    [],
    name='WiiM Scrobbler',
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

cli = Analysis(
    [str(spec_dir / "cli_entry.py")],
    pathex=[str(project_root), str(source_root)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

cli_pyz = PYZ(cli.pure, cli.zipped_data, cipher=block_cipher)

cli_exe = EXE(
    cli_pyz,
    cli.scripts,
    cli.binaries,
    cli.zipfiles,
    cli.datas,
    [],
    name='WiiM Scrobbler CLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
