"""
Assotsiativ xaritalash sahifasi — SSR marker-trait assotsiatsiya (single-marker).
Backend: aida_assoc
"""

from __future__ import annotations

import os
import subprocess
import sys

import aida_assoc as asc
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)

from .. import settings
from ..theme import COLORS, MODULE_ACCENT
from ..widgets import Card, ChartView, StatTile, make_table, stat_row
from ..workers import TaskRunner
from .base import Page


class AssocPage(Page):
    def __init__(self, parent=None):
        super().__init__(
            "Assotsiativ xaritalash",
            "SSR marker–trait assotsiatsiyasi (single-marker, genetik xaritasiz). "
            "Marker QC, fenotip diversity, kinship-korreksiyali MTA va dala↔lab mosligi.",
            MODULE_ACCENT["assoc"],
            parent,
        )
        self._runner = TaskRunner()
        self._chart_runner = TaskRunner()
        self._data: dict = {}
        self._build()
        self._refresh_recent()

    def _build(self):
        load_card = Card("Ma'lumot")
        hint = QLabel("3 varaqli Excel yuklang (Genotype, Field_Data, Lab_Data) "
                      "yoki namuna ma'lumotdan foydalaning.")
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        load_card.add(hint)
        row = QHBoxLayout()
        self.sample_btn = QPushButton("Namuna ma'lumot")
        self.sample_btn.setObjectName("Primary")
        self.sample_btn.clicked.connect(self._use_sample)
        self.load_btn = QPushButton("Fayl yuklash")
        self.load_btn.setObjectName("Ghost")
        self.load_btn.clicked.connect(self._pick_file)
        self.file_lbl = QLabel("Fayl tanlanmagan")
        self.file_lbl.setObjectName("Muted")
        row.addWidget(self.sample_btn)
        row.addWidget(self.load_btn)
        row.addWidget(self.file_lbl, 1)
        load_card.add_layout(row)

        rrow = QHBoxLayout()
        self.recent_cb = QComboBox()
        self.recent_cb.setMinimumWidth(220)
        self.recent_cb.activated.connect(self._open_recent)
        rrow.addWidget(QLabel("Oxirgi:"))
        rrow.addWidget(self.recent_cb)
        drop_hint = QLabel("yoki faylni oynaga sudrab tashlang")
        drop_hint.setObjectName("Dim")
        rrow.addWidget(drop_hint)
        rrow.addStretch(1)
        load_card.add_layout(rrow)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        load_card.add(self.progress)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        load_card.add(self.status)
        self.add(load_card)

        # Tablar
        self.tabs = QTabWidget()
        self.tabs.setEnabled(False)
        self._tab_qc = self._make_scroll_tab()
        self._tab_pheno = self._make_scroll_tab()
        self._tab_struct = self._make_scroll_tab()
        self._tab_mta = self._make_scroll_tab()
        self._tab_overlap = self._make_scroll_tab()
        self.tabs.addTab(self._tab_qc[0], "Marker QC")
        self.tabs.addTab(self._tab_pheno[0], "Fenotip")
        self.tabs.addTab(self._tab_struct[0], "Struktura / Kinship")
        self.tabs.addTab(self._tab_mta[0], "MTA")
        self.tabs.addTab(self._tab_overlap[0], "Dala ↔ Lab")
        self.add(self.tabs)

        # Eksport
        self._out_dir = settings.output_dir()
        exp_card = Card("Hisobot eksporti")
        ehint = QLabel("Barcha natijalar (QC/PIC, descriptives, MTA, grafiklar) "
                       "bitta publikatsiya-hisobotiga.")
        ehint.setObjectName("Dim")
        ehint.setWordWrap(True)
        exp_card.add(ehint)
        erow = QHBoxLayout()
        self.xlsx_btn = QPushButton("Excel")
        self.pdf_btn = QPushButton("PDF")
        self.docx_btn = QPushButton("Word")
        for b, fmt in ((self.xlsx_btn, "xlsx"), (self.pdf_btn, "pdf"), (self.docx_btn, "docx")):
            b.setObjectName("Ghost")
            b.setEnabled(False)
            b.clicked.connect(lambda _=False, f=fmt: self._export(f))
            erow.addWidget(b)
        erow.addStretch(1)
        exp_card.add_layout(erow)
        self.exp_status = QLabel("")
        self.exp_status.setObjectName("Dim")
        exp_card.add(self.exp_status)
        self.add(exp_card)
        self._export_runner = TaskRunner()

    def _make_scroll_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 14, 0, 0)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignTop)
        return w, lay

    # ------------------------------------------------------------------
    def _use_sample(self):
        self.file_lbl.setText("Namuna: 80 RIL × 83 SSR lokus")
        self._start(asc.sample_dataset())

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Assotsiatsiya fayli (3 varaq)", settings.output_dir(),
            "Excel (*.xlsx *.xls);;Barchasi (*)")
        if path:
            self.load_path(path)

    def load_path(self, path: str):
        """Tashqi chaqiruv (drag-drop / oxirgi fayllar)."""
        self.file_lbl.setText(os.path.basename(path))
        settings.add_recent(path)
        self._refresh_recent()
        self._start(path)

    def _refresh_recent(self):
        self.recent_cb.blockSignals(True)
        self.recent_cb.clear()
        recents = settings.recent_files()
        self.recent_cb.addItem("— oxirgi fayllar —", None)
        for p in recents:
            self.recent_cb.addItem(os.path.basename(p), p)
        self.recent_cb.setEnabled(bool(recents))
        self.recent_cb.blockSignals(False)

    def _open_recent(self, idx: int):
        path = self.recent_cb.itemData(idx)
        if path and os.path.exists(path):
            self.load_path(path)

    def _start(self, source):
        # fayl o'qish + validatsiya + to'liq tahlil — hammasi worker'da
        self.status.setText("O'qilmoqda va tahlil bajarilmoqda (QC, kinship, MTA scan)…")
        self.progress.show()
        self.sample_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self._runner.run(_compute_source, source, on_done=self._done, on_error=self._error)

    def _error(self, msg: str):
        self.progress.hide()
        self.sample_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        self.status.setText(f"Xato: {msg}")

    def _done(self, data: dict):
        self.progress.hide()
        self.sample_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        self._data = data
        self.tabs.setEnabled(True)
        self._fill_qc()
        self._fill_pheno()
        self._fill_struct()
        self._fill_mta()
        self._fill_overlap()
        nsig = len(asc.significant_hits(data["field_mta"])) + len(asc.significant_hits(data["lab_mta"]))
        self.status.setText(
            f"Tayyor. Markerlar: {data['qc'].shape[0]}, MTA testlari: "
            f"{len(data['field_mta']) + len(data['lab_mta'])}, FDR-signifikant: {nsig}.")
        for b in (self.xlsx_btn, self.pdf_btn, self.docx_btn):
            b.setEnabled(True)

    def _export(self, fmt: str):
        if not self._data:
            return
        d = QFileDialog.getExistingDirectory(self, "Saqlash papkasi", self._out_dir)
        if not d:
            return
        self._out_dir = d
        settings.set_output_dir(d)
        self.exp_status.setText("Hisobot tayyorlanmoqda…")
        self._export_runner.run(
            _export_assoc, self._data, os.path.join(d, "aida_assotsiatsiya"), fmt,
            on_done=self._export_done, on_error=self._export_err)

    def _export_done(self, path: str):
        self.exp_status.setText(f"✓ Saqlandi: {path}")
        self.exp_status.setStyleSheet(f"color: {COLORS['success']};")
        _open_folder(os.path.dirname(path))

    def _export_err(self, msg: str):
        self.exp_status.setText(f"Xato: {msg}")
        self.exp_status.setStyleSheet(f"color: {COLORS['danger']};")

    # ---- Tab 1: QC ----
    def _fill_qc(self):
        _, lay = self._tab_qc
        _clear(lay)
        s = self._data["qc_summary"]
        pic = s["O'rtacha PIC"]
        he = s["O'rtacha He"]
        tiles = [
            StatTile(str(s["Polimorf"]), "Polimorf lokus", COLORS["primary"]),
            StatTile(str(s["Monomorf"]), "Monomorf", COLORS["danger"]),
            StatTile(str(pic), "O'rtacha PIC", COLORS["secondary"]),
            StatTile(str(he), "O'rtacha He", COLORS["info"]),
            StatTile(str(s["MAF<0.05 (kam)"]), "MAF<0.05", COLORS["warning"]),
        ]
        lay.addLayout(stat_row(*tiles))
        card = Card("Lokuslar bo'yicha PIC / MAF / diversity")
        card.add(make_table(self._data["qc"]))
        lay.addWidget(card)

    # ---- Tab 2: Fenotip ----
    def _fill_pheno(self):
        _, lay = self._tab_pheno
        _clear(lay)
        fcard = Card("Dala traitlari — descriptive statistika")
        fcard.add(make_table(self._data["field_desc"]))
        lay.addWidget(fcard)
        lcard = Card("Laboratoriya traitlari — descriptive statistika")
        lcard.add(make_table(self._data["lab_desc"]))
        lay.addWidget(lcard)
        cv = ChartView()
        cv.show_chart(self._data["corr_png"], "Korrelyatsiya (dala traitlari)",
                      "* p<0.05, ** p<0.01")
        lay.addWidget(cv)

    # ---- Tab 3: Struktura ----
    def _fill_struct(self):
        _, lay = self._tab_struct
        _clear(lay)
        pca_v = ChartView()
        pca_v.show_chart(self._data["pca_png"], "PCA (dala fenotipi)",
                         "Nuqtalar = liniyalar (klaster rangi), qizil vektorlar = traitlar.")
        lay.addWidget(pca_v)
        dendro_v = ChartView()
        dendro_v.show_chart(self._data["dendro_png"], "RIL dendrogrammasi (fenotip)")
        lay.addWidget(dendro_v)
        kin_v = ChartView()
        kin_v.show_chart(self._data["kinship_png"], "Kinship matritsasi (marker asosida)",
                         "Assotsiatsiyada qarindoshlikni korreksiya qilish uchun ishlatiladi.")
        lay.addWidget(kin_v)

    # ---- Tab 4: MTA ----
    def _fill_mta(self):
        _, lay = self._tab_mta
        _clear(lay)
        note = QLabel(
            "Genetik xarita yo'qligi sababli bu single-marker assotsiatsiya "
            "(interval/QTL mapping emas). GLM (marker) va MLM-approx (marker + "
            "kinship PC lari) hisoblanadi; FDR (Benjamini-Hochberg) va Bonferroni qo'llanadi.")
        note.setObjectName("Disclaimer")
        note.setWordWrap(True)
        lay.addWidget(note)

        hits = self._data["all_hits"]
        hcard = Card(f"Ahamiyatli assotsiatsiyalar (FDR<0.05): {len(hits)} ta")
        if len(hits):
            show = hits[["Dataset", "Marker", "Trait", "effect", "R2%",
                         "p_GLM", "p_MLM", "q_FDR", "sig"]].copy()
            hcard.add(make_table(show.head(40)))
        else:
            lbl = QLabel("FDR chegarasidan o'tgan assotsiatsiya topilmadi "
                         "(namuna effektlari kuchsizroq bo'lishi mumkin).")
            lbl.setObjectName("Muted")
            hcard.add(lbl)
        lay.addWidget(hcard)

        # trait tanlab Manhattan + box
        sel_card = Card("Trait bo'yicha Manhattan va box grafik")
        srow = QHBoxLayout()
        srow.addWidget(QLabel("Dataset:"))
        self.ds_cb = QComboBox()
        self.ds_cb.addItems(["field", "lab"])
        self.ds_cb.currentTextChanged.connect(self._refresh_traits)
        srow.addWidget(self.ds_cb)
        srow.addWidget(QLabel("Trait:"))
        self.trait_cb = QComboBox()
        self.trait_cb.currentTextChanged.connect(self._show_manhattan)
        srow.addWidget(self.trait_cb, 1)
        sel_card.add_layout(srow)
        lay.addWidget(sel_card)
        self.mh_chart = ChartView()
        lay.addWidget(self.mh_chart)
        self.box_chart = ChartView()
        lay.addWidget(self.box_chart)
        self._refresh_traits("field")

    def _refresh_traits(self, dataset: str):
        mta = self._data[f"{dataset}_mta"]
        traits = list(dict.fromkeys(mta["Trait"])) if len(mta) else []
        self.trait_cb.blockSignals(True)
        self.trait_cb.clear()
        self.trait_cb.addItems(traits)
        self.trait_cb.blockSignals(False)
        if traits:
            self._show_manhattan(traits[0])

    def _show_manhattan(self, trait: str):
        if not trait:
            return
        dataset = self.ds_cb.currentText()
        mta = self._data[f"{dataset}_mta"]
        geno = self._data["geno"]
        pheno = self._data["field"] if dataset == "field" else self._data["lab"]
        p_col = "p_MLM" if mta["p_MLM"].notna().any() else "p_GLM"
        # grafiklar worker'da (Manhattan ~1s — UI qotmasin)
        self.mh_chart.clear("Grafik chizilmoqda…")
        self.box_chart.clear("Grafik chizilmoqda…")
        self._chart_runner.run(
            _render_mta_charts, mta, trait, geno, pheno, p_col,
            on_done=lambda out: self._mta_charts_done(out, trait),
            on_error=lambda e: self.mh_chart.clear(f"Grafik xatosi: {e}"))

    def _mta_charts_done(self, out: dict, trait: str):
        self.mh_chart.show_chart(out["manhattan"], f"Manhattan — {trait}")
        if out.get("box") is not None:
            self.box_chart.show_chart(out["box"], f"Eng kuchli: {out['top_marker']} → {trait}")
        else:
            self.box_chart.clear("Box grafik uchun ma'lumot yetarli emas.")

    # ---- Tab 5: Overlap ----
    def _fill_overlap(self):
        _, lay = self._tab_overlap
        _clear(lay)
        ov = self._data["overlap"]
        tiles = [
            StatTile(str(len(ov["field_markers"])), "Dala (drought)", COLORS["primary"]),
            StatTile(str(len(ov["lab_markers"])), "Lab (PEG)", COLORS["info"]),
            StatTile(str(len(ov["overlap"])), "Barqaror (ikkalasi)", COLORS["success"]),
        ]
        lay.addLayout(stat_row(*tiles))
        card = Card("Barqaror nomzod markerlar (dala + lab)")
        if len(ov["overlap"]):
            card.add(make_table({m: "ikkala sharoitda ahamiyatli" for m in sorted(ov["overlap"])}))
            info = QLabel(
                "Bu markerlar ham tabiiy qurg'oqchilik (dala), ham PEG (lab) "
                "sharoitida ahamiyatli — muhitdan mustaqil, marker-yordamli "
                "selektsiya (MAS) uchun eng ishonchli nomzodlar.")
        else:
            info = QLabel("Ikkala sharoitda ham ahamiyatli umumiy marker topilmadi.")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        card.add(info)
        lay.addWidget(card)


