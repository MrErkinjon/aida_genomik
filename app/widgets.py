"""
AIDA Desktop — qayta ishlatiladigan UI komponentlar
==================================================
Card, StatTile, ChartView, jadval quruvchi va yordamchilar.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .theme import COLORS


def add_shadow(widget: QWidget, blur: int = 28, y: int = 8, alpha: int = 120):
    """Soya effekti — ATAYLAB o'chirilgan (performance).

    QGraphicsDropShadowEffect har repaint/scroll/resize'da qayta hisoblanadi
    va ko'p bo'lsa (o'nlab kartochka) interfeys qotib qoladi. Chuqurlik hissi
    endi QSS chegara + fon farqi orqali beriladi (tez va toza tekis dizayn).
    """
    return  # no-op — freeze'ning oldini olish uchun


class Card(QFrame):
    """Umumiy kartochka konteyner — sarlavha (ixtiyoriy) + tarkib."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        add_shadow(self)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(18, 16, 18, 18)
        self._lay.setSpacing(12)
        if title:
            t = QLabel(title)
            t.setObjectName("SectionTitle")
            self._lay.addWidget(t)

    def add(self, widget: QWidget) -> QWidget:
        self._lay.addWidget(widget)
        return widget

    def add_layout(self, layout):
        self._lay.addLayout(layout)
        return layout


class StatTile(QFrame):
    """Bitta ko'rsatkich — katta qiymat + tag."""

    def __init__(self, value: str, label: str, color: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("StatTile")
        self.setMinimumWidth(130)
        add_shadow(self, blur=18, y=5, alpha=90)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(2)
        self.value = QLabel(value)
        self.value.setObjectName("StatValue")
        if color:
            self.value.setStyleSheet(f"color: {color};")
        self.label = QLabel(label)
        self.label.setObjectName("StatLabel")
        lay.addWidget(self.value)
        lay.addWidget(self.label)

    def set_value(self, value: str):
        self.value.setText(value)


class ChartView(QFrame):
    """Matplotlib grafigini (PNG bytes) ko'rsatuvchi boshqariladigan panel.

    Sarlavha yonida boshqaruv tugmalari:
      ⤢ kattalashtirish (zoom/pan dialog) · 💾 saqlash · 📋 nusxalash
    Rasm ustiga bosib ham kattalashtirish mumkin.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        add_shadow(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # --- sarlavha qatori + boshqaruv tugmalari ---
        header = QHBoxLayout()
        self._title = QLabel("")
        self._title.setObjectName("SectionTitle")
        header.addWidget(self._title, 1)
        self._btns: list[QPushButton] = []
        for glyph, tip, slot in (
            ("⤢", "Kattalashtirish (zoom / pan)", self._enlarge),
            ("💾", "PNG saqlash", self._save),
            ("📋", "Nusxalash (clipboard)", self._copy),
        ):
            b = QPushButton(glyph)
            b.setObjectName("ChartTool")
            b.setToolTip(tip)
            b.setFixedSize(30, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.setEnabled(False)
            b.clicked.connect(slot)
            header.addWidget(b)
            self._btns.append(b)
        lay.addLayout(header)

        # --- rasm ---
        self._img = _ClickLabel("Grafik shu yerda ko'rinadi")
        self._img.setObjectName("Muted")
        self._img.setAlignment(Qt.AlignCenter)
        self._img.setMinimumHeight(260)
        self._img.setStyleSheet(
            "background: #ffffff; border-radius: 10px; padding: 6px; color: #64748b;")
        self._img.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._img.clicked.connect(self._enlarge)
        lay.addWidget(self._img, 1)

        self._caption = QLabel("")
        self._caption.setObjectName("Dim")
        self._caption.setWordWrap(True)
        self._caption.hide()
        lay.addWidget(self._caption)

        self._pixmap: QPixmap | None = None
        self._png: bytes | None = None
        self._chart_title = "grafik"
        self._last_w = 0

    def show_chart(self, png: bytes, title: str = "", caption: str = ""):
        pm = QPixmap()
        pm.loadFromData(png, "PNG")
        self._pixmap = pm
        self._png = png
        self._last_w = 0  # yangi grafik — qayta masshtablansin
        self._chart_title = title or "grafik"
        self._img.setCursor(Qt.PointingHandCursor)
        for b in self._btns:
            b.setEnabled(True)
        self._rescale()
        self._title.setText(title)
        if caption:
            self._caption.setText(caption)
            self._caption.show()
        else:
            self._caption.hide()

    def clear(self, message: str = "Grafik shu yerda ko'rinadi"):
        self._pixmap = None
        self._png = None
        self._img.setPixmap(QPixmap())
        self._img.setText(message)
        self._img.setCursor(Qt.ArrowCursor)
        self._caption.hide()
        self._title.setText("")
        for b in self._btns:
            b.setEnabled(False)

    # --- boshqaruv ---
    def _enlarge(self):
        if self._pixmap and not self._pixmap.isNull():
            ChartDialog(self._pixmap, self._png, self._chart_title, self).exec()

    def _save(self):
        if not self._png:
            return
        safe = "".join(c if c.isalnum() else "_" for c in self._chart_title)[:40] or "grafik"
        path, _ = QFileDialog.getSaveFileName(self, "Grafikni saqlash", f"{safe}.png",
                                              "PNG rasm (*.png)")
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            with open(path, "wb") as f:
                f.write(self._png)

    def _copy(self):
        if self._pixmap and not self._pixmap.isNull():
            QGuiApplication.clipboard().setPixmap(self._pixmap)

    def _rescale(self):
        if self._pixmap and not self._pixmap.isNull():
            w = max(self._img.width() - 12, 200)
            # kenglik deyarli o'zgarmasa qayta masshtablamaymiz (resize'da tejamkorlik)
            if abs(w - self._last_w) < 4:
                return
            self._last_w = w
            self._img.setPixmap(self._pixmap.scaledToWidth(w, Qt.SmoothTransformation))
            self._img.setText("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


class _ClickLabel(QLabel):
    """Bosilganda signal chiqaradigan QLabel."""

    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pixmap() and not self.pixmap().isNull():
            self.clicked.emit()
        super().mousePressEvent(event)


class ChartDialog(QDialog):
    """Grafikni to'liq oynada zoom/pan bilan ko'rish + saqlash."""

    def __init__(self, pixmap: QPixmap, png: bytes | None, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1000, 720)
        self._pixmap = pixmap
        self._png = png
        self._title = title
        self._zoom = 1.0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        # boshqaruv paneli
        bar = QHBoxLayout()
        for glyph, tip, slot in (
            ("−", "Kichraytirish", lambda: self._scale(1 / 1.25)),
            ("+", "Kattalashtirish", lambda: self._scale(1.25)),
            ("⤢", "Oynaga moslash", self._fit),
            ("1:1", "Asl o'lcham", self._reset),
        ):
            b = QPushButton(glyph)
            b.setObjectName("Ghost")
            b.setFixedHeight(30)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch(1)
        self._zoom_lbl = QLabel("100%")
        self._zoom_lbl.setObjectName("Dim")
        bar.addWidget(self._zoom_lbl)
        save = QPushButton("💾 Saqlash")
        save.setObjectName("Primary")
        save.setFixedHeight(30)
        save.clicked.connect(self._save)
        bar.addWidget(save)
        lay.addLayout(bar)

        # zoom qilinadigan rasm (scroll ichida)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignCenter)
        self._scroll.setStyleSheet("background: #ffffff; border-radius: 8px;")
        self._canvas = QLabel()
        self._canvas.setAlignment(Qt.AlignCenter)
        self._scroll.setWidget(self._canvas)
        lay.addWidget(self._scroll, 1)

        self._apply()

    def showEvent(self, event):
        super().showEvent(event)
        self._fit()

    def _apply(self):
        w = max(int(self._pixmap.width() * self._zoom), 1)
        self._canvas.setPixmap(self._pixmap.scaledToWidth(w, Qt.SmoothTransformation))
        self._canvas.resize(self._canvas.pixmap().size())
        self._zoom_lbl.setText(f"{int(self._zoom * 100)}%")

    def _scale(self, factor: float):
        self._zoom = max(0.1, min(self._zoom * factor, 8.0))
        self._apply()

    def _fit(self):
        avail = self._scroll.viewport().width() - 20
        if self._pixmap.width():
            self._zoom = max(0.1, avail / self._pixmap.width())
        self._apply()

    def _reset(self):
        self._zoom = 1.0
        self._apply()

    def wheelEvent(self, event):
        self._scale(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)

    def _save(self):
        if not self._png:
            return
        safe = "".join(c if c.isalnum() else "_" for c in self._title)[:40] or "grafik"
        path, _ = QFileDialog.getSaveFileName(self, "Grafikni saqlash", f"{safe}.png",
                                              "PNG rasm (*.png)")
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            with open(path, "wb") as f:
                f.write(self._png)


def make_table(data, headers: list[str] | None = None) -> QTableWidget:
    """dict, list yoki pandas DataFrame'dan chiroyli jadval yasaydi."""
    # pandas DataFrame -> sarlavha + qatorlar
    if hasattr(data, "columns") and hasattr(data, "itertuples"):
        headers = headers or [str(c) for c in data.columns]
        rows = [[_fmt(v) for v in row] for row in data.itertuples(index=False, name=None)]
        return _build_table(headers, rows)

    if isinstance(data, dict):
        headers = headers or ["Ko'rsatkich", "Qiymat"]
        rows = [[str(k), _fmt(v)] for k, v in data.items()]
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        headers = headers or list(data[0].keys())
        rows = [[_fmt(r.get(h, "")) for h in headers] for r in data]
    elif isinstance(data, list):
        headers = headers or [f"Ustun {i+1}" for i in range(len(data[0]))]
        rows = [[_fmt(v) for v in r] for r in data]
    else:
        headers, rows = headers or [], []

    return _build_table(headers, rows)


def _build_table(headers: list[str], rows: list[list]) -> QTableWidget:
    table = QTableWidget(len(rows), len(headers))
    table.setHorizontalHeaderLabels([str(h) for h in headers])
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.setAlternatingRowColors(False)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            item = QTableWidgetItem(str(val))
            if c > 0:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(r, c, item)
    table.setMinimumHeight(min(46 + len(rows) * 34, 460))
    return table


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    return v


def stat_row(*tiles: StatTile) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(12)
    for t in tiles:
        lay.addWidget(t)
    return lay


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"color: {COLORS['border']}; background: {COLORS['border']}; max-height: 1px;")
    return line
