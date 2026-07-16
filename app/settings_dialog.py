"""
AIDA — Sozlamalar oynasi
========================
Claude API kaliti, tema (yorug'/qorong'i), standart saqlash papkasi,
oxirgi fayllarni tozalash. QSettings orqali saqlanadi.
"""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout,
)

from . import settings
from .theme import COLORS, build_qss
from .widgets import Card


class SettingsDialog(QDialog):
    def __init__(self, parent=None, on_theme_changed=None):
        super().__init__(parent)
        self.setWindowTitle("AIDA — Sozlamalar")
        self.setModal(True)
        self.resize(560, 520)
        self._on_theme_changed = on_theme_changed

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        title = QLabel("Sozlamalar")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # --- Claude API kaliti ---
        api_card = Card("Claude API kaliti")
        ah = QLabel("Tushuntirish moduli uchun. Kalit shu qurilmada saqlanadi "
                    "(ANTHROPIC_API_KEY o'rniga). console.anthropic.com dan olinadi.")
        ah.setObjectName("Dim")
        ah.setWordWrap(True)
        api_card.add(ah)
        krow = QHBoxLayout()
        self.api_input = QLineEdit(settings.api_key())
        self.api_input.setEchoMode(QLineEdit.Password)
        self.api_input.setPlaceholderText("sk-ant-...")
        self.show_btn = QPushButton("👁")
        self.show_btn.setObjectName("Ghost")
        self.show_btn.setFixedWidth(44)
        self.show_btn.setCheckable(True)
        self.show_btn.toggled.connect(
            lambda on: self.api_input.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password))
        krow.addWidget(self.api_input, 1)
        krow.addWidget(self.show_btn)
        api_card.add_layout(krow)
        root.addWidget(api_card)

        # --- Tema ---
        theme_card = Card("Ko'rinish (tema)")
        trow = QHBoxLayout()
        trow.addWidget(QLabel("Tema:"))
        self.theme_cb = QComboBox()
        self.theme_cb.addItem("Qorong'i (dark)", "dark")
        self.theme_cb.addItem("Yorug' (light)", "light")
        self.theme_cb.setCurrentIndex(0 if settings.theme() == "dark" else 1)
        trow.addWidget(self.theme_cb)
        trow.addStretch(1)
        theme_card.add_layout(trow)
        root.addWidget(theme_card)

        # --- Standart papka ---
        dir_card = Card("Standart saqlash papkasi")
        drow = QHBoxLayout()
        self.dir_lbl = QLabel(settings.output_dir())
        self.dir_lbl.setObjectName("Muted")
        dbtn = QPushButton("Tanlash")
        dbtn.setObjectName("Ghost")
        dbtn.clicked.connect(self._pick_dir)
        drow.addWidget(self.dir_lbl, 1)
        drow.addWidget(dbtn)
        dir_card.add_layout(drow)
        clr = QPushButton("Oxirgi fayllar ro'yxatini tozalash")
        clr.setObjectName("Ghost")
        clr.clicked.connect(lambda: (settings.clear_recent(), clr.setText("✓ Tozalandi")))
        dir_card.add(clr)
        root.addWidget(dir_card)

        root.addStretch(1)

        # --- tugmalar ---
        foot = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        foot.addWidget(self.status, 1)
        cancel = QPushButton("Bekor")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Saqlash")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        foot.addWidget(cancel)
        foot.addWidget(save)
        root.addLayout(foot)

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Standart papka", settings.output_dir())
        if d:
            self.dir_lbl.setText(d)

    def _save(self):
        # API kalit
        key = self.api_input.text().strip()
        settings.set_api_key(key)
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
        elif "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]

        # papka
        settings.set_output_dir(self.dir_lbl.text())

        # tema — darrov qo'llanadi
        new_theme = self.theme_cb.currentData()
        if new_theme != settings.theme():
            settings.set_theme(new_theme)
            QApplication.instance().setStyleSheet(build_qss(new_theme))
            if self._on_theme_changed:
                self._on_theme_changed(new_theme)

        self.accept()
