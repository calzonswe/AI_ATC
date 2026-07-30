# -*- mode: python ; coding: utf-8 -*-
#
# OpenATC Client — PyInstaller spec file
#
# Build a single-file Windows .exe (or macOS/Unix binary) from the
# PySide6 GUI client.
#
# Usage:
#   pyinstaller build_exe.spec
#

import os
import sys
from pathlib import Path

# Ensure the src directory is on the path so that `gui` package imports work
SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

block_cipher = None

a = Analysis(
    ["src/main_gui.py"],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PySide6 internals
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtWebSockets",
        "PySide6.QtMultimedia",
        # Audio
        "sounddevice",
        "numpy",
        "numpy.core._multiarray_umath",
        "numpy.core.multiarray",
        # GUI package (relative import from main_gui.py)
        "gui",
        "gui.app",
        "gui.state",
        "gui.settings_store",
        "gui.audio_manager",
        "gui.audio_widget",
        "gui.ptt_manager",
        "gui.websocket_bridge",
        "gui.connection_widget",
        "gui.flight_info_widget",
        "gui.radio_widget",
        "gui.simbrief_client",
        "gui.simbrief_widget",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude what we don't need to reduce size
        "tkinter",
        "matplotlib",
        "scipy",
        "PIL",
        "cv2",
        "pandas",
        "sympy",
        "IPython",
        "notebook",
        "jupyter",
        "setuptools",
        "pip",
    ],
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
    name="OpenATC_Client",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # No console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="client_icon.ico" if os.path.exists("client_icon.ico") else None,
)

# Create the COLLECT for one-folder mode (dist/OpenATC_Client/)
# The single .exe is inside this folder.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OpenATC_Client",
)
