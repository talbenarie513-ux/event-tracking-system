# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Event Management System
# Run with: pyinstaller main.spec

import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect all webview data files
webview_datas = collect_data_files('webview')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Frontend files
        ('index.html', '.'),
        ('app.js', '.'),
        # Backend Python files
        ('backend/app.py',                   'backend'),
        ('backend/database.py',              'backend'),
        ('backend/email_notifications.py',   'backend'),
        ('backend/reports.py',               'backend'),
        # Include webview assets
        *webview_datas,
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'webview',
        'webview.platforms.winforms',   # Windows
        'webview.platforms.gtk',        # Linux
        'clr',
        'apscheduler',
        'apscheduler.schedulers.background',
        'apscheduler.triggers.cron',
        'openpyxl',
        'xlsxwriter',
        'werkzeug',
        'jinja2',
        'click',
        'itsdangerous',
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
    name='EventManagementSystem',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # ← no black terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # ← add 'icon.ico' here if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EventManagementSystem',
)