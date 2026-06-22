import sys
import os
from pathlib import Path

block_cipher = None

sys.setrecursionlimit(5000)

import litellm
litellm_dir = Path(litellm.__file__).parent

def collect_litellm_datas():
    datas = []
    for item in litellm_dir.rglob('*.json'):
        relative_path = item.relative_to(litellm_dir)
        dest_dir = str(relative_path.parent)
        if dest_dir == '.':
            dest_dir = 'litellm'
        else:
            dest_dir = f'litellm/{dest_dir}'
        datas.append((str(item), dest_dir))
    return datas

litellm_datas = collect_litellm_datas()

a = Analysis(
    ['backend/start_server.py'],
    pathex=['backend'],
    binaries=[],
    datas=[
        ('backend/desktopclaw/templates', 'desktopclaw/templates'),
        ('backend/desktopclaw/skills', 'desktopclaw/skills'),
        *litellm_datas,
    ],
    hiddenimports=[
        'desktopclaw',
        'desktopclaw.agent',
        'desktopclaw.api',
        'desktopclaw.bus',
        'desktopclaw.channels',
        'desktopclaw.cli',
        'desktopclaw.config',
        'desktopclaw.cron',
        'desktopclaw.heartbeat',
        'desktopclaw.providers',
        'desktopclaw.session',
        'litellm',
        'litellm.utils',
        'litellm.proxy',
        'litellm.containers',
        'litellm.litellm_core_utils',
    ],
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
    [],
    exclude_binaries=True,
    name='desktopclaw',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='desktopclaw',
)
