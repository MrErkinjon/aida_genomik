"""
Genomika sahifasi — GWAS assotsiatsiya, Manhattan/QQ, PRS.
Backend: aida_bioscience (gwas_association, bonferroni, polygenic_risk_score)
         aida_export.Charts (manhattan_plot, qq_plot, prs_distribution)
"""

from __future__ import annotations

import aida_bioscience as bio
import numpy as np
from aida_export import Charts
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from ..theme import COLORS, MODULE_ACCENT
from ..widgets import Card, ChartView, StatTile, make_table, stat_row
from ..workers import TaskRunner
from .base import Page


class GenomicsPage(Page):
    def __init__(self, parent=None):
        super().__init__(
            "Genomik tahlil (GWAS)",
            "Kasallik-variant assotsiatsiyasi, Manhattan va QQ grafiklari, "
            "hamda poligenik xavf balli (PRS).",
            MODULE_ACCENT["genomics"],
            parent,
        )
        self._runner = TaskRunner()
        self._prs_runner = TaskRunner()
        self._build_assoc()
        self._build_manhattan()
        self._build_prs()

    # ================================================================
    # 1. Assotsiatsiya testi
    # ================================================================
    def _build_assoc(self):
        card = Card("Assotsiatsiya testi (case–control)")
        hint = QLabel("Genotiplarni vergul bilan kiriting. Fisher aniq testi va odds ratio hisoblanadi.")
        hint.setObjectName("Dim")
        card.add(hint)

        row = QHBoxLayout()
        cbox = QVBoxLayout()
        cbox.addWidget(_lbl("Kasallar (cases):"))
        self.cases = QPlainTextEdit(", ".join(["AA"] * 60 + ["AG"] * 30 + ["GG"] * 10))
        self.cases.setMaximumHeight(70)
        cbox.addWidget(self.cases)
        nbox = QVBoxLayout()
        nbox.addWidget(_lbl("Sog'lom (controls):"))
        self.controls = QPlainTextEdit(", ".join(["AA"] * 30 + ["AG"] * 40 + ["GG"] * 30))
        self.controls.setMaximumHeight(70)
        nbox.addWidget(self.controls)
        row.addLayout(cbox)
        row.addLayout(nbox)
        card.add_layout(row)

        btn = QPushButton("Assotsiatsiyani tekshirish")
        btn.setObjectName("Primary")
        btn.clicked.connect(self._run_assoc)
        card.add(btn)
        self.add(card)

        self.assoc_tiles = {
            "or": StatTile("—", "Odds ratio", COLORS["info"]),
            "case": StatTile("—", "Case chastota", COLORS["primary"]),
            "ctrl": StatTile("—", "Control chastota", COLORS["secondary"]),
            "p": StatTile("—", "p-qiymat", COLORS["warning"]),
            "sig": StatTile("—", "GWAS chegara", COLORS["success"]),
        }
        self.add_layout(stat_row(*self.assoc_tiles.values()))
        self.assoc_note = QLabel("")
        self.assoc_note.setObjectName("Dim")
        self.assoc_note.setWordWrap(True)
        self.add(self.assoc_note)

    def _run_assoc(self):
        cases = _parse_genos(self.cases.toPlainText())
        controls = _parse_genos(self.controls.toPlainText())
        if not cases or not controls:
            self.assoc_note.setText("Genotiplarni kiriting.")
            return
        res = bio.gwas_association(cases, controls)
        if "error" in res:
            self.assoc_note.setText(res["error"])
            return
        self.assoc_tiles["or"].set_value(f"{res['odds_ratio']}")
        self.assoc_tiles["case"].set_value(f"{res['case_freq']:.3f}")
        self.assoc_tiles["ctrl"].set_value(f"{res['control_freq']:.3f}")
        self.assoc_tiles["p"].set_value(f"{res['p_value']:.2e}")
        sig = "O'tdi" if res["significant"] else "O'tmadi"
        self.assoc_tiles["sig"].set_value(sig)
        self.assoc_tiles["sig"].value.setStyleSheet(
            f"color: {COLORS['success'] if res['significant'] else COLORS['text_muted']};")
        ci = res["ci_95"]
        self.assoc_note.setText(
            f"Alel {res['allele_1']} vs {res['allele_2']}. 95% ishonch oralig'i: "
            f"{ci[0]}–{ci[1]}. {res['note']}")

    # ================================================================
    # 2. Manhattan + QQ (demo ma'lumot)
    # ================================================================
    def _build_manhattan(self):
        card = Card("Manhattan va QQ grafiklari")
        hint = QLabel(
            "Katta GWAS natijalarini vizualizatsiya qiladi. Namoyish uchun sun'iy "
            "ma'lumot yaratamiz — bitta xromosomada signal joylashtiriladi.")
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        card.add(hint)

        row = QHBoxLayout()
        row.addWidget(_lbl("Variantlar (har xromosoma):"))
        self.n_variants = QSpinBox()
        self.n_variants.setRange(50, 2000)
        self.n_variants.setValue(220)
        self.n_variants.setButtonSymbols(QSpinBox.NoButtons)
        row.addWidget(self.n_variants)
        row.addSpacing(16)
        row.addWidget(_lbl("Signal xromosoma:"))
        self.signal_chrom = QComboBox()
        self.signal_chrom.addItems([str(i) for i in range(1, 11)])
        self.signal_chrom.setCurrentText("3")
        row.addWidget(self.signal_chrom)
        row.addStretch(1)
        card.add_layout(row)

        self.manhattan_btn = QPushButton("Grafiklarni yaratish")
        self.manhattan_btn.setObjectName("Primary")
        self.manhattan_btn.clicked.connect(self._run_manhattan)
        card.add(self.manhattan_btn)
        self.add(card)

        self.manhattan_chart = ChartView()
        self.add(self.manhattan_chart)
        qq_row = QHBoxLayout()
        self.qq_chart = ChartView()
        self.bonf_card = Card("Bonferroni tuzatishi")
        self.bonf_host = QVBoxLayout()
        self.bonf_card.add_layout(self.bonf_host)
        qq_row.addWidget(self.qq_chart, 1)
        qq_row.addWidget(self.bonf_card, 1)
        self.add_layout(qq_row)

    def _run_manhattan(self):
        self.manhattan_btn.setEnabled(False)
        n = self.n_variants.value()
        signal = int(self.signal_chrom.currentText())
        self._runner.run(_gen_gwas, n, signal,
                         on_done=self._show_manhattan, on_error=self._mh_err)

    def _show_manhattan(self, out: dict):
        self.manhattan_btn.setEnabled(True)
        m = out["manhattan"]
        self.manhattan_chart.show_chart(m.png, m.title, m.caption)
        q = out["qq"]
        self.qq_chart.show_chart(q.png, q.title, q.caption)
        _clear(self.bonf_host)
        b = out["bonferroni"]
        tbl = make_table({
            "Testlar soni": b["tests"],
            "Tuzatilgan chegara": f"{b['corrected_threshold']:.2e}",
            "Ahamiyatli (tuzatishdan keyin)": b["significant_count"],
        })
        self.bonf_host.addWidget(tbl)

    def _mh_err(self, msg: str):
        self.manhattan_btn.setEnabled(True)

    # ================================================================
    # 3. PRS
    # ================================================================
    def _build_prs(self):
        card = Card("Poligenik xavf balli (PRS)")
        hint = QLabel(
            "Har qatorda:  rsID  doza(0/1/2)  og'irlik.  Masalan:  rs123  1  0.4")
        hint.setObjectName("Dim")
        card.add(hint)
        self.prs_input = QPlainTextEdit(
            "rs101  2  0.35\nrs202  1  -0.20\nrs303  0  0.50\nrs404  2  0.15\nrs505  1  0.28")
        self.prs_input.setMaximumHeight(120)
        card.add(self.prs_input)
        btn = QPushButton("PRS hisoblash")
        btn.setObjectName("Primary")
        btn.clicked.connect(self._run_prs)
        card.add(btn)
        self.add(card)

        self.prs_chart = ChartView()
        self.add(self.prs_chart)
        self.prs_note = QLabel("")
        self.prs_note.setObjectName("Disclaimer")
        self.prs_note.setWordWrap(True)
        self.prs_note.hide()
        self.add(self.prs_note)

    def _run_prs(self):
        variants = {}
        for line in self.prs_input.toPlainText().splitlines():
            parts = line.replace(",", " ").split()
            if len(parts) >= 3:
                try:
                    variants[parts[0]] = (int(float(parts[1])), float(parts[2]))
                except ValueError:
                    continue
        if not variants:
            self.prs_note.setText("To'g'ri formatda variant kiriting.")
            self.prs_note.show()
            return
        res = bio.polygenic_risk_score(variants)
        self.prs_note.setText("⚠  " + res["interpretation"])
        self.prs_note.show()
        self.prs_chart.clear("Grafik chizilmoqda…")
        self._prs_runner.run(
            Charts.prs_distribution, user_score=res["prs"],
            on_done=lambda c: self.prs_chart.show_chart(c.png, c.title, c.caption),
            on_error=lambda e: self.prs_chart.clear(f"Grafik xatosi: {e}"))


# ---------------------------------------------------------------------
def _gen_gwas(n: int, signal_chrom: int) -> dict:
    """Sun'iy GWAS ma'lumot + Manhattan/QQ/Bonferroni (fon oqimida)."""
    rng = np.random.default_rng(42)
    results = []
    for c in range(1, 11):
        positions = np.sort(rng.integers(0, 200_000, n))
        low = 1e-9 if c == signal_chrom else 1e-4
        pvals = rng.uniform(low, 1, n)
        for p, pv in zip(positions, pvals):
            results.append({"chromosome": str(c), "position": int(p), "p_value": float(pv)})
    p_values = [r["p_value"] for r in results]
    return {
        "manhattan": Charts.manhattan_plot(results),
        "qq": Charts.qq_plot(p_values),
        "bonferroni": bio.bonferroni_correction(p_values),
    }


def _parse_genos(text: str) -> list[str]:
    return [g.strip().upper() for g in text.replace("\n", " ").replace(",", " ").split() if g.strip()]


def _lbl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Muted")
    return lbl


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
