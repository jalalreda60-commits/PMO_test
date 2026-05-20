"""
Reusable UI widgets used throughout the application.
"""
from PySide6.QtWidgets import (
    QLabel, QFrame, QHBoxLayout, QVBoxLayout, QPushButton,
    QWidget, QProgressBar, QSizePolicy, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from app.utils.theme import *


def make_label(text: str, size: int = FONT_SIZE_MD, bold: bool = False,
               color: str = TEXT_PRIMARY) -> QLabel:
    lbl = QLabel(text)
    font = QFont(FONT_FAMILY, size)
    font.setBold(bold)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


def add_shadow(widget: QWidget, blur: int = 8, offset: int = 1,
               color: str = "#0000000E"):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, offset)
    shadow.setColor(QColor(color))
    widget.setGraphicsEffect(shadow)


# ─────────────────────────────────────────────────────────────────────────────
# KPI Card
# ─────────────────────────────────────────────────────────────────────────────

class KpiCard(QFrame):
    def __init__(self, title: str, value: str, icon: str = "", accent: str = PRIMARY,
                 subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("KpiCard")
        self.setStyleSheet(f"""
            #KpiCard {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: {RADIUS}px;
                border-left: 3px solid {accent};
            }}
        """)
        self.setFixedHeight(76)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(1)

        # Title + icon on same row
        title_row = QHBoxLayout(); title_row.setSpacing(4)
        title_lbl = make_label(title, FONT_SIZE_SM - 1, color=TEXT_SECONDARY)
        title_lbl.setWordWrap(True)
        title_row.addWidget(title_lbl, 1)
        if icon:
            icon_lbl = make_label(icon, 12, color=accent)
            icon_lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
            title_row.addWidget(icon_lbl, 0)
        lay.addLayout(title_row)

        # Value — large bold coloured (same as Total Budget style)
        self.value_lbl = make_label(value, FONT_SIZE_LG + 2, bold=True, color=accent)
        lay.addWidget(self.value_lbl)

        # Subtitle — small grey
        if subtitle:
            sub = make_label(subtitle, 7, color=TEXT_SECONDARY)
            lay.addWidget(sub)

    def set_value(self, value: str):
        self.value_lbl.setText(value)


# ─────────────────────────────────────────────────────────────────────────────
# Status Badge
# ─────────────────────────────────────────────────────────────────────────────

class StatusBadge(QLabel):
    def __init__(self, status: str, parent=None):
        super().__init__(status, parent)
        self.set_status(status)
        self.setFixedHeight(22)
        self.setAlignment(Qt.AlignCenter)

    def set_status(self, status: str):
        self.setText(status)
        color = STATUS_COLORS.get(status, "#607D8B")
        bg = STATUS_BG.get(status, "#ECEFF1")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {color};
                border-radius: 11px;
                padding: 2px 10px;
                font-size: 8pt;
                font-weight: bold;
                font-family: {FONT_FAMILY};
            }}
        """)


# ─────────────────────────────────────────────────────────────────────────────
# Section Header
# ─────────────────────────────────────────────────────────────────────────────

class SectionHeader(QWidget):
    def __init__(self, title: str, btn_label: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        title_lbl = make_label(title, FONT_SIZE_LG, bold=True)
        lay.addWidget(title_lbl)
        lay.addStretch()
        self.btn = None
        if btn_label:
            self.btn = QPushButton(btn_label)
            self.btn.setStyleSheet(BUTTON_PRIMARY_QSS)
            lay.addWidget(self.btn)


# ─────────────────────────────────────────────────────────────────────────────
# Divider
# ─────────────────────────────────────────────────────────────────────────────

class HDivider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setStyleSheet(f"color: {BORDER}; background: {BORDER};")
        self.setFixedHeight(1)


# ─────────────────────────────────────────────────────────────────────────────
# Progress Bar (styled)
# ─────────────────────────────────────────────────────────────────────────────

class StyledProgressBar(QProgressBar):
    def __init__(self, value: int = 0, color: str = PRIMARY, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(int(value))
        self.setTextVisible(True)
        self.setFixedHeight(20)
        self.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 10px;
                background-color: {BORDER};
                text-align: center;
                color: {TEXT_PRIMARY};
                font-size: 8pt;
                font-family: {FONT_FAMILY};
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 10px;
            }}
        """)


# ─────────────────────────────────────────────────────────────────────────────
# Card Frame
# ─────────────────────────────────────────────────────────────────────────────

class CardFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardFrame")
        self.setStyleSheet(f"""
            #CardFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: {RADIUS}px;
            }}
        """)
        # Shadow removed — border gives depth without GPU compositing cost
