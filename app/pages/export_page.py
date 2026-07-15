"""
Hisobot eksporti sahifasi — to'liq namunaviy hisobotni Excel/PDF/Word ga chiqaradi.
Backend: aida_export (AnalysisReport, ReportExporter, Charts)
"""

from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
from aida_export import AnalysisReport, Charts, ReportExporter
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from ..theme import COLORS, MODULE_ACCENT
from ..widgets import Card
from ..workers import TaskRunner
from .base import Page


class ExportPage(Page):
    def __init__(self, parent=None):
        super().__init__(
            "Hisobot eksporti",
            "Tahlil natijalarini grafiklari bilan Excel, PDF va Word "
            "formatlarida professional hisobot qilib saqlaydi.",
            MODULE_ACCENT["export"],
            parent,
        )
        self._runner = TaskRunner()
        self._out_dir = os.path.expanduser("~/Desktop")
        self._last_paths: dict[str, str] = {}
        self._build()

    def _build(self):
        # Sozlamalar
        card = Card("Hisobot sozlamalari")
        self.title_input = QLineEdit("Genetik tahlil hisoboti")
        self.subtitle_input = QLineEdit("Namuna: DNK sekvensiyasi va populyatsiya tahlili")
        card.add(_lbl("Sarlavha:"))
        card.add(self.title_input)
        card.add(_lbl("Subtitr:"))
        card.add(self.subtitle_input)

        # Formatlar
        card.add(_lbl("Formatlar:"))
        frow = QHBoxLayout()
        self.fmt_xlsx = QCheckBox("Excel (.xlsx)")
        self.fmt_pdf = QCheckBox("PDF (.pdf)")
        self.fmt_docx = QCheckBox("Word (.docx)")
        for cb in (self.fmt_xlsx, self.fmt_pdf, self.fmt_docx):
            cb.setChecked(True)
            frow.addWidget(cb)
        frow.addStretch(1)
        card.add_layout(frow)

        # Chiqish papkasi
        card.add(_lbl("Saqlash joyi:"))
        drow = QHBoxLayout()
        self.dir_label = QLabel(self._out_dir)
        self.dir_label.setObjectName("Muted")
        dir_btn = QPushButton("Papka tanlash")
        dir_btn.setObjectName("Ghost")
        dir_btn.clicked.connect(self._pick_dir)
        drow.addWidget(self.dir_label, 1)
        drow.addWidget(dir_btn)
        card.add_layout(drow)

        self.gen_btn = QPushButton("Hisobotni yaratish")
        self.gen_btn.setObjectName("Primary")
        self.gen_btn.clicked.connect(self._generate)
        card.add(self.gen_btn)
        self.add(card)

        # Natija
        self.result_card = Card("Natija")
        self.result_host = QVBoxLayout()
        placeholder = QLabel("Hisobot yaratilgach fayllar shu yerda ko'rinadi.")
        placeholder.setObjectName("Muted")
        self.result_host.addWidget(placeholder)
        self.result_card.add_layout(self.result_host)
        self.add(self.result_card)

        note = QLabel(
            "Hisobot 12+ bo'lim va grafikni o'z ichiga oladi: nukleotid tarkibi, "
            "GC oynasi, Hardy-Weinberg, allel chastotalari, Manhattan, QQ, Fst "
            "matritsasi, primer sifati, PRS va oqsil tahlili.")
        note.setObjectName("Dim")
        note.setWordWrap(True)
        self.add(note)

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Saqlash papkasini tanlang", self._out_dir)
        if d:
            self._out_dir = d
            self.dir_label.setText(d)

    def _generate(self):
        fmts = []
        if self.fmt_xlsx.isChecked():
            fmts.append("xlsx")
        if self.fmt_pdf.isChecked():
            fmts.append("pdf")
        if self.fmt_docx.isChecked():
            fmts.append("docx")
        if not fmts:
            self._set_result([QLabel("Kamida bitta format tanlang.")])
            return
        self.gen_btn.setEnabled(False)
        self._set_result([_muted("Hisobot yaratilmoqda… (grafiklar chizilmoqda)")])
        base = os.path.join(self._out_dir, "aida_hisobot")
        self._runner.run(
            _build_and_export, self.title_input.text(), self.subtitle_input.text(),
            base, fmts, on_done=self._done, on_error=self._err)

    def _done(self, paths: dict):
        self.gen_btn.setEnabled(True)
        self._last_paths = paths
        widgets = []
        for fmt, path in paths.items():
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            ok = not path.startswith("XATO")
            icon = "✓" if ok else "✗"
            color = COLORS["success"] if ok else COLORS["danger"]
            lbl = QLabel(f"{icon}  {fmt.upper()}:  {path}")
            lbl.setStyleSheet(f"color: {color};")
            lbl.setWordWrap(True)
            rl.addWidget(lbl, 1)
            widgets.append(row)
        open_btn = QPushButton("Papkani ochish")
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(self._open_folder)
        widgets.append(open_btn)
        self._set_result(widgets)

    def _err(self, msg: str):
        self.gen_btn.setEnabled(True)
        self._set_result([QLabel(f"Xato: {msg}")])

    def _open_folder(self):
        if sys.platform == "darwin":
            subprocess.run(["open", self._out_dir])
        elif sys.platform.startswith("win"):
            os.startfile(self._out_dir)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", self._out_dir])

    def _set_result(self, widgets):
        while self.result_host.count():
            item = self.result_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for w in widgets:
            self.result_host.addWidget(w)


