"""
AIDA — Yangilanishlar oynasi
============================
Barcha release'larni (o'zgarishlar, yangi funksiyalar, tuzatilgan buglar)
ko'rsatadi. Ma'lumot GitHub Releases API'dan worker oqimida olinadi.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QTextBrowser, QVBoxLayout, QWidget,
)

from . import updater
from .theme import COLORS
from .version import RELEASES_PAGE, __version__
from .widgets import Card, add_shadow
from .workers import TaskRunner


class ReleasesDialog(QDialog):
    def __init__(self, parent=None, preloaded: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("AIDA — Yangilanishlar")
        self.setModal(True)
        self.resize(720, 640)
        self._runner = TaskRunner()

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        # sarlavha
        head = QHBoxLayout()
        title = QLabel("Yangilanishlar tarixi")
        title.setObjectName("PageTitle")
        head.addWidget(title, 1)
        self.ver_lbl = QLabel(f"Joriy: v{__version__}")
        self.ver_lbl.setObjectName("Muted")
        head.addWidget(self.ver_lbl)
        root.addLayout(head)

        # update banner (kerak bo'lsa ko'rinadi)
        self.banner = QFrame()
        self.banner.setObjectName("Card")
        self.banner.hide()
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(14, 10, 14, 10)
        self.banner_lbl = QLabel()
        self.banner_lbl.setWordWrap(True)
        bl.addWidget(self.banner_lbl, 1)
        self.download_btn = QPushButton("⬇  Yuklab olish")
        self.download_btn.setObjectName("Primary")
        self.download_btn.clicked.connect(self._download_latest)
        bl.addWidget(self.download_btn)
        root.addWidget(self.banner)

        # kontent (scroll)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 8, 0)
        self.body_layout.setSpacing(12)
        self.body_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)

        # pastki tugmalar
        foot = QHBoxLayout()
        self.status = QLabel("Yuklanmoqda…")
        self.status.setObjectName("Dim")
        foot.addWidget(self.status, 1)
        web_btn = QPushButton("GitHub'da ochish")
        web_btn.setObjectName("Ghost")
        web_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(RELEASES_PAGE)))
        foot.addWidget(web_btn)
        close_btn = QPushButton("Yopish")
        close_btn.setObjectName("Ghost")
        close_btn.clicked.connect(self.accept)
        foot.addWidget(close_btn)
        root.addLayout(foot)

        self._latest_url = RELEASES_PAGE
        if preloaded is not None:
            self._render(preloaded)
        else:
            self._load()

    # ------------------------------------------------------------------
    def _load(self):
        self.status.setText("GitHub'dan yuklanmoqda…")
        self._runner.run(updater.check_for_update, on_done=self._render, on_error=self._error)

    def _error(self, msg: str):
        self.status.setText("Yuklab bo'lmadi.")
        _clear(self.body_layout)
        lbl = QLabel(f"Yangilanishlarni yuklab bo'lmadi.\n\n{msg}")
        lbl.setObjectName("Muted")
        lbl.setWordWrap(True)
        self.body_layout.addWidget(lbl)

    def _render(self, data: dict):
        _clear(self.body_layout)
        releases = data.get("releases", [])
        if data.get("update_available") and data.get("latest"):
            lt = data["latest"]
            self._latest_url = lt.get("asset_url") or lt.get("url") or RELEASES_PAGE
            self.banner_lbl.setText(
                f"<b style='color:{COLORS['success']}'>Yangi versiya mavjud: "
                f"{lt['tag']}</b> — joriy v{__version__}. O'zgarishlar quyida.")
            self.banner.show()
            self.status.setText(f"{len(releases)} ta release · yangilanish bor")
        elif releases:
            self.status.setText(f"{len(releases)} ta release · eng so'nggi versiyadasiz ✓")
        else:
            self.status.setText("Hali rasmiy release chiqmagan.")
            info = QLabel(
                "Hali birorta release e'lon qilinmagan.\n\n"
                "Release chiqarish uchun teg push qiling:\n"
                "    git tag v1.0.0 && git push origin v1.0.0\n\n"
                "GitHub Actions avtomatik ravishda Windows/macOS/Linux uchun "
                "ilova yasab, bu yerda ko'rsatiladigan Release yaratadi.")
            info.setObjectName("Muted")
            info.setWordWrap(True)
            self.body_layout.addWidget(info)
            return

        for rel in releases:
            self.body_layout.addWidget(_release_card(rel))

    def _download_latest(self):
        QDesktopServices.openUrl(QUrl(self._latest_url))


def _release_card(rel: dict) -> Card:
    tag = rel.get("tag", "")
    name = rel.get("name", tag)
    date = rel.get("date", "")
    pre = "  ·  pre-release" if rel.get("prerelease") else ""
    card = Card()
    header = QLabel(f"<b>{name}</b>  <span style='color:{COLORS['text_dim']}'>"
                    f"({tag}{pre})  ·  {date}</span>")
    header.setTextFormat(Qt.RichText)
    card.add(header)

    notes = QTextBrowser()
    notes.setOpenExternalLinks(True)
    notes.setMarkdown(rel.get("body", ""))
    notes.setStyleSheet(
        f"background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; "
        f"border-radius: 8px; padding: 6px;")
    notes.setMinimumHeight(90)
    notes.setMaximumHeight(260)
    card.add(notes)

    if rel.get("assets"):
        row = QHBoxLayout()
        for aname, aurl in rel["assets"]:
            b = QPushButton(f"⬇ {aname}")
            b.setObjectName("Ghost")
            b.clicked.connect(lambda _=False, u=aurl: QDesktopServices.openUrl(QUrl(u)))
            row.addWidget(b)
        row.addStretch(1)
        card.add_layout(row)
    return card


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
