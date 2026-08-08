# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata

datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]
hiddenimports = [
    'engineio.async_drivers.gevent',
    'geventwebsocket.handler',
]

for distribution in (
    'Flask',
    'Flask-SocketIO',
    'python-socketio',
    'gevent',
    'gevent-websocket',
    'asyncio-gevent',
    'regex',
    'zope.event',
    'zope.interface',
):
    datas += copy_metadata(distribution)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter', 'test', 'unittest'],
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