# =====================================================================
def _export_assoc(data: dict, base: str, fmt: str) -> str:
    """Assotsiatsiya natijalarini publikatsiya-hisobotiga (Excel/PDF/Word)."""
    from aida_export import AnalysisReport, Chart, ReportExporter

    rep = AnalysisReport(
        title="Assotsiativ xaritalash hisoboti",
        subtitle="SSR marker–trait assotsiatsiyasi (single-marker, kinship-korreksiyali MLM)")

    rep.add_table("Marker sifat nazorati (xulosa)", data["qc_summary"],
                  text="Polimorfizm, PIC va gen diversity umumiy ko'rsatkichlari.")
    rep.add_table("Lokuslar bo'yicha QC", data["qc"].to_dict("records"))
    rep.add_chart(Chart("Traitlar korrelyatsiyasi", data["corr_png"],
                        "Dala traitlari orasidagi Pearson korrelyatsiyasi."))
    rep.add_table("Dala traitlari — descriptive statistika", data["field_desc"].to_dict("records"))
    rep.add_table("Laboratoriya traitlari — descriptive statistika", data["lab_desc"].to_dict("records"))
    rep.add_chart(Chart("PCA (dala fenotipi)", data["pca_png"]))
    rep.add_chart(Chart("RIL dendrogrammasi", data["dendro_png"]))
    rep.add_chart(Chart("Kinship matritsasi", data["kinship_png"],
                        "Marker asosidagi qarindoshlik — MTA'da korreksiya uchun."))

    hits = data["all_hits"]
    if len(hits):
        cols = ["Dataset", "Marker", "Trait", "effect", "R2%", "p_GLM", "p_MLM", "q_FDR", "sig"]
        cols = [c for c in cols if c in hits.columns]
        rep.add_table("Ahamiyatli marker–trait assotsiatsiyalari (FDR<0.05)",
                      hits[cols].to_dict("records"),
                      text="Genetik xarita yo'qligi sababli single-marker assotsiatsiya "
                           "(GLM + kinship-korreksiyali MLM), FDR (Benjamini-Hochberg).")
        # eng kuchli trait uchun Manhattan
        try:
            fmta = data["field_mta"]
            p_col = "p_MLM" if fmta["p_MLM"].notna().any() else "p_GLM"
            top_trait = hits.sort_values("q_FDR").iloc[0]["Trait"]
            src_mta = fmta if top_trait in set(fmta["Trait"]) else data["lab_mta"]
            rep.add_chart(Chart(f"Manhattan — {top_trait}",
                                asc.manhattan(src_mta, top_trait, p_col)))
        except Exception:
            pass
    else:
        rep.add_section("Ahamiyatli assotsiatsiyalar",
                        "FDR chegarasidan o'tgan assotsiatsiya topilmadi.")

    ov = data["overlap"]
    overlap_tbl = ({m: "dala + lab (barqaror)" for m in sorted(ov["overlap"])}
                   or {"—": "umumiy marker topilmadi"})
    rep.add_table("Dala ↔ laboratoriya barqaror markerlari", overlap_tbl,
                  text="Ikkala sharoitda ham ahamiyatli — MAS uchun eng ishonchli nomzodlar.")

    exporter = ReportExporter(rep)
    fn = {"xlsx": exporter.to_xlsx, "pdf": exporter.to_pdf, "docx": exporter.to_docx}[fmt]
    return fn(f"{base}.{fmt}")


