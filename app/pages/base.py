"""Sahifalar uchun umumiy asos — bir xil sarlavha va tuzilma."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QScrollArea, QVBoxLayout, QWidget,
)


class Page(QWidget):
    """Har bir modul sahifasi shundan meros oladi.

    Yuqorida sarlavha + subtitr, pastda scroll qilinadigan tarkib maydoni.
    """

    def __init__(self, title: str, subtitle: str, accent: str, parent=None):
        super().__init__(parent)
        self.accent = accent

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 20)
        root.setSpacing(6)

        head = QLabel(title)
        head.setObjectName("PageTitle")
        bar = QLabel()
        bar.setFixedSize(46, 4)
        bar.setStyleSheet(f"background: {accent}; border-radius: 2px;")
        sub = QLabel(subtitle)
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)

        root.addWidget(head)
        root.addWidget(bar)
        root.addSpacing(2)
        root.addWidget(sub)
        root.addSpacing(14)

        # scroll qilinadigan tarkib
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 8, 8)
        self.body_layout.setSpacing(16)
        self.body_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self.body)
        root.addWidget(scroll, 1)

    def add(self, widget: QWidget) -> QWidget:
        self.body_layout.addWidget(widget)
        return widget

    def add_layout(self, layout):
        self.body_layout.addLayout(layout)
        return layout
