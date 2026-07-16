"""
AIDA — sozlamalar (persistence)
===============================
QSettings orqali diskda saqlanadigan sozlamalar: tema, Claude API kaliti,
standart papka, oxirgi fayllar, oyna holati.

macOS: ~/Library/Preferences/uz.erkinjon.AIDA.plist
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

_S = QSettings("uz.erkinjon", "AIDA")
MAX_RECENT = 8


def _get(key: str, default=None):
    return _S.value(key, default)


def _set(key: str, value):
    _S.setValue(key, value)


# ---- Tema ----
def theme() -> str:
    return str(_get("theme", "dark"))


def set_theme(value: str):
    _set("theme", value)


# ---- Claude API kaliti ----
def api_key() -> str:
    return str(_get("api_key", "") or "")


def set_api_key(value: str):
    _set("api_key", value or "")


# ---- Standart saqlash papkasi ----
def output_dir() -> str:
    import os
    return str(_get("output_dir", os.path.expanduser("~/Desktop")))


def set_output_dir(value: str):
    _set("output_dir", value)


# ---- Oxirgi ochilgan fayllar ----
def recent_files() -> list[str]:
    import os
    v = _get("recent_files", [])
    if isinstance(v, str):
        v = [v]
    return [p for p in (v or []) if p and os.path.exists(p)]


def add_recent(path: str):
    files = recent_files()
    if path in files:
        files.remove(path)
    files.insert(0, path)
    _set("recent_files", files[:MAX_RECENT])


def clear_recent():
    _set("recent_files", [])


# ---- Oyna holati ----
def window_geometry():
    return _get("window_geometry")


def set_window_geometry(geom):
    _set("window_geometry", geom)
