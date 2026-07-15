"""
Populyatsiya + Genetika sahifasi.
Backend: aida_bioscience — hardy_weinberg, allele_frequency, heterozygosity,
fst, linkage_disequilibrium, punnett_square, inheritance_risk.
"""

from __future__ import annotations

import aida_bioscience as bio
from aida_export import Charts
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ..theme import COLORS, MODULE_ACCENT
from ..widgets import Card, ChartView, StatTile, make_table, stat_row
from ..workers import TaskRunner
from .base import Page


class PopulationPage(Page):
    def __init__(self, parent=None):
        super().__init__(
            "Populyatsiya va genetika",
            "Hardy-Weinberg muvozanati, allel chastotalari, geterozigotlik, "
            "Punnett kvadrati va irsiyat xavfi.",
            MODULE_ACCENT["population"],
            parent,
        )
        self._hw_runner = TaskRunner()
        self._geno_runner = TaskRunner()
        tabs = QTabWidget()
        tabs.addTab(self._hw_tab(), "Hardy-Weinberg")
        tabs.addTab(self._geno_tab(), "Genotiplar")
        tabs.addTab(self._punnett_tab(), "Punnett kvadrati")
        tabs.addTab(self._inherit_tab(), "Irsiyat xavfi")
        tabs.addTab(self._diff_tab(), "Populyatsiya farqi")
        self.add(tabs)

    # ================================================================
    # 1. Hardy-Weinberg
    # ================================================================
    def _hw_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)

        card = Card("Genotip sonlarini kiriting")
        form = QHBoxLayout()
        self.hw_aa = _spin(320)
        self.hw_ab = _spin(480)
        self.hw_bb = _spin(200)
        for lbl, sp in (("AA (homozigot)", self.hw_aa),
                        ("Aa (geterozigot)", self.hw_ab),
                        ("aa (homozigot)", self.hw_bb)):
            box = QVBoxLayout()
            t = QLabel(lbl)
            t.setObjectName("Muted")
            box.addWidget(t)
            box.addWidget(sp)
            form.addLayout(box)
        card.add_layout(form)
        btn = QPushButton("Hisoblash")
        btn.setObjectName("Primary")
        btn.clicked.connect(self._run_hw)
        card.add(btn)
        lay.addWidget(card)

        self.hw_tiles = {
            "p": StatTile("—", "p (A chastotasi)", COLORS["primary"]),
            "q": StatTile("—", "q (a chastotasi)", COLORS["info"]),
            "chi2": StatTile("—", "χ²", COLORS["secondary"]),
            "pval": StatTile("—", "p-qiymat", COLORS["warning"]),
            "eq": StatTile("—", "Holat", COLORS["success"]),
        }
        lay.addLayout(stat_row(*self.hw_tiles.values()))

        self.hw_chart = ChartView()
        lay.addWidget(self.hw_chart)
        self.hw_speech = QLabel("")
        self.hw_speech.setObjectName("Muted")
        self.hw_speech.setWordWrap(True)
        lay.addWidget(self.hw_speech)
        lay.addStretch(1)
        return w

    def _run_hw(self):
        aa, ab, bb = self.hw_aa.value(), self.hw_ab.value(), self.hw_bb.value()
        if aa + ab + bb == 0:
            self.hw_speech.setText("Populyatsiya bo'sh.")
            return
        res = bio.hardy_weinberg(aa, ab, bb)
        self.hw_tiles["p"].set_value(f"{res.p:.3f}")
        self.hw_tiles["q"].set_value(f"{res.q:.3f}")
        self.hw_tiles["chi2"].set_value(f"{res.chi_square:.2f}")
        self.hw_tiles["pval"].set_value(f"{res.p_value:.4f}")
        eq = "Muvozanat" if res.in_equilibrium else "Chetlashgan"
        self.hw_tiles["eq"].set_value(eq)
        self.hw_tiles["eq"].value.setStyleSheet(
            f"color: {COLORS['success'] if res.in_equilibrium else COLORS['danger']};")

        self.hw_speech.setText(res.to_speech())
        self.hw_chart.clear("Grafik chizilmoqda…")
        self._hw_runner.run(
            Charts.hardy_weinberg, res.observed, res.expected, res.chi_square, res.p_value,
            on_done=lambda c: self.hw_chart.show_chart(c.png, c.title, c.caption),
            on_error=lambda e: self.hw_chart.clear(f"Grafik xatosi: {e}"))

    # ================================================================
    # 2. Genotiplar — allel chastotasi + geterozigotlik
    # ================================================================
    def _geno_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)

        card = Card("Genotiplar ro'yxati")
        hint = QLabel("Vergul yoki probel bilan ajrating. Masalan:  AA, AG, GG, AG, AA")
        hint.setObjectName("Dim")
        card.add(hint)
        self.geno_input = QLineEdit("AA, AG, GG, AG, AA, AG, GG, AG, AA, GG")
        card.add(self.geno_input)
        btn = QPushButton("Hisoblash")
        btn.setObjectName("Primary")
        btn.clicked.connect(self._run_geno)
        card.add(btn)
        lay.addWidget(card)

        self.geno_tiles = {
            "ho": StatTile("—", "Kuzatilgan het.", COLORS["primary"]),
            "he": StatTile("—", "Kutilgan het.", COLORS["info"]),
            "f": StatTile("—", "Inbreeding F", COLORS["warning"]),
        }
        lay.addLayout(stat_row(*self.geno_tiles.values()))
        self.geno_chart = ChartView()
        lay.addWidget(self.geno_chart)
        lay.addStretch(1)
        return w

    def _run_geno(self):
        genotypes = [g for g in self.geno_input.text().replace(",", " ").split() if g]
        if not genotypes:
            return
        freqs = bio.allele_frequency(genotypes)
        het = bio.heterozygosity(genotypes)
        if het:
            self.geno_tiles["ho"].set_value(f"{het['observed_het']:.3f}")
            self.geno_tiles["he"].set_value(f"{het['expected_het']:.3f}")
            self.geno_tiles["f"].set_value(f"{het['inbreeding_coefficient_F']:.3f}")
        if freqs:
            self.geno_chart.clear("Grafik chizilmoqda…")
            self._geno_runner.run(
                Charts.allele_frequencies, freqs,
                on_done=lambda c: self.geno_chart.show_chart(c.png, c.title, c.caption),
                on_error=lambda e: self.geno_chart.clear(f"Grafik xatosi: {e}"))

    # ================================================================
    # 3. Punnett kvadrati
    # ================================================================
    def _punnett_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)

        card = Card("Ota-ona genotiplari")
        row = QHBoxLayout()
        self.p1 = QLineEdit("Aa")
        self.p2 = QLineEdit("Aa")
        self.p1.setMaximumWidth(120)
        self.p2.setMaximumWidth(120)
        row.addWidget(QLabel("Ota-ona 1:"))
        row.addWidget(self.p1)
        row.addSpacing(20)
        row.addWidget(QLabel("Ota-ona 2:"))
        row.addWidget(self.p2)
        row.addStretch(1)
        card.add_layout(row)
        btn = QPushButton("Kvadratni hisoblash")
        btn.setObjectName("Primary")
        btn.clicked.connect(self._run_punnett)
        card.add(btn)
        lay.addWidget(card)

        self.punnett_host = QVBoxLayout()
        lay.addLayout(self.punnett_host)
        lay.addStretch(1)
        return w

    def _run_punnett(self):
        _clear(self.punnett_host)
        p1, p2 = self.p1.text().strip(), self.p2.text().strip()
        if len(p1) != 2 or len(p2) != 2:
            _add(self.punnett_host, _muted("Har bir genotip 2 harfdan iborat bo'lsin (masalan Aa)."))
            return
        res = bio.punnett_square(p1, p2)
        card = Card(f"Chatishtirish: {res['cross']}")
        rows = [{"Genotip": gt, "Ehtimol": pct} for gt, pct in res["genotypes"].items()]
        card.add(make_table(rows))
        _add(self.punnett_host, card)

    # ================================================================
    # 4. Irsiyat xavfi
    # ================================================================
    def _inherit_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)

        card = Card("Irsiyat modeli")
        form = QFormLayout()
        form.setSpacing(12)
        self.pattern = QComboBox()
        self.pattern.addItems([
            "autosomal_recessive", "autosomal_dominant", "x_linked_recessive"])
        self.status_cb = QComboBox()
        self.status_cb.addItems(["both_carriers", "one_affected", "one_carrier"])
        form.addRow("Irsiyat turi:", self.pattern)
        form.addRow("Ota-ona holati:", self.status_cb)
        card.add_layout(form)
        btn = QPushButton("Xavfni hisoblash")
        btn.setObjectName("Primary")
        btn.clicked.connect(self._run_inherit)
        card.add(btn)
        lay.addWidget(card)

        self.inherit_host = QVBoxLayout()
        lay.addLayout(self.inherit_host)
        lay.addStretch(1)
        return w

    def _run_inherit(self):
        _clear(self.inherit_host)
        res = bio.inheritance_risk(self.pattern.currentText(), self.status_cb.currentText())
        if "error" in res:
            _add(self.inherit_host, _muted(
                "Bu kombinatsiya uchun ma'lumot yo'q. Mos juftlik: "
                "autosomal_recessive + both_carriers, autosomal_dominant + one_affected, "
                "x_linked_recessive + one_carrier."))
            return
        disclaimer = res.pop("disclaimer", "")
        note = res.pop("note", "")
        card = Card("Nasl xavfi")
        rows = [{"Ko'rsatkich": k, "Ehtimol": v} for k, v in res.items()]
        card.add(make_table(rows))
        if note:
            card.add(_muted(note))
        _add(self.inherit_host, card)
        if disclaimer:
            d = QLabel("⚠  " + disclaimer)
            d.setObjectName("Disclaimer")
            d.setWordWrap(True)
            _add(self.inherit_host, d)

    # ================================================================
    # 5. Populyatsiya farqi — Fst + LD
    # ================================================================
    def _diff_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)

        # Fst
        fst_card = Card("Fst — ikki populyatsiya orasidagi farqlanish")
        hint = QLabel("Har populyatsiya uchun allel chastotalarini vergul bilan kiriting.")
        hint.setObjectName("Dim")
        fst_card.add(hint)
        self.fst_p1 = QLineEdit("0.3, 0.5, 0.7")
        self.fst_p2 = QLineEdit("0.35, 0.45, 0.72")
        fst_card.add(self.fst_p1)
        fst_card.add(self.fst_p2)
        fbtn = QPushButton("Fst hisoblash")
        fbtn.setObjectName("Primary")
        fbtn.clicked.connect(self._run_fst)
        fst_card.add(fbtn)
        self.fst_result = QLabel("")
        self.fst_result.setObjectName("SectionTitle")
        fst_card.add(self.fst_result)
        lay.addWidget(fst_card)

        # LD
        ld_card = Card("Bog'lanish nomuvozanati (LD)")
        hint2 = QLabel("Gaplotiplarni kiriting. Masalan:  AB, Ab, aB, ab, AB, AB")
        hint2.setObjectName("Dim")
        ld_card.add(hint2)
        self.ld_input = QLineEdit("AB, AB, AB, Ab, aB, ab, AB, aB")
        ld_card.add(self.ld_input)
        lbtn = QPushButton("LD hisoblash")
        lbtn.setObjectName("Primary")
        lbtn.clicked.connect(self._run_ld)
        ld_card.add(lbtn)
        self.ld_host = QVBoxLayout()
        ld_card.add_layout(self.ld_host)
        lay.addWidget(ld_card)
        lay.addStretch(1)
        return w

    def _run_fst(self):
        try:
            p1 = [float(x) for x in self.fst_p1.text().replace(",", " ").split()]
            p2 = [float(x) for x in self.fst_p2.text().replace(",", " ").split()]
        except ValueError:
            self.fst_result.setText("Faqat raqam kiriting.")
            return
        val = bio.fst(p1, p2)
        level = ("kam farq" if val < 0.05 else "o'rtacha farq" if val < 0.15 else "katta farq")
        self.fst_result.setText(f"Fst = {val}  ({level})")
        self.fst_result.setStyleSheet(f"color: {MODULE_ACCENT['population']};")

    def _run_ld(self):
        _clear(self.ld_host)
        haps = [h for h in self.ld_input.text().replace(",", " ").split() if len(h) == 2]
        if not haps:
            _add(self.ld_host, _muted("Kamida bitta 2-harfli gaplotip kiriting."))
            return
        res = bio.linkage_disequilibrium(haps)
        _add(self.ld_host, make_table(res))


# ---------------------------------------------------------------------
def _spin(default: int) -> QSpinBox:
    sp = QSpinBox()
    sp.setRange(0, 10_000_000)
    sp.setValue(default)
    sp.setButtonSymbols(QSpinBox.NoButtons)
    return sp


def _muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Muted")
    lbl.setWordWrap(True)
    return lbl


def _add(layout, widget):
    layout.addWidget(widget)


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
