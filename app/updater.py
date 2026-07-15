"""
AIDA — avto-update tekshiruvi
=============================
GitHub Releases API orqali yangi versiyani tekshiradi va release
tarixini (o'zgarishlar, tuzatilgan buglar) oladi.

MUHIM: barcha funksiyalar tarmoqqa murojaat qiladi — ularni faqat worker
oqimida chaqiring (TaskRunner), UI qotmasligi uchun.

Xavfsizlik: imzolanmagan ilovani jimgina almashtirmaymiz. Yangilanish
topilsa, foydalanuvchiga xabar beriladi va rasmiy Release sahifasidan
yuklab olishga yo'naltiriladi (sanoat standarti bo'lgan xavfsiz usul).
"""

from __future__ import annotations

import platform

import requests

from .version import API_RELEASES, __version__

_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "AIDA-Updater"}


def parse_version(tag: str) -> tuple[int, int, int]:
    """'v1.2.3' yoki '1.2' -> (1, 2, 3)."""
    tag = (tag or "").lstrip("vV").strip()
    parts: list[int] = []
    for p in tag.split(".")[:3]:
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])  # type: ignore[return-value]


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def _asset_for_platform(assets: list[tuple[str, str]]) -> str | None:
    """Joriy OS uchun mos yuklab olish havolasini tanlaydi."""
    system = platform.system().lower()  # darwin / windows / linux
    key = {"darwin": "macos", "windows": "windows", "linux": "linux"}.get(system, "")
    for name, url in assets:
        if key and key in name.lower():
            return url
    return None


def fetch_releases(timeout: int = 10) -> list[dict]:
    """Barcha release'lar (eng yangisidan boshlab)."""
    r = requests.get(API_RELEASES, headers=_HEADERS, timeout=timeout)
    if r.status_code == 404:
        raise RuntimeError(
            "Repozitoriy topilmadi yoki private. Avto-update va yangilanishlar "
            "ro'yxati ishlashi uchun repo GitHub'da public bo'lishi kerak "
            "(Settings → General → Danger Zone → Change visibility).")
    r.raise_for_status()
    releases = []
    for rel in r.json():
        if rel.get("draft"):
            continue
        assets = [(a.get("name", ""), a.get("browser_download_url", ""))
                  for a in rel.get("assets", [])]
        releases.append({
            "tag": rel.get("tag_name", ""),
            "name": rel.get("name") or rel.get("tag_name", ""),
            "body": rel.get("body") or "_O'zgarishlar tavsifi berilmagan._",
            "date": (rel.get("published_at") or "")[:10],
            "url": rel.get("html_url", ""),
            "prerelease": bool(rel.get("prerelease", False)),
            "assets": assets,
            "asset_url": _asset_for_platform(assets),
        })
    return releases


def check_for_update(timeout: int = 10) -> dict:
    """Joriy versiyani eng yangi release bilan solishtiradi.

    Qaytadi: {current, latest, update_available, releases}
    """
    releases = fetch_releases(timeout)
    stable = [r for r in releases if not r["prerelease"]]
    latest = (stable or releases)[0] if releases else None
    update = bool(latest and is_newer(latest["tag"], __version__))
    return {
        "current": __version__,
        "latest": latest,
        "update_available": update,
        "releases": releases,
    }
