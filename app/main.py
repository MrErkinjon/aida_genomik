"""
AIDA Desktop — kirish nuqtasi
=============================
Asosiy oyna: chapda sidebar navigatsiya, o'ngda sahifalar (QStackedWidget).

Ishga tushirish:
    python -m app.main
yoki
    ./run.sh
"""

from __future__ import annotations

import sys

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from . import settings, updater
from .releases_dialog import ReleasesDialog
from .settings_dialog import SettingsDialog
from .theme import COLORS, build_qss
from .version import __version__
from .workers import TaskRunner

# Navigatsiya: (kalit, belgi, nom, tavsif)
NAV = [
    ("sequence", "🧬", "Sekvensiya", "DNK/RNK tahlili"),
    ("population", "👥", "Populyatsiya", "Genetika va statistika"),
    ("genomics", "📊", "Genomika", "GWAS va variantlar"),
    ("assoc", "🗺️", "Assotsiatsiya", "SSR marker-trait xaritalash"),
    ("anova", "📈", "ANOVA / RPC", "RIL trait ANOVA tahlili"),
    ("explain", "💬", "Tushuntirish", "Claude bilan izoh"),
    ("export", "📄", "Hisobot", "Excel · PDF · Word"),
]


class PlaceholderPage(QWidget):
    """Hali qurilmagan sahifa uchun vaqtinchalik o'rinbosar."""

    def __init__(self, name: str):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        t = QLabel(f"{name}")
        t.setObjectName("PageTitle")
        t.setAlignment(Qt.AlignCenter)
        s = QLabel("Bu modul keyingi bosqichda quriladi.")
        s.setObjectName("Muted")
        s.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        lay.addWidget(s)


