# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],  # Thư mục hiện tại
    binaries=[],
    datas=[
        ('background_music/*', 'background_music'),  # Copy folder nhạc nền
        #('outputs/*', 'outputs'),  # Nếu muốn đóng gói outputs (thường để ngoài)
    ],
    hiddenimports=['pydub', 'requests', 'moviepy', 'PyQt5'],
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
    [],
    a.datas,
    [],
    name='VideoAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Ẩn console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
