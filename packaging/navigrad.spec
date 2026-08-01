# -*- mode: python ; coding: utf-8 -*-
# Build with (from repo root): .venv\Scripts\pyinstaller.exe packaging\navigrad.spec
#
# onedir (not onefile): the real distributable is the Inno Setup installer
# (packaging/installer.iss), not this raw PyInstaller output -- onedir gives
# a stable sys._MEIPASS (same folder as the exe, no per-launch extraction)
# which app/main.py's frozen-mode BASE_DIR resolution depends on, plus
# faster cold start and easier field debugging.
#
# No hiddenimports were needed in practice -- pyinstaller-hooks-contrib
# already ships hooks for pywin32 (pulled in by mcp), pythonnet/clr_loader
# (pulled in by pywebview), pdfminer/pypdfium2, python-docx, and lxml.

import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

a = Analysis(
    [os.path.join(REPO_ROOT, "app", "desktop.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[
        (os.path.join(REPO_ROOT, "public"), "public"),
        (os.path.join(REPO_ROOT, "USER_MANUAL.md"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    name="Navigrad",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(REPO_ROOT, "packaging", "icon.ico")],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Navigrad",
)