def _open_folder(folder: str):
    if sys.platform == "darwin":
        subprocess.run(["open", folder])
    elif sys.platform.startswith("win"):
        os.startfile(folder)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", folder])


def _compute_source(source) -> dict:
    """Fayl (yo'l) yoki tayyor varaqlardan to'liq tahlil (worker oqimida)."""
    if isinstance(source, str):
        sheets = asc.load_workbook(source)
        need = {"Genotype", "Field_Data", "Lab_Data"}
        if not need.issubset(sheets.keys()):
            raise ValueError(
                "Kutilgan varaqlar: Genotype, Field_Data, Lab_Data. "
                f"Topildi: {sorted(sheets.keys())}")
        return _compute(sheets)
    return _compute(source)


def _render_mta_charts(mta, trait, geno, pheno, p_col) -> dict:
    """Manhattan + eng kuchli marker box grafigi (worker oqimida)."""
    out = {"manhattan": asc.manhattan(mta, trait, p_col), "box": None, "top_marker": None}
    sub = mta[mta["Trait"] == trait].sort_values(p_col)
    if len(sub):
        top = sub.iloc[0]["Marker"]
        out["top_marker"] = top
        try:
            out["box"] = asc.box_by_marker(geno, pheno, top, trait)
        except Exception:
            out["box"] = None
    return out