class Sidebar(QWidget):
    def __init__(self, on_select, on_updates=None, on_settings=None):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(232)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 24, 16, 20)
        lay.setSpacing(6)

        # Brend
        brand = QLabel("AIDA")
        brand.setObjectName("Brand")
        sub = QLabel("GENOMIKA STUDIYASI")
        sub.setObjectName("BrandSub")
        lay.addWidget(brand)
        lay.addWidget(sub)
        lay.addSpacing(22)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (key, icon, name, desc) in enumerate(NAV):
            btn = QPushButton(f"  {icon}   {name}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setToolTip(f"{desc}   (⌘{i + 1})")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, idx=i: on_select(idx))
            self.group.addButton(btn, i)
            lay.addWidget(btn)

        lay.addStretch(1)

        # Yangilanishlar tugmasi
        settings_btn = QPushButton("  ⚙   Sozlamalar")
        settings_btn.setObjectName("NavButton")
        settings_btn.setCursor(Qt.PointingHandCursor)
        if on_settings:
            settings_btn.clicked.connect(on_settings)
        lay.addWidget(settings_btn)

        self.update_btn = QPushButton("  ⬆   Yangilanishlar")
        self.update_btn.setObjectName("NavButton")
        self.update_btn.setCursor(Qt.PointingHandCursor)
        if on_updates:
            self.update_btn.clicked.connect(on_updates)
        lay.addWidget(self.update_btn)

        self.version_lbl = QLabel(f"AIDA v{__version__}")
        self.version_lbl.setObjectName("Dim")
        lay.addWidget(self.version_lbl)

        foot = QLabel("Faqat ma'lumot uchun.\nTashxis qo'ymaydi.")
        foot.setObjectName("Dim")
        lay.addWidget(foot)

    def select(self, idx: int):
        self.group.button(idx).setChecked(True)

    def set_update_available(self, tag: str):
        """Yangilanish topilganda tugmani ajratib ko'rsatadi."""
        self.update_btn.setText(f"  ⬆   Yangilanish bor: {tag}")
        self.update_btn.setStyleSheet(
            f"QPushButton#NavButton {{ color: {COLORS['success']}; "
            f"background-color: rgba(16,185,129,0.12); font-weight: 700; }}")
        self.version_lbl.setText(f"AIDA v{__version__} — yangi: {tag}")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("AIDA — Genomika studiyasi")
        self.resize(1240, 820)
        self.setMinimumSize(1040, 680)
        self.setAcceptDrops(True)   # faylni oynaga sudrab tashlab yuklash

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        self.sidebar = Sidebar(self._go, self._open_releases, self._open_settings)
        root.addWidget(self.sidebar)
        root.addWidget(self.stack, 1)

        self._pages: dict[int, QWidget] = {}
        self._build_pages()
        self.sidebar.select(0)
        self._go(0)
        self._add_shortcuts()
        # oyna holatini tiklash (yo'q bo'lsa markazga)
        geom = settings.window_geometry()
        if geom is not None:
            self.restoreGeometry(geom)
        else:
            self._center()

        # avto-update: ishga tushganda fon'da tekshiramiz (UI qotmaydi)
        self._update_data: dict | None = None
        self._update_runner = TaskRunner()
        self._update_runner.run(
            updater.check_for_update, timeout=6,
            on_done=self._on_update_check, on_error=lambda e: None)

    def closeEvent(self, event):
        """Yopilishdan oldin oyna holatini saqlaydi va fon oqimini to'xtatadi."""
        settings.set_window_geometry(self.saveGeometry())
        self._update_runner.wait(2000)
        super().closeEvent(event)

    # ---- Drag & drop: faylni joriy sahifaga yuklaydi ----
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        page = self._pages.get(self.stack.currentIndex())
        if hasattr(page, "load_path"):
            page.load_path(path)
        else:
            # faylni qabul qiladigan birinchi sahifaga yo'naltiramiz
            for i, pg in self._pages.items():
                if hasattr(pg, "load_path"):
                    self._select(i)
                    pg.load_path(path)
                    break

    def _open_settings(self):
        SettingsDialog(self, on_theme_changed=self._on_theme_changed).exec()

    def _on_theme_changed(self, name: str):
        # QSS qayta qo'llandi; sidebar tanlangan holatini yangilaymiz
        self.sidebar.select(self.stack.currentIndex())

    def _add_shortcuts(self):
        """⌘1…⌘5 — sahifalar orasida tez almashish."""
        for i in range(len(NAV)):
            sc = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            sc.activated.connect(lambda idx=i: self._select(idx))
        # ⌘W / ⌘Q — oynani yopish
        QShortcut(QKeySequence.Close, self).activated.connect(self.close)

    def _center(self):
        """Oynani ekran markaziga joylashtiradi."""
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2,
                      geo.center().y() - self.height() // 2)

    def _select(self, idx: int):
        """Sidebar tugmasini ham yangilab sahifaga o'tadi."""
        self.sidebar.select(idx)
        self._go(idx)

    def _build_pages(self):
        """Sahifalarni kalit bo'yicha yaratadi. Import xatosi bo'lsa o'rinbosar."""
        def load(module, cls):
            mod = __import__(f"app.pages.{module}", fromlist=[cls])
            return getattr(mod, cls)

        registry = {
            "sequence": ("sequence_page", "SequencePage"),
            "population": ("population_page", "PopulationPage"),
            "genomics": ("genomics_page", "GenomicsPage"),
            "assoc": ("assoc_page", "AssocPage"),
            "anova": ("anova_page", "AnovaPage"),
            "explain": ("explain_page", "ExplainPage"),
            "export": ("export_page", "ExportPage"),
        }
        for i, (key, icon, name, desc) in enumerate(NAV):
            page = None
            if key in registry:
                try:
                    page = load(*registry[key])()
                except Exception as e:  # noqa: BLE001
                    print(f"[{key}] sahifa yuklanmadi: {e}")
            self._pages[i] = page or PlaceholderPage(name)
            self.stack.addWidget(self._pages[i])

    def _go(self, idx: int):
        self.stack.setCurrentIndex(idx)

    def _on_update_check(self, data: dict):
        """Fon tekshiruvi natijasi — yangilanish bo'lsa sidebar'ni belgilaydi."""
        self._update_data = data
        if data.get("update_available") and data.get("latest"):
            self.sidebar.set_update_available(data["latest"]["tag"])

    def _open_releases(self):
        """Yangilanishlar oynasini ochadi (tekshiruv natijasi tayyor bo'lsa qayta ishlatadi)."""
        ReleasesDialog(self, preloaded=self._update_data).exec()


def _icon_path() -> str | None:
    p = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    return p if os.path.exists(p) else None


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AIDA")
    app.setApplicationDisplayName("AIDA")
    # saqlangan tema va Claude API kalitini qo'llaymiz
    app.setStyleSheet(build_qss(settings.theme()))
    app.setFont(QFont("SF Pro Text", 10))
    _saved_key = settings.api_key()
    if _saved_key and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = _saved_key

    icon = _icon_path()
    if icon:
        app.setWindowIcon(QIcon(icon))

    win = MainWindow()
    if icon:
        win.setWindowIcon(QIcon(icon))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
