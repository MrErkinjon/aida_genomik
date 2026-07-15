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

from .theme import COLORS, build_qss

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
    def __init__(self, on_select):
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
        foot = QLabel("Faqat ma'lumot uchun.\nTashxis qo'ymaydi.")
        foot.setObjectName("Dim")
        lay.addWidget(foot)

    def select(self, idx: int):
        self.group.button(idx).setChecked(True)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("AIDA — Genomika studiyasi")
        self.resize(1240, 820)
        self.setMinimumSize(1040, 680)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        self.sidebar = Sidebar(self._go)
        root.addWidget(self.sidebar)
        root.addWidget(self.stack, 1)

        self._pages: dict[int, QWidget] = {}
        self._build_pages()
        self.sidebar.select(0)
        self._go(0)
        self._add_shortcuts()
        self._center()

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


def _icon_path() -> str | None:
    p = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    return p if os.path.exists(p) else None


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AIDA")
    app.setApplicationDisplayName("AIDA")
    app.setStyleSheet(build_qss())
    app.setFont(QFont("SF Pro Text", 10))

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