def _compute(sheets: dict) -> dict:
    """Fon oqimida: to'liq assotsiatsiya tahlili + grafiklar."""
    geno, field, lab = asc._prep(sheets)
    qc = asc.marker_qc(geno)
    field_desc = asc.pheno_descriptives(field)
    lab_desc = asc.pheno_descriptives(lab)
    corr, pval = asc.correlation(field)
    K = asc.kinship_matrix(geno)
    kpcs = asc.kinship_pcs(K, 3)
    field_pca = asc.pca(field)
    Z, labels = asc.hierarchical(field, 3)
    field_mta = asc.mta_scan(geno, field, kpcs, "field")
    lab_mta = asc.mta_scan(geno, lab, kpcs, "lab")
    overlap = asc.field_lab_overlap(field_mta, lab_mta)

    import pandas as pd
    fh = asc.significant_hits(field_mta)
    lh = asc.significant_hits(lab_mta)
    all_hits = pd.concat([fh, lh]) if len(fh) or len(lh) else field_mta.head(0)

    # dala korrelyatsiyasi — juda katta bo'lmasligi uchun birinchi 12 trait
    ccols = corr.columns[:12]
    return {
        "geno": geno, "field": field, "lab": lab,
        "qc": qc, "qc_summary": asc.marker_summary(qc),
        "field_desc": field_desc, "lab_desc": lab_desc,
        "field_mta": field_mta, "lab_mta": lab_mta, "overlap": overlap,
        "all_hits": all_hits.reset_index(drop=True),
        "corr_png": asc.corr_heatmap(corr.loc[ccols, ccols], pval.loc[ccols, ccols]),
        "pca_png": asc.pca_biplot(field_pca, labels=labels, title="Field PCA"),
        "dendro_png": asc.dendro(Z, geno.index, "RIL dendrogrammasi"),
        "kinship_png": asc.kinship_heatmap(K),
    }


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        elif item.layout():
            _clear_layout(item.layout())


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
