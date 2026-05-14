# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Collect all Textual assets (CSS themes, etc.)
textual_datas, textual_binaries, textual_hiddenimports = collect_all("textual")

# Collect rich assets
rich_datas, rich_binaries, rich_hiddenimports = collect_all("rich")

a = Analysis(
    ["phpgen_version82.py"],
    pathex=[],
    binaries=textual_binaries + rich_binaries,
    datas=textual_datas + rich_datas,
    hiddenimports=(
        textual_hiddenimports
        + rich_hiddenimports
        + [
            "byteplussdkarkruntime",
            "dotenv",
            "requests",
            "zipfile",
            "queue",
            "threading",
        ]
    ),
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
    name="PHP Site Generator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,          # Terminal app — must stay True
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.icns" if sys.platform == "darwin" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PHP Site Generator",
)

# macOS .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PHP Site Generator.app",
        icon="icon.icns",
        bundle_identifier="com.phpgen.sitegenerator",
        info_plist={
            "NSPrincipalClass": "NSApplication",
            "NSAppleScriptEnabled": False,
            "CFBundleDocumentTypes": [],
            "LSUIElement": False,          # Show in Dock
            "NSRequiresAquaSystemAppearance": False,
        },
    )
