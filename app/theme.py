"""
AIDA Desktop — dizayn tizimi
============================
Ranglar, tipografiya va global QSS (Qt Style Sheet).
Bir joyda saqlab, butun ilova bir xil ko'rinishda bo'lishini ta'minlaydi.
"""

from __future__ import annotations

# =====================================================================
# RANG PALITRASI  (dark, "ultra" ilmiy uslub)
# =====================================================================

# Aksent va nukleotid ranglari — ikkala temada bir xil
_ACCENTS = {
    "primary": "#3b82f6", "primary_hi": "#60a5fa", "primary_dim": "#1e3a8a",
    "secondary": "#8b5cf6", "success": "#10b981", "warning": "#f59e0b",
    "danger": "#ef4444", "info": "#06b6d4",
    "A": "#10b981", "T": "#ef4444", "G": "#3b82f6", "C": "#f59e0b",
}

COLORS_DARK = {
    "bg": "#0b1120", "surface": "#111a2e", "card": "#16213a",
    "card_hover": "#1c2b49", "border": "#243350", "border_soft": "#1b2740",
    "text": "#e8eefc", "text_muted": "#93a4c4", "text_dim": "#5f6f8f",
    **_ACCENTS,
}

COLORS_LIGHT = {
    "bg": "#eef2f8", "surface": "#ffffff", "card": "#ffffff",
    "card_hover": "#f1f5f9", "border": "#dfe6ef", "border_soft": "#eef2f7",
    "text": "#0f1e34", "text_muted": "#5a6b85", "text_dim": "#94a3b8",
    "primary_dim": "#dbe6fb",   # yorug'da och ko'k (checked fon uchun)
    **{k: v for k, v in _ACCENTS.items() if k != "primary_dim"},
}

# Faol palitra (o'rniga mutatsiya qilinadi — barcha 'from theme import COLORS' ko'radi)
COLORS = dict(COLORS_DARK)


def apply_theme(name: str):
    """Faol palitrani almashtiradi (yangi widget'lar yangi rangda quriladi)."""
    palette = COLORS_LIGHT if name == "light" else COLORS_DARK
    COLORS.clear()
    COLORS.update(palette)

# Modullar uchun aksent (sidebar / sahifa sarlavhalari)
MODULE_ACCENT = {
    "sequence": COLORS["primary"],
    "population": COLORS["secondary"],
    "genomics": COLORS["info"],
    "assoc": "#ec4899",       # pushti
    "anova": "#14b8a6",       # teal
    "explain": COLORS["success"],
    "export": COLORS["warning"],
}

FONT_FAMILY = "SF Pro Text, -apple-system, Helvetica Neue, Arial, sans-serif"
MONO_FAMILY = "SF Mono, Menlo, Consolas, monospace"


# =====================================================================
# GLOBAL QSS
# =====================================================================

