"""
Theme constants for the PMO application.
Professional dark-accent color palette — v16 spacing overhaul.
"""

# ── Brand Colors ─────────────────────────────────────────────────────────────
PRIMARY       = "#1565C0"
PRIMARY_LIGHT = "#1E88E5"
PRIMARY_DARK  = "#0D47A1"
ACCENT        = "#00ACC1"
BG            = "#F0F4F8"        # slightly cooler background
BG_CARD       = "#FFFFFF"
SIDEBAR_BG    = "#1A2035"
SIDEBAR_TEXT  = "#B0BEC5"
SIDEBAR_ACTIVE= "#1E88E5"
HEADER_BG     = "#FFFFFF"
BORDER        = "#E0E7EF"
TEXT_PRIMARY  = "#1A2035"
TEXT_SECONDARY= "#607080"

# ── Status Colors ─────────────────────────────────────────────────────────────
STATUS_COLORS = {
    "Active":    "#1E88E5",
    "Completed": "#43A047",
    "Delayed":   "#E53935",
    "At Risk":   "#FB8C00",
    "On Hold":   "#8E24AA",
    "Cancelled": "#757575",
}
STATUS_BG = {
    "Active":    "#E3F2FD",
    "Completed": "#E8F5E9",
    "Delayed":   "#FFEBEE",
    "At Risk":   "#FFF3E0",
    "On Hold":   "#F3E5F5",
    "Cancelled": "#F5F5F5",
}

# ── Priority Colors ───────────────────────────────────────────────────────────
PRIORITY_COLORS = {
    "Critical": "#C62828",
    "High":     "#E53935",
    "Medium":   "#FB8C00",
    "Low":      "#43A047",
}

# ── Phase Colors ──────────────────────────────────────────────────────────────
PHASE_COLORS = {
    "Phase 1": "#5C6BC0",
    "Phase 2": "#1E88E5",
    "Phase 3": "#00ACC1",
    "Phase 4": "#43A047",
    "Phase 5": "#8E24AA",
}

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_FAMILY   = "Segoe UI"
FONT_SIZE_SM  = 9
FONT_SIZE_MD  = 11
FONT_SIZE_LG  = 13
FONT_SIZE_XL  = 18
FONT_SIZE_XXL = 24

# ── Spacing ───────────────────────────────────────────────────────────────────
RADIUS        = 8
CARD_PADDING  = 14
SIDEBAR_WIDTH = 220

# ── Scrollbar (shared snippet) ────────────────────────────────────────────────
SCROLLBAR_QSS = """
    QScrollBar:vertical {
        background: #EEF2F7; width: 6px; border-radius: 3px; margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #C5D0DC; border-radius: 3px; min-height: 24px;
    }
    QScrollBar::handle:vertical:hover { background: #A0B4C4; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar:horizontal {
        background: #EEF2F7; height: 6px; border-radius: 3px; margin: 0;
    }
    QScrollBar::handle:horizontal {
        background: #C5D0DC; border-radius: 3px; min-width: 24px;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
"""

# ── Table styles ──────────────────────────────────────────────────────────────
TABLE_QSS = f"""
    QTableWidget {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: {RADIUS}px;
        gridline-color: transparent;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_SM}pt;
        color: {TEXT_PRIMARY};
        selection-background-color: #E3F2FD;
        selection-color: {TEXT_PRIMARY};
    }}
    QTableWidget::item {{
        padding: 6px 10px;
        border-bottom: 1px solid {BORDER};
    }}
    QTableWidget::item:alternate {{
        background-color: #F8FAFC;
    }}
    QTableWidget::item:selected {{
        background-color: #DBEAFE;
        color: {PRIMARY};
    }}
    QHeaderView::section {{
        background-color: #1E293B;
        color: #E2E8F0;
        padding: 8px 10px;
        font-size: {FONT_SIZE_SM}pt;
        font-weight: bold;
        border: none;
        border-right: 1px solid #334155;
    }}
    QHeaderView::section:first {{
        border-top-left-radius: {RADIUS}px;
    }}
    QHeaderView::section:last {{
        border-top-right-radius: {RADIUS}px;
        border-right: none;
    }}
    {SCROLLBAR_QSS}
"""

# ── Input styles ──────────────────────────────────────────────────────────────
INPUT_QSS = f"""
    QLineEdit, QComboBox, QDateEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: {RADIUS}px;
        padding: 6px 10px;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_SM}pt;
        color: {TEXT_PRIMARY};
        min-height: 28px;
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 2px solid {PRIMARY_LIGHT};
        background-color: #FAFCFF;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background: white;
        border: 1px solid {BORDER};
        border-radius: 4px;
        selection-background-color: #DBEAFE;
        padding: 2px;
    }}
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        width: 18px;
        border: none;
        background: transparent;
    }}
"""

# ── Buttons ───────────────────────────────────────────────────────────────────
BUTTON_PRIMARY_QSS = f"""
    QPushButton {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 {PRIMARY_LIGHT}, stop:1 {PRIMARY});
        color: white;
        border: none;
        border-radius: {RADIUS}px;
        padding: 7px 18px;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_SM}pt;
        font-weight: bold;
        min-height: 30px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 #42A5F5, stop:1 {PRIMARY_LIGHT});
    }}
    QPushButton:pressed {{ background-color: {PRIMARY_DARK}; }}
    QPushButton:disabled {{ background-color: #B0BEC5; color: #ECEFF1; }}
"""

BUTTON_SECONDARY_QSS = f"""
    QPushButton {{
        background-color: transparent;
        color: {PRIMARY};
        border: 1.5px solid {PRIMARY};
        border-radius: {RADIUS}px;
        padding: 6px 16px;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_SM}pt;
        min-height: 28px;
    }}
    QPushButton:hover {{ background-color: #EFF6FF; }}
    QPushButton:pressed {{ background-color: #DBEAFE; }}
"""

BUTTON_DANGER_QSS = f"""
    QPushButton {{
        background-color: #E53935;
        color: white;
        border: none;
        border-radius: {RADIUS}px;
        padding: 7px 16px;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_SM}pt;
        min-height: 28px;
    }}
    QPushButton:hover {{ background-color: #C62828; }}
"""

CARD_QSS = f"""
    QFrame {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: {RADIUS}px;
    }}
"""

APP_QSS = f"""
    QMainWindow, QWidget {{
        background-color: {BG};
        font-family: {FONT_FAMILY};
        color: {TEXT_PRIMARY};
    }}
    QLabel {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY};
    }}
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QSplitter::handle {{ background: {BORDER}; }}

    /* ── Tab bar ── */
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        border-top: none;
        background: {BG_CARD};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_SECONDARY};
        padding: 7px 16px;
        border: none;
        border-bottom: 2px solid transparent;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_SM}pt;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        color: {PRIMARY};
        border-bottom: 2px solid {PRIMARY};
        font-weight: bold;
        background: {BG_CARD};
    }}
    QTabBar::tab:hover:!selected {{ color: {PRIMARY}; }}

    /* ── GroupBox ── */
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: {RADIUS}px;
        margin-top: 10px;
        padding: 10px 10px 6px 10px;
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_SM}pt;
        font-weight: bold;
        color: {TEXT_PRIMARY};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: {PRIMARY};
    }}

    /* ── Tooltip ── */
    QToolTip {{
        background-color: #1E293B;
        color: #F1F5F9;
        border: none;
        padding: 4px 8px;
        border-radius: 4px;
        font-family: {FONT_FAMILY};
        font-size: 8pt;
    }}

    /* ── Scrollbars ── */
    {SCROLLBAR_QSS}
"""
