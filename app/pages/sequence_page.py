"""
Sekvensiya sahifasi — DNK/RNK tahlili, ORF, primer, restriksiya.
Backend: aida_genomics + aida_bioscience + aida_export.Charts
"""

from __future__ import annotations

import aida_bioscience as bio
import aida_genomics as gx
from aida_export import Charts
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from ..theme import COLORS, MODULE_ACCENT
from ..widgets import Card, ChartView, StatTile, make_table, stat_row
from ..workers import TaskRunner
from .base import Page

DEMO_SEQ = (
    "ATGGCCCTGTGGATGCGCCTCCTGCCCCTGCTGGCGCTGCTGGCCCTCTGGGGA"
    "CCTGACCCAGCCTTCCTGGTGTGCGGGGAACGAGGCTTCTTCTACACACCCAAG"
    "ACCCGCCGGGAGGCAGAGGACCTGCAGGTGGGGCAGGTGGAGCTGGGCGGG"
)


class SequencePage(Page):
    def __init__(self, parent=None):
        super().__init__(
            "Sekvensiya tahlili",
            "DNK yoki RNK sekvensiyasini kiriting — tarkib, oqsil, ORF, "
            "primer sifati va restriksiya joylari avtomatik hisoblanadi.",
            MODULE_ACCENT["sequence"],
            parent,
        )
        self._runner = TaskRunner()
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        # --- Kiritish kartochkasi ---
        inp = Card("Sekvensiya kiriting")
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Masalan: ATGGCCCTGTGG...")
        self.editor.setPlainText(DEMO_SEQ)
        self.editor.setMinimumHeight(120)
        inp.add(self.editor)

        btn_row = QHBoxLayout()
        self.analyze_btn = QPushButton("Tahlil qilish")
        self.analyze_btn.setObjectName("Primary")
        self.analyze_btn.clicked.connect(self._analyze)
        clear_btn = QPushButton("Tozalash")
        clear_btn.setObjectName("Ghost")
        clear_btn.clicked.connect(self._clear_all)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        btn_row.addWidget(self.analyze_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.status)
        inp.add_layout(btn_row)
        self.add(inp)

        # --- Statistika plitkalari ---
        self.tiles = {
            "type": StatTile("—", "Turi", COLORS["primary"]),
            "length": StatTile("—", "Uzunlik (nt)", COLORS["info"]),
            "gc": StatTile("—", "GC tarkibi", COLORS["secondary"]),
            "protein": StatTile("—", "Oqsil (aa)", COLORS["success"]),
            "mw": StatTile("—", "Og'irlik (kDa)", COLORS["warning"]),
        }
        self.add_layout(stat_row(*self.tiles.values()))

        # --- Grafiklar (yonma-yon) ---
        charts = QHBoxLayout()
        charts.setSpacing(16)
        self.chart_base = ChartView()
        self.chart_gc = ChartView()
        charts.addWidget(self.chart_base, 1)
        charts.addWidget(self.chart_gc, 1)
        self.add_layout(charts)

        # --- Molekulyar tafsilotlar (jadvallar joyi) ---
        self.detail_host = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_host)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(16)
        self.add(self.detail_host)

    # ------------------------------------------------------------------
    def _analyze(self):
        raw = self.editor.toPlainText().strip()
        if not raw:
            self.status.setText("Sekvensiya bo'sh.")
            return
        self.analyze_btn.setEnabled(False)
        self.status.setText("Hisoblanmoqda…")
        self._runner.run(self._compute, raw, on_done=self._show, on_error=self._error)

    def _clear_all(self):
        """Tozalash — sekvensiya matni, plitkalar, grafiklar va tafsilotlar."""
        self.editor.clear()
        for t in self.tiles.values():
            t.set_value("—")
        self.chart_base.clear()
        self.chart_gc.clear()
        self._clear_details()
        self.status.setText("")
        self.status.setStyleSheet("")

    @staticmethod
    def _compute(raw: str) -> dict:
        """Fon oqimida — barcha hisob shu yerda."""
        report = gx.analyze_sequence(raw)
        seq = report.reverse_complement  # tozalangan holat uchun emas; asl kerak
        clean = gx.clean_sequence(raw).replace("U", "T")

        out = {
            "report": report,
            "clean": clean,
            "base_png": Charts.base_composition(report.base_counts),
            "gc_png": Charts.gc_content_window(clean, window=40),
            "restriction": bio.find_restriction_sites(clean),
            "orfs": gx.find_orfs(clean, min_length_aa=20)[:5],
        }
        return out

    def _show(self, out: dict):
        self.analyze_btn.setEnabled(True)
        r = out["report"]
        self.tiles["type"].set_value(r.seq_type)
        self.tiles["length"].set_value(f"{r.length:,}")
        self.tiles["gc"].set_value(f"{r.gc_percent:.1f}%")
        self.tiles["protein"].set_value(str(len(r.protein)))
        self.tiles["mw"].set_value(f"{r.mol_weight_kda:.1f}" if r.mol_weight_kda else "—")

        bc = out["base_png"]
        self.chart_base.show_chart(bc.png, bc.title, bc.caption)
        gc = out["gc_png"]
        self.chart_gc.show_chart(gc.png, gc.title, gc.caption)

        # tafsilotlarni qayta yig'amiz
        self._clear_details()

        # Ovozli xulosa
        speech = Card("Xulosa")
        lbl = QLabel(r.to_speech())
        lbl.setObjectName("Muted")
        lbl.setWordWrap(True)
        speech.add(lbl)
        self.detail_layout.addWidget(speech)

        # Oqsil / RNK
        seq_card = Card("Translyatsiya")
        seq_card.add(make_table({
            "RNK (mRNA)": _wrap(r.rna),
            "Oqsil": _wrap(r.protein),
            "Teskari komplement": _wrap(r.reverse_complement),
        }))
        self.detail_layout.addWidget(seq_card)

        # Restriksiya
        rest = out["restriction"]
        rest_card = Card("Restriksiya joylari (klonlash uchun)")
        if rest:
            rows = [
                {"Ferment": e, "Ketma-ketlik": d["site"],
                 "Soni": d["count"], "Pozitsiyalar": ", ".join(map(str, d["positions"]))}
                for e, d in rest.items()
            ]
            rest_card.add(make_table(rows))
        else:
            _empty(rest_card, "Ma'lum fermentlar uchun kesish joyi topilmadi.")
        self.detail_layout.addWidget(rest_card)

        # ORF
        orfs = out["orfs"]
        orf_card = Card("Ochiq o'qish ramkalari (ORF) — potensial genlar")
        if orfs:
            rows = [
                {"Ip": o["strand"], "Ramka": o["frame"], "Boshi (nt)": o["start"],
                 "Uzunlik (aa)": o["length_aa"], "Oqsil": _wrap(o["protein"], 60)}
                for o in orfs
            ]
            orf_card.add(make_table(rows))
        else:
            _empty(orf_card, "20 aa dan uzun ORF topilmadi.")
        self.detail_layout.addWidget(orf_card)

        self.status.setText("Tayyor.")

    def _error(self, msg: str):
        self.analyze_btn.setEnabled(True)
        self.status.setText(f"Xato: {msg}")
        self.status.setStyleSheet(f"color: {COLORS['danger']};")

    def _clear_details(self):
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


def _wrap(s: str, width: int = 70) -> str:
    """Uzun sekvensiyani bo'laklab ko'rsatish."""
    if len(s) <= width:
        return s
    return "\n".join(s[i:i + width] for i in range(0, len(s), width))


def _empty(card: Card, text: str):
    lbl = QLabel(text)
    lbl.setObjectName("Muted")
    lbl.setWordWrap(True)
    card.add(lbl)