def build_qss(theme_name: str | None = None) -> str:
    if theme_name:
        apply_theme(theme_name)
    c = COLORS
    return f"""
    * {{
        font-family: {FONT_FAMILY};
        color: {c['text']};
        outline: none;
    }}

    QMainWindow, QWidget#Root, QDialog {{
        background-color: {c['bg']};
    }}

    /* ---------- Sidebar ---------- */
    QWidget#Sidebar {{
        background-color: {c['surface']};
        border-right: 1px solid {c['border_soft']};
    }}
    QLabel#Brand {{
        font-size: 22px;
        font-weight: 800;
        color: {c['text']};
        letter-spacing: 1px;
    }}
    QLabel#BrandSub {{
        font-size: 11px;
        color: {c['text_dim']};
        letter-spacing: 2px;
    }}

    QPushButton#NavButton {{
        text-align: left;
        padding: 11px 16px;
        border: none;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 600;
        color: {c['text_muted']};
        background: transparent;
    }}
    QPushButton#NavButton:hover {{
        background-color: {c['card']};
        color: {c['text']};
    }}
    QPushButton#NavButton:checked {{
        background-color: {c['primary_dim']};
        color: {c['primary_hi']};
    }}

    /* ---------- Sarlavhalar ---------- */
    QLabel#PageTitle {{
        font-size: 26px;
        font-weight: 800;
        color: {c['text']};
    }}
    QLabel#PageSubtitle {{
        font-size: 13px;
        color: {c['text_muted']};
    }}
    QLabel#SectionTitle {{
        font-size: 15px;
        font-weight: 700;
        color: {c['text']};
    }}

    /* ---------- Kartochka ---------- */
    QFrame#Card {{
        background-color: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 16px;
    }}
    QFrame#StatTile {{
        background-color: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 14px;
    }}
    QLabel#StatValue {{
        font-size: 24px;
        font-weight: 800;
    }}
    QLabel#StatLabel {{
        font-size: 12px;
        color: {c['text_muted']};
    }}

    /* ---------- Kiritish maydonlari ---------- */
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 9px 12px;
        font-size: 13px;
        selection-background-color: {c['primary']};
    }}
    QPlainTextEdit, QTextEdit {{
        font-family: {MONO_FAMILY};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
    QSpinBox:focus, QComboBox:focus {{
        border: 1px solid {c['primary']};
    }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background-color: {c['card']};
        border: 1px solid {c['border']};
        selection-background-color: {c['primary_dim']};
        border-radius: 8px;
        padding: 4px;
    }}

    /* ---------- Tugmalar ---------- */
    QPushButton#Primary {{
        background-color: {c['primary']};
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 20px;
        font-size: 14px;
        font-weight: 700;
    }}
    QPushButton#Primary:hover {{ background-color: {c['primary_hi']}; }}
    QPushButton#Primary:pressed {{ background-color: {c['primary_dim']}; }}
    QPushButton#Primary:disabled {{
        background-color: {c['border']};
        color: {c['text_dim']};
    }}
    QPushButton#Ghost {{
        background-color: transparent;
        color: {c['text_muted']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 9px 18px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton#Ghost:hover {{
        border: 1px solid {c['primary']};
        color: {c['text']};
    }}
    QPushButton#ChartTool {{
        background-color: {c['surface']};
        color: {c['text_muted']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        font-size: 14px;
        padding: 0;
    }}
    QPushButton#ChartTool:hover {{
        border: 1px solid {c['primary']};
        color: {c['text']};
        background-color: {c['card_hover']};
    }}
    QPushButton#ChartTool:disabled {{
        color: {c['text_dim']};
        border: 1px solid {c['border_soft']};
    }}

    /* ---------- Jadval ---------- */
    QTableWidget {{
        background-color: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 12px;
        gridline-color: {c['border_soft']};
        font-size: 13px;
    }}
    QHeaderView::section {{
        background-color: {c['surface']};
        color: {c['text_muted']};
        padding: 8px 10px;
        border: none;
        border-bottom: 1px solid {c['border']};
        font-weight: 700;
    }}
    QTableWidget::item {{ padding: 6px 10px; }}
    QTableWidget::item:selected {{
        background-color: {c['primary_dim']};
        color: {c['text']};
    }}

    /* ---------- Scrollbar ---------- */
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']}; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c['text_dim']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar:horizontal {{
        background: transparent; height: 10px; margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border']}; border-radius: 5px; min-width: 30px;
    }}

    /* ---------- Boshqalar ---------- */
    QLabel#Muted {{ color: {c['text_muted']}; font-size: 13px; }}
    QLabel#Dim {{ color: {c['text_dim']}; font-size: 12px; }}
    QLabel#Disclaimer {{
        color: {c['warning']};
        font-size: 12px;
        background-color: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.25);
        border-radius: 10px;
        padding: 10px 14px;
    }}
    QProgressBar {{
        border: none; background: {c['surface']};
        border-radius: 6px; height: 6px; text-align: center;
    }}
    QProgressBar::chunk {{ background: {c['primary']}; border-radius: 6px; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{
        background: transparent; color: {c['text_muted']};
        padding: 8px 18px; margin-right: 4px;
        border-radius: 8px; font-weight: 600; font-size: 13px;
    }}
    QTabBar::tab:selected {{ background: {c['card']}; color: {c['primary_hi']}; }}
    QToolTip {{
        background-color: {c['card']}; color: {c['text']};
        border: 1px solid {c['border']}; border-radius: 6px; padding: 6px;
    }}
    """
