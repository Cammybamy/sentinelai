# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for SentinelAI.
#
# Build command:
#   Windows:  pyinstaller sentinelai.spec
#   macOS:    pyinstaller sentinelai.spec
#
# Output:
#   Windows:  dist\SentinelAI\SentinelAI.exe   (one-folder build)
#   macOS:    dist/SentinelAI.app               (app bundle)
#
# To create a single-file .exe on Windows, set onefile=True below.
# One-folder is preferred because startup is ~3x faster (no temp extraction).

import sys
from pathlib import Path

SRC = Path('src/sentinelai')

# All YAML rule files must be bundled as data.
rule_datas = [
    (str(SRC / 'config' / 'rules'), 'sentinelai/config/rules'),
]

a = Analysis(
    ['src/sentinelai/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=rule_datas,
    hiddenimports=[
        'sentinelai',
        'sentinelai.core',
        'sentinelai.core.analyzer',
        'sentinelai.core.rule_engine',
        'sentinelai.core.llm_client',
        'sentinelai.core.models',
        'sentinelai.monitors',
        'sentinelai.monitors.clipboard',
        'sentinelai.storage',
        'sentinelai.storage.audit_log',
        'sentinelai.storage.db',
        'sentinelai.ui',
        'sentinelai.ui.alert_dialog',
        'sentinelai.ui.dashboard',
        'sentinelai.ui.tray',
        'sentinelai.config',
        'sentinelai.config.settings',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'yaml',
        'pyperclip',
        'ollama',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy'],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SentinelAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # No terminal window on Windows.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Uncomment when icon file is added.
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SentinelAI',
)

# macOS: wrap in an .app bundle.
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='SentinelAI.app',
        # icon='assets/icon.icns',
        bundle_identifier='co.drgnstudios.sentinelai',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': True,
            'LSUIElement': True,          # Background app — no Dock icon.
            'CFBundleShortVersionString': '0.1.0',
            'NSClipboardUsageDescription':
                'SentinelAI monitors clipboard content to detect dangerous commands.',
        },
    )