# ---------------------------------------------------------------------
def _build_and_export(title: str, subtitle: str, base: str, fmts: list[str]) -> dict:
    """To'liq namunaviy hisobotni tuzadi va tanlangan formatlarga chiqaradi."""
    np.random.seed(42)
    rep = AnalysisReport(title=title or "Genetik tahlil hisoboti", subtitle=subtitle)

    counts = {"A": 5, "T": 13, "G": 21, "C": 27}
    rep.add_table("Nukleotid tarkibi", counts, headers=["Nukleotid", "Soni"],
                  text="Sekvensiyadagi har bir nukleotid soni.")
    rep.add_chart(Charts.base_composition(counts))

    demo_seq = "ATGGCCCTGTGGATGCGCCTCCTGCCCCTGCTGGCGCTGCTGGCCCTCTGGGGACCTGACCCAGCC" * 6
    rep.add_chart(Charts.gc_content_window(demo_seq, window=40))

    rep.add_section("Hardy-Weinberg muvozanati",
                    "Populyatsiyada genotiplar taqsimoti nazariy kutilganga mos keladimi.")
    rep.add_chart(Charts.hardy_weinberg(
        observed={"AA": 320, "Ab": 480, "bb": 200},
        expected={"AA": 313.6, "Ab": 492.8, "bb": 193.6},
        chi2=0.67, p_value=0.4114))
    rep.add_table("Allel chastotalari", {"A": 0.56, "G": 0.44}, headers=["Allel", "Chastota"])
    rep.add_chart(Charts.allele_frequencies({"A": 0.56, "G": 0.44}))

    gwas = [
        {"chromosome": str(c), "position": p, "p_value": pv}
        for c in range(1, 11)
        for p, pv in zip(
            sorted(np.random.randint(0, 200_000, 220)),
            np.random.uniform(1e-9 if c == 3 else 1e-4, 1, 220))
    ]
    rep.add_chart(Charts.manhattan_plot(gwas))
    rep.add_chart(Charts.qq_plot([g["p_value"] for g in gwas]))

    labels = ["O'zbek", "Qozoq", "Tojik", "Rus"]
    m = np.array([
        [0.000, 0.012, 0.018, 0.045],
        [0.012, 0.000, 0.021, 0.048],
        [0.018, 0.021, 0.000, 0.039],
        [0.045, 0.048, 0.039, 0.000]])
    rep.add_chart(Charts.fst_heatmap(m, labels))

    rep.add_chart(Charts.primer_tm([
        {"primer": "ATGGCCCTGTGGATGCGCC", "tm": 59.7, "gc_percent": 68.4},
        {"primer": "GCTAGCTAGCTTAAGCTAG", "tm": 52.1, "gc_percent": 47.4},
        {"primer": "CGCGCGGCGGCCGCGGCGC", "tm": 72.3, "gc_percent": 89.5}]))
    rep.add_chart(Charts.prs_distribution(user_score=1.4))
    rep.add_chart(Charts.protein_properties({
        "molecular_weight_kda": 24.6, "isoelectric_point": 6.8, "gravy": -0.35,
        "instability_index": 32.4, "stable": True,
        "secondary_structure": {"helix": 0.34, "turn": 0.22, "sheet": 0.28}}))

    exporter = ReportExporter(rep)
    fn = {"xlsx": exporter.to_xlsx, "pdf": exporter.to_pdf, "docx": exporter.to_docx}
    results = {}
    for fmt in fmts:
        try:
            results[fmt] = fn[fmt](f"{base}.{fmt}")
        except Exception as e:  # noqa: BLE001
            results[fmt] = f"XATO: {e}"
    return results


def _lbl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Muted")
    return lbl


def _muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Muted")
    lbl.setWordWrap(True)
    return lbl
