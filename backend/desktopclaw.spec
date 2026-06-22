# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

litellm_data = collect_data_files('litellm')

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('desktopclaw/templates', 'desktopclaw/templates'), ('desktopclaw/skills', 'desktopclaw/skills')] + litellm_data,
    hiddenimports=['litellm.litellm_core_utils.tokenizers', 'litellm.litellm_core_utils.get_model_cost_map'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_fix_permissions.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='desktopclaw',
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
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='desktopclaw',
)
