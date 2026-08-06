# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]
hiddenimports = []
for package in ('flask_socketio', 'socketio', 'engineio', 'geventwebsocket', 'asyncio_gevent'):
    hiddenimports += collect_submodules(package, filter=lambda name: '.tests' not in name)

for distribution in ('Flask', 'Flask-SocketIO', 'python-socketio', 'gevent', 'gevent-websocket', 'asyncio-gevent', 'regex'):
    datas += copy_metadata(distribution)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TourniRC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='TourniRC',
)
