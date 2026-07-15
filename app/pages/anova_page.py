"""
ANOVA / RPC sahifasi — 80 RIL uchun har trait bo'yicha bir tomonlama ANOVA.
Backend: aida_anova
"""

from __future__ import annotations

import os
import subprocess
import sys

import aida_anova as av
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ..theme import COLORS, MODULE_ACCENT
from ..widgets import Card, ChartView, StatTile, make_table, stat_row
from ..workers import TaskRunner
from .base import Page


class AnovaPage(Page):
    def __init__(self, parent=None):
        super().__init__(
            "ANOVA / RPC tahlili",
            "80 RIL uchun har bir RPC trait bo'yicha bir tomonlama ANOVA, LSD, "
            "ahamiyat harflari (a/b/c) va tolerantlik tasnifi.",
            MODULE_ACCENT["anova"],
            parent,
        )
        self._runner = TaskRunner()
        self._chart_runner = TaskRunner()
        self._results: list = []
        self._out_dir = os.path.expanduser("~/Desktop")
        self._build()

    def _build(self):
        # Yuklash
        load_card = Card("Ma'lumot")
        hint = QLabel("Excel/CSV yuklang (Genotype, Rep va RPC ustunlari) yoki "
                      "namuna ma'lumotdan foydalaning.")
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        load_card.add(hint)
        row = QHBoxLayout()
        self.load_btn = QPushButton("Fayl yuklash")
        self.load_btn.setObjectName("Ghost")
        self.load_btn.clicked.connect(self._pick_file)
        self.sample_btn = QPushButton("Namuna ma'lumot")
        self.sample_btn.setObjectName("Primary")
        self.sample_btn.clicked.connect(self._use_sample)
        self.file_lbl = QLabel("Fayl tanlanmagan")
        self.file_lbl.setObjectName("Muted")
        row.addWidget(self.sample_btn)
        row.addWidget(self.load_btn)
        row.addWidget(self.file_lbl, 1)
        load_card.add_layout(row)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        load_card.add(self.status)
        self.add(load_card)

        # Statistika
        self.tiles = {
            "traits": StatTile("—", "Traitlar", COLORS["primary"]),
            "geno": StatTile("—", "Genotiplar", COLORS["info"]),
            "sig": StatTile("—", "Signifikant (P<0.05)", COLORS["success"]),
            "obs": StatTile("—", "Kuzatuvlar", COLORS["secondary"]),
        }
        self.add_layout(stat_row(*self.tiles.values()))

        # Xulosa jadvali
        self.summary_card = Card("ANOVA xulosasi (barcha traitlar)")
        self.summary_host = QVBoxLayout()
        self.summary_card.add_layout(self.summary_host)
        self.add(self.summary_card)

        # Trait tanlash + grafik
        sel_card = Card("Trait bo'yicha batafsil")
        srow = QHBoxLayout()
        srow.addWidget(QLabel("Trait:"))
        self.trait_cb = QComboBox()
        self.trait_cb.currentTextChanged.connect(self._show_trait)
        srow.addWidget(self.trait_cb)
        srow.addStretch(1)
        sel_card.add_layout(srow)
        self.add(sel_card)
        self.chart = ChartView()
        self.add(self.chart)
        self.means_card = Card("Genotip o'rtachalari va tasnif")
        self.means_host = QVBoxLayout()
        self.means_card.add_layout(self.means_host)
        self.add(self.means_card)

        # Eksport
        exp_card = Card("Eksport")
        erow = QHBoxLayout()
        self.xlsx_btn = QPushButton("Excel (har trait varaq)")
        self.xlsx_btn.setObjectName("Ghost")
        self.xlsx_btn.clicked.connect(lambda: self._export("xlsx"))
        self.docx_btn = QPushButton("Word (Results & Discussion)")
        self.docx_btn.setObjectName("Ghost")
        self.docx_btn.clicked.connect(lambda: self._export("docx"))
        for b in (self.xlsx_btn, self.docx_btn):
            b.setEnabled(False)
            erow.addWidget(b)
        erow.addStretch(1)
        exp_card.add_layout(erow)
        self.exp_status = QLabel("")
        self.exp_status.setObjectName("Dim")
        exp_card.add(self.exp_status)
        self.add(exp_card)

    # ------------------------------------------------------------------
    def _use_sample(self):
        self.file_lbl.setText("Namuna ma'lumot (80 RIL × 19 RPC trait)")
        self._start(av.sample_rpc_data())

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "RPC fayl", "", "Jadval (*.xlsx *.xls *.csv);;Barchasi (*)")
        if not path:
            return
        self.file_lbl.setText(os.path.basename(path))
        self._start(path)

    def _start(self, source):
        # fayl o'qish + ustun aniqlash + ANOVA — hammasi worker'da (UI qotmaydi)
        self.status.setText("O'qilmoqda va hisoblanmoqda…")
        self.sample_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self._runner.run(_analyze_source, source, on_done=self._done, on_error=self._error)

    def _done(self, payload: dict):
        self.sample_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        results = payload["results"]
        self._results = results
        self._detected = payload
        sig = sum(1 for r in results if r.p_value < 0.05)
        self.tiles["traits"].set_value(str(len(results)))
        self.tiles["geno"].set_value(str(results[0].n_genotypes))
        self.tiles["sig"].set_value(f"{sig}/{len(results)}")
        self.tiles["obs"].set_value(str(results[0].n_obs))

        _clear(self.summary_host)
        rows = [r.summary_row() for r in results]
        self.summary_host.addWidget(make_table(rows))

        self.trait_cb.blockSignals(True)
        self.trait_cb.clear()
        self.trait_cb.addItems([r.trait for r in results])
        self.trait_cb.blockSignals(False)
        self._show_trait(results[0].trait)

        self.xlsx_btn.setEnabled(True)
        self.docx_btn.setEnabled(True)
        self.status.setText(
            f"Genotip: {payload['gcol']}, Rep: {payload['rcol']} — "
            f"{len(results)} trait tahlil qilindi.")

    def _show_trait(self, trait: str):
        res = next((r for r in self._results if r.trait == trait), None)
        if not res:
            return
        # grafik — worker'da chiziladi (UI qotmasligi uchun)
        caption = (f"F = {res.f_value:.2f} ({res.sig_code}), LSD(0.05) = {res.lsd_05:.2f}, "
                   f"CV = {res.cv_percent:.1f}%. Ranglar: yashil=chidamli, sariq=o'rtacha, qizil=chidamsiz.")
        self.chart.clear("Grafik chizilmoqda…")
        self._chart_runner.run(
            av.bar_chart, res, show_letters=True, top=20,
            on_done=lambda png: self.chart.show_chart(png, trait, caption),
            on_error=lambda e: self.chart.clear(f"Grafik xatosi: {e}"))
        _clear(self.means_host)
        counts = res.means["group"].value_counts().to_dict()
        n_res = counts.get("chidamli", 0)
        n_mod = counts.get("o'rtacha", 0)
        n_sus = counts.get("chidamsiz", 0)
        summary = QLabel(
            f"Chidamli: {n_res}   ·   O'rtacha: {n_mod}   ·   Chidamsiz: {n_sus}")
        summary.setObjectName("Muted")
        self.means_host.addWidget(summary)
        tbl = res.means.rename(columns={
            "genotype": "Genotip", "mean": "Mean", "sd": "SD", "se": "SE",
            "n": "N", "letters": "Guruh", "group": "Tasnif"})
        self.means_host.addWidget(make_table(tbl.head(25)))

    def _error(self, msg: str):
        self.sample_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        self.status.setText(f"Xato: {msg}")

    def _export(self, fmt: str):
        if not self._results:
            return
        d = QFileDialog.getExistingDirectory(self, "Saqlash papkasi", self._out_dir)
        if not d:
            return
        self._out_dir = d
        base = os.path.join(d, "aida_anova")
        try:
            if fmt == "xlsx":
                path = av.to_excel(self._results, base)
            else:
                path = av.to_docx(self._results, base)
            self.exp_status.setText(f"✓ Saqlandi: {path}")
            self.exp_status.setStyleSheet(f"color: {COLORS['success']};")
            _open(d)
        except Exception as e:  # noqa: BLE001
            self.exp_status.setText(f"Xato: {e}")
            self.exp_status.setStyleSheet(f"color: {COLORS['danger']};")


def _analyze_source(source) -> dict:
    """Fayl o'qish + ustun aniqlash + barcha trait ANOVA (worker oqimida)."""
    df = av.load_rpc(source) if isinstance(source, str) else source
    gcol, rcol, traits = av.detect_columns(df)
    if not traits:
        raise ValueError("Raqamli trait (RPC) ustuni topilmadi.")
    return {"results": av.analyze_all(df, gcol, traits), "gcol": gcol, "rcol": rcol}


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


def _open(folder: str):
    if sys.platform == "darwin":
        subprocess.run(["open", folder])
    elif sys.platform.startswith("win"):
        os.startfile(folder)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", folder])
