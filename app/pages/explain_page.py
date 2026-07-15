"""
Tushuntirish sahifasi — Claude orqali genetik izoh + fayl yuklash + variant qidirish.
Backend: aida_genomics (explain_with_claude, handle_genetic_file, lookup_variant)
"""

from __future__ import annotations

import os

import aida_genomics as gx
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from ..theme import COLORS, MODULE_ACCENT
from ..widgets import Card, make_table
from ..workers import TaskRunner
from .base import Page


class ExplainPage(Page):
    def __init__(self, parent=None):
        super().__init__(
            "Tushuntirish",
            "Genetik ma'lumotni Claude sodda o'zbek tilida izohlaydi. "
            "Fayl yuklashingiz yoki savol berishingiz mumkin.",
            MODULE_ACCENT["explain"],
            parent,
        )
        self._runner = TaskRunner()
        self._file_runner = TaskRunner()
        self._var_runner = TaskRunner()
        self._context = ""
        self._build()
        self._check_key()

    def _build(self):
        # API holati
        self.key_banner = QLabel("")
        self.key_banner.setObjectName("Disclaimer")
        self.key_banner.setWordWrap(True)
        self.add(self.key_banner)

        # Fayl yuklash
        file_card = Card("Genetik fayl yuklash")
        hint = QLabel("Qo'llab-quvvatlanadi: FASTA (.fasta/.fa), VCF (.vcf), "
                      "23andMe raw (.txt/.csv/.tsv), PDF hisobot (.pdf).")
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        file_card.add(hint)
        frow = QHBoxLayout()
        self.file_btn = QPushButton("Fayl tanlash")
        self.file_btn.setObjectName("Ghost")
        self.file_btn.clicked.connect(self._pick_file)
        self.file_label = QLabel("Fayl tanlanmagan")
        self.file_label.setObjectName("Muted")
        frow.addWidget(self.file_btn)
        frow.addWidget(self.file_label, 1)
        file_card.add_layout(frow)
        self.file_summary = QLabel("")
        self.file_summary.setObjectName("Muted")
        self.file_summary.setWordWrap(True)
        file_card.add(self.file_summary)
        self.add(file_card)

        # Savol
        q_card = Card("Savol berish")
        self.question = QPlainTextEdit()
        self.question.setPlaceholderText(
            "Masalan: GC tarkibi 60% bo'lishi nimani anglatadi?")
        self.question.setMaximumHeight(90)
        q_card.add(self.question)
        self.ctx_note = QLabel("")
        self.ctx_note.setObjectName("Dim")
        q_card.add(self.ctx_note)
        self.ask_btn = QPushButton("Claude'dan so'rash")
        self.ask_btn.setObjectName("Primary")
        self.ask_btn.clicked.connect(self._ask)
        q_card.add(self.ask_btn)
        self.add(q_card)

        # Javob
        self.answer_card = Card("Claude javobi")
        self.answer = QTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setMinimumHeight(160)
        self.answer.setPlaceholderText("Javob shu yerda ko'rinadi…")
        self.answer_card.add(self.answer)
        self.add(self.answer_card)

        # Variant qidirish (internet)
        var_card = Card("Variant qidirish (myvariant.info)")
        vhint = QLabel("rsID kiriting — gen, klinik ahamiyat va chastota olinadi. "
                       "Internet talab qiladi.")
        vhint.setObjectName("Dim")
        vhint.setWordWrap(True)
        var_card.add(vhint)
        vrow = QHBoxLayout()
        self.rsid = QLineEdit("rs429358")
        self.rsid.setMaximumWidth(200)
        self.var_btn = QPushButton("Qidirish")
        self.var_btn.setObjectName("Ghost")
        self.var_btn.clicked.connect(self._lookup)
        vrow.addWidget(self.rsid)
        vrow.addWidget(self.var_btn)
        vrow.addStretch(1)
        var_card.add_layout(vrow)
        self.var_host = QVBoxLayout()
        var_card.add_layout(self.var_host)
        self.add(var_card)

    # ------------------------------------------------------------------
    def _check_key(self):
        if os.environ.get("ANTHROPIC_API_KEY"):
            self.key_banner.setText("✓  ANTHROPIC_API_KEY topildi — Claude tushuntirish tayyor.")
            self.key_banner.setStyleSheet(
                f"color: {COLORS['success']}; background-color: rgba(16,185,129,0.08); "
                f"border: 1px solid rgba(16,185,129,0.25); border-radius: 10px; padding: 10px 14px;")
        else:
            self.key_banner.setText(
                "⚠  ANTHROPIC_API_KEY o'rnatilmagan. Claude izohi ishlashi uchun "
                "muhitga kalitni qo'shing:  export ANTHROPIC_API_KEY=...")

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Genetik fayl tanlang", "",
            "Genetik fayllar (*.fasta *.fa *.fna *.vcf *.txt *.csv *.tsv *.pdf);;Barchasi (*)")
        if not path:
            return
        self.file_label.setText(os.path.basename(path))
        self.file_summary.setText("O'qilmoqda…")
        self.file_btn.setEnabled(False)
        self._file_runner.run(gx.handle_genetic_file, path,
                              on_done=self._file_done, on_error=self._file_err)

    def _file_done(self, summary: str):
        self.file_btn.setEnabled(True)
        self.file_summary.setText(summary)
        self._context = summary
        self.ctx_note.setText("Yuklangan fayl xulosasi savolga kontekst sifatida qo'shiladi.")

    def _file_err(self, msg: str):
        self.file_btn.setEnabled(True)
        self.file_summary.setText(f"Xato: {msg}")

    def _ask(self):
        q = self.question.toPlainText().strip()
        if not q:
            return
        if not os.environ.get("ANTHROPIC_API_KEY"):
            self.answer.setPlainText("ANTHROPIC_API_KEY o'rnatilmagan.")
            return
        self.ask_btn.setEnabled(False)
        self.answer.setPlainText("Claude o'ylamoqda…")
        self._runner.run(gx.explain_with_claude, q, self._context,
                         on_done=self._answer_done, on_error=self._answer_err)

    def _answer_done(self, text: str):
        self.ask_btn.setEnabled(True)
        self.answer.setPlainText(text)

    def _answer_err(self, msg: str):
        self.ask_btn.setEnabled(True)
        self.answer.setPlainText(f"Xato: {msg}")

    def _lookup(self):
        rsid = self.rsid.text().strip()
        if not rsid:
            return
        self.var_btn.setEnabled(False)
        _clear(self.var_host)
        lbl = QLabel("Qidirilmoqda…")
        lbl.setObjectName("Muted")
        self.var_host.addWidget(lbl)
        self._var_runner.run(gx.lookup_variant, rsid,
                            on_done=self._lookup_done, on_error=self._lookup_err)

    def _lookup_done(self, res):
        self.var_btn.setEnabled(True)
        _clear(self.var_host)
        if not res:
            lbl = QLabel("Variant topilmadi yoki internet yo'q.")
            lbl.setObjectName("Muted")
            self.var_host.addWidget(lbl)
            return
        self.var_host.addWidget(make_table({
            "rsID": res.get("rsid", "—"),
            "Gen": res.get("gene") or "—",
            "Klinik ahamiyat": res.get("significance") or "—",
            "Holat": res.get("condition") or "—",
            "Chastota": str(res.get("frequency") or "—"),
        }))

    def _lookup_err(self, msg: str):
        self.var_btn.setEnabled(True)
        _clear(self.var_host)
        lbl = QLabel(f"Xato: {msg}")
        lbl.setObjectName("Muted")
        self.var_host.addWidget(lbl)


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
