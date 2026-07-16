"""AIDA versiya va repozitoriy ma'lumotlari (bir joyda)."""

__version__ = "1.0.0"

# Relizlar va issue'lar public repo'da (kod private repo'da).
# Avto-update va Yangilanishlar oynasi shu public repo API'siga murojaat qiladi.
REPO = "MrErkinjon/aida_genomika_releases"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
API_RELEASES = f"https://api.github.com/repos/{REPO}/releases"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
