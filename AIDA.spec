# -*- mode: python ; coding: utf-8 -*-
"""
AIDA — macOS .app paketlash konfiguratsiyasi.
Qurish:  pyinstaller AIDA.spec --noconfirm
Natija:  dist/AIDA.app
"""

import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files

# --- Platformaga mos ikona ---
if sys.platform == "darwin":
    ICON = "app/assets/icon.icns"
elif sys.platform == "win32":
    ICON = "app/assets/icon.ico"   # CI'da icon.png dan yaratiladi
else:
    ICON = None                     # Linux: binary ikonasi shart emas

# --- Ma'lumot fayllari ---
datas = [
    ("app/assets/icon.png", "app/assets"),
]
if sys.platform == "darwin":
    datas.append(("app/assets/icon.icns", "app/assets"))
binaries = []
# backend modullar top-level import qilinadi — aniq ko'rsatamiz
hiddenimports = ["aida_bioscience", "aida_genomics", "aida_export"]

# Biopython ma'lumot fayllari (substitution matritsalari va h.k.)
for pkg in ("Bio",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# reportlab shriftlari/ranglari
datas += collect_data_files("reportlab")


a = Analysis(
    ["run_app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # kerak bo'lmagan og'ir/GUI Qt modullari — hajmni kamaytiradi
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml",
        "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "tkinter", "PyQt5", "PyQt6",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AIDA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # windowed — terminalsiz
    disable_windowed_traceback=False,
    argv_emulation=(sys.platform == "darwin"),  # macOS: fayllarni ilovaga tashlash
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AIDA",
)

# macOS uchun .app bundle (Windows/Linux'da COLLECT papkasi yakuniy natija)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="AIDA.app",
        icon=ICON,
        bundle_identifier="uz.erkinjon.medical",
        version="1.0.0",
        info_plist={
            "CFBundleName": "AIDA",
            "CFBundleDisplayName": "AIDA",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.medical",
            "NSHumanReadableCopyright": "© 2026 Erkinjon. Faqat ma'lumot uchun — tashxis qo'ymaydi.",
            # ANTHROPIC_API_KEY muhitdan o'qiladi; internet uchun ruxsat:
            "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
        },
    )
