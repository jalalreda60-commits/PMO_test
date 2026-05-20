"""
R@R (Run @ Rate) Tab — embedded inside ProjectDetailView.
Features:
  - Plan R@R events per Ref
  - Fields: Ref, Planned Week, Shift, 1st Score, Updated Score
  - 1st Score feeds KPI dashboard immediately upon entry (avg per month)
  - 🔒 Lock freezes the 1st Score permanently
"""
from __future__ import annotations
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QDialog, QDialogButtonBox, QFormLayout,
    QComboBox, QDoubleSpinBox, QLineEdit, QMessageBox, QGridLayout,
    QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from app.utils.theme import *
from app.utils.widgets import make_label, add_shadow
from app.models.project_model import (
    get_rar_entries, upsert_rar_entry, delete_rar_entry, lock_rar_1st_score
)

SHIFTS = ["06:00 – 14:00", "14:00 – 22:00", "22:00 – 06:00"]
MONTHS_SHORT = ["Jan","Feb","Mar","Apr","May","Jun",
                "Jul","Aug","Sep","Oct","Nov","Dec"]


def _week_options():
    """Generate week options for the current year."""
    opts = []
    year = datetime.date.today().year
    for w in range(1, 53):
        opts.append(f"WK{w:02d}-{year}")
    for w in range(1, 10):
        opts.append(f"WK{w:02d}-{year+1}")
    return opts


# ── RAG badge helper ──────────────────────────────────────────────────────────
def _score_badge(score, target=90):
    if score is None:
        return "—", "#F5F7FA", TEXT_SECONDARY
    pct = score
    if pct >= target:
        return f"{pct:.1f}", "#C8E6C9", "#1B5E20"
    elif pct >= target * 0.8:
        return f"{pct:.1f}", "#FFF9C4", "#F57F17"
    else:
        return f"{pct:.1f}", "#FFCDD2", "#B71C1C"


# ══════════════════════════════════════════════════════════════════════════════
# R@R Entry Form Dialog
# ══════════════════════════════════════════════════════════════════════════════
class RaRForm(QDialog):
    def __init__(self, project_id, ref_names: list[str], entry=None, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.ref_names  = ref_names
        self._entry     = entry or {}
        self._locked    = bool(entry and entry.get("score_1st_locked"))
        self.setWindowTitle("Edit R@R Entry" if entry else "Add R@R Entry")
        self.setMinimumWidth(480)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14); lay.setContentsMargins(24, 20, 24, 20)

        # Header
        hdr_lbl = make_label("R@R (Run @ Rate) Entry", FONT_SIZE_MD, bold=True)
        lay.addWidget(hdr_lbl)

        form = QFormLayout(); form.setSpacing(10); form.setLabelAlignment(Qt.AlignRight)

        # Reference
        self.ref_combo = QComboBox(); self.ref_combo.setStyleSheet(INPUT_QSS)
        for r in self.ref_names:
            self.ref_combo.addItem(r)
        if self._entry.get("ref_name") in self.ref_names:
            self.ref_combo.setCurrentText(self._entry["ref_name"])
        form.addRow(_lbl("Reference (Ref)"), self.ref_combo)

        # Planned Week
        self.week_combo = QComboBox(); self.week_combo.setStyleSheet(INPUT_QSS)
        self.week_combo.setEditable(True)
        for w in _week_options():
            self.week_combo.addItem(w)
        if self._entry.get("planned_week"):
            self.week_combo.setCurrentText(self._entry["planned_week"])
        form.addRow(_lbl("Planned Week"), self.week_combo)

        # Shift
        self.shift_combo = QComboBox(); self.shift_combo.setStyleSheet(INPUT_QSS)
        self.shift_combo.addItems(SHIFTS)
        if self._entry.get("shift"):
            self.shift_combo.setCurrentText(self._entry["shift"])
        form.addRow(_lbl("Shift"), self.shift_combo)

        # 1st Score — feeds KPI as soon as a value is entered
        self.score1_sb = QDoubleSpinBox()
        self.score1_sb.setRange(-1, 100); self.score1_sb.setDecimals(1)
        self.score1_sb.setSuffix(" %"); self.score1_sb.setStyleSheet(INPUT_QSS)
        self.score1_sb.setSpecialValueText("— not set —")
        if self._entry.get("score_1st") is not None:
            self.score1_sb.setValue(float(self._entry["score_1st"]))
        else:
            self.score1_sb.setValue(-1)   # show "— not set —" for new entries
        if self._locked:
            self.score1_sb.setEnabled(False)
            self.score1_sb.setToolTip("1st Score is locked and cannot be modified.")
        form.addRow(_lbl("1st Score (R@R) ★"), self.score1_sb)

        if self._locked:
            lock_info = QLabel("🔒  Saved on "
                               f"{MONTHS_SHORT[self._entry.get('score_1st_month',1)-1]} "
                               f"{self._entry.get('score_1st_year','')}")
            lock_info.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM))
            lock_info.setStyleSheet("color:#E53935;")
            form.addRow("", lock_info)

        # Updated Score
        self.score2_sb = QDoubleSpinBox()
        self.score2_sb.setRange(0, 100); self.score2_sb.setDecimals(1)
        self.score2_sb.setSuffix(" %"); self.score2_sb.setStyleSheet(INPUT_QSS)
        if self._entry.get("score_updated") is not None:
            self.score2_sb.setValue(float(self._entry["score_updated"]))
        form.addRow(_lbl("Updated Score (After OPC)"), self.score2_sb)

        # Comment
        self.comment_edit = QLineEdit(self._entry.get("comment", ""))
        self.comment_edit.setPlaceholderText("Open points, remarks…")
        self.comment_edit.setStyleSheet(INPUT_QSS)
        form.addRow(_lbl("Comment"), self.comment_edit)

        lay.addLayout(form)

        if not self._locked and self._entry.get("id"):
            note = QLabel("ℹ  Changes to the 1st Score are saved immediately and update the KPI. "
                          "Use 🔒 Lock to freeze the score permanently.")
            note.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM))
            note.setWordWrap(True)
            note.setStyleSheet("color:#1565C0; background:#E3F2FD; padding:6px; border-radius:4px;")
            lay.addWidget(note)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setStyleSheet(BUTTON_PRIMARY_QSS)
        lay.addWidget(btns)

    def _save(self):
        # score1_sb value of -1 means "not set" (special value text)
        raw_score1 = self.score1_sb.value()
        score_1st = (
            self._entry.get("score_1st")   # keep existing when locked
            if self._locked
            else (None if raw_score1 < 0 else raw_score1)
        )
        data = {
            "id":            self._entry.get("id"),
            "project_id":    self.project_id,
            "ref_name":      self.ref_combo.currentText(),
            "planned_week":  self.week_combo.currentText(),
            "shift":         self.shift_combo.currentText(),
            "score_1st":     score_1st,
            "score_updated": self.score2_sb.value(),
            "comment":       self.comment_edit.text().strip(),
        }
        upsert_rar_entry(data)
        self.accept()


def _lbl(text):
    l = QLabel(text)
    l.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM))
    l.setStyleSheet(f"color:{TEXT_SECONDARY};")
    return l


# ══════════════════════════════════════════════════════════════════════════════
# Single R@R card
# ══════════════════════════════════════════════════════════════════════════════
class RaRCard(QFrame):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setStyleSheet(f"""
            QFrame {{
                background:{BG_CARD};
                border:1px solid {BORDER};
                border-radius:{RADIUS}px;
            }}
        """)
        add_shadow(self)
        self._build()

    def _build(self):
        lay = QGridLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        e = self.entry

        # Ref name
        ref_lbl = QLabel(e.get("ref_name", "—"))
        ref_lbl.setFont(QFont(FONT_FAMILY, FONT_SIZE_MD, QFont.Bold))
        ref_lbl.setStyleSheet(f"color:{PRIMARY};background:transparent;")
        lay.addWidget(ref_lbl, 0, 0, 1, 2)

        # Week + Shift
        lay.addWidget(make_label(f"📅 {e.get('planned_week','—')}", FONT_SIZE_SM), 1, 0)
        lay.addWidget(make_label(f"🕐 {e.get('shift','—')}", FONT_SIZE_SM), 1, 1)

        # 1st Score badge
        txt, bg, fg = _score_badge(e.get("score_1st"), 90)
        score1_lbl = QLabel(f"  1st: {txt}%  ")
        score1_lbl.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
        score1_lbl.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:8px;padding:2px 6px;"
        )
        score1_lbl.setAlignment(Qt.AlignCenter)
        lock_icon = " 🔒" if e.get("score_1st_locked") else " ✏"
        score1_lbl.setText(f"  1st: {txt}%{lock_icon}  ")
        lay.addWidget(score1_lbl, 2, 0)

        # Updated score badge
        if e.get("score_updated") is not None:
            txt2, bg2, fg2 = _score_badge(e.get("score_updated"), 90)
            score2_lbl = QLabel(f"  Updated: {txt2}%  ")
            score2_lbl.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
            score2_lbl.setStyleSheet(
                f"background:{bg2};color:{fg2};border-radius:8px;padding:2px 6px;"
            )
            score2_lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(score2_lbl, 2, 1)

        # Month label for locked score
        if e.get("score_1st_locked") and e.get("score_1st_month"):
            m = int(e["score_1st_month"])
            y = e.get("score_1st_year", "")
            month_lbl = make_label(f"Recorded: {MONTHS_SHORT[m-1]} {y}",
                                   FONT_SIZE_SM - 1, color=TEXT_SECONDARY)
            lay.addWidget(month_lbl, 3, 0, 1, 2)

        # Comment
        if e.get("comment"):
            c_lbl = make_label(e["comment"], FONT_SIZE_SM, color=TEXT_SECONDARY)
            c_lbl.setWordWrap(True)
            lay.addWidget(c_lbl, 4, 0, 1, 2)


# ══════════════════════════════════════════════════════════════════════════════
# R@R Tab Widget
# ══════════════════════════════════════════════════════════════════════════════
class RaRTab(QWidget):
    def __init__(self, project_id: str, project: dict, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.project    = project
        self._ref_names = self._parse_ref_names()
        self._build()

    def _parse_ref_names(self):
        raw = self.project.get("ref_names") or ""
        names = [n.strip() for n in raw.split("|") if n.strip()]
        if not names:
            nbr = int(self.project.get("nbr_ref", 1) or 1)
            names = [f"Ref {i+1}" for i in range(nbr)]
        return names

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.addWidget(make_label("R@R — Run @ Rate", FONT_SIZE_LG, bold=True))
        hdr.addStretch()

        add_btn = QPushButton("＋ Add R@R Entry")
        add_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        add_btn.setFixedHeight(34)
        add_btn.clicked.connect(self._add_entry)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        lay.addWidget(make_label(
            "Plan and track Run @ Rate events per reference. "
            "The 1st Score feeds the KPI dashboard immediately when entered — "
            "the monthly average is recalculated automatically. "
            "Use 🔒 Lock to freeze a score permanently.",
            FONT_SIZE_SM, color=TEXT_SECONDARY
        ))

        # ── Ref summary strip ─────────────────────────────────────────────────
        strip = QFrame()
        strip.setStyleSheet(f"background:#EEF2FF;border:1px solid #C7D2FE;"
                            f"border-radius:{RADIUS}px;")
        sl = QHBoxLayout(strip); sl.setContentsMargins(12, 8, 12, 8); sl.setSpacing(10)
        sl.addWidget(make_label("References in this project:", FONT_SIZE_SM,
                                bold=True, color="#3730A3"))
        for rn in self._ref_names:
            pill = QLabel(f"  {rn}  ")
            pill.setStyleSheet("background:#6366F1;color:white;border-radius:8px;"
                               "padding:2px 8px;font-size:8pt;font-weight:bold;")
            pill.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            sl.addWidget(pill)
        sl.addStretch()
        strip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(strip)

        # ── Scrollable cards area ─────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea{border:none;background:transparent;}
            QScrollBar:vertical{background:#F0F4F8;width:6px;border-radius:3px;}
            QScrollBar::handle:vertical{background:#C5D0DC;border-radius:3px;min-height:20px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}
        """)
        lay.addWidget(self._scroll)
        self._refresh_cards()

    def _refresh_cards(self):
        entries = get_rar_entries(self.project_id)
        container = QWidget(); container.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(container); vl.setSpacing(12); vl.setContentsMargins(0, 0, 0, 0)

        if not entries:
            empty = make_label(
                "No R@R entries yet. Click '＋ Add R@R Entry' to plan a Run @ Rate event.",
                FONT_SIZE_SM, color=TEXT_SECONDARY
            )
            empty.setAlignment(Qt.AlignCenter)
            vl.addWidget(empty)
        else:
            for e in entries:
                # Card + action buttons row
                row = QHBoxLayout(); row.setSpacing(8)
                card = RaRCard(e)
                card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                row.addWidget(card)

                # Action column
                act_col = QVBoxLayout(); act_col.setSpacing(6)

                edit_btn = QPushButton("✏ Edit")
                edit_btn.setFixedWidth(80); edit_btn.setFixedHeight(30)
                edit_btn.setStyleSheet(f"""
                    QPushButton{{background:{PRIMARY};color:white;border:none;
                    border-radius:6px;font-size:8pt;font-weight:bold;}}
                    QPushButton:hover{{background:#1565C0;}}
                """)
                edit_btn.clicked.connect(lambda _, en=e: self._edit_entry(en))
                act_col.addWidget(edit_btn)

                if not e.get("score_1st_locked") and e.get("score_1st") is not None:
                    lock_btn = QPushButton("🔒 Lock")
                    lock_btn.setFixedWidth(80); lock_btn.setFixedHeight(30)
                    lock_btn.setStyleSheet("""
                        QPushButton{background:#E65100;color:white;border:none;
                        border-radius:6px;font-size:8pt;font-weight:bold;}
                        QPushButton:hover{background:#BF360C;}
                    """)
                    lock_btn.clicked.connect(lambda _, eid=e["id"]: self._lock_score(eid))
                    act_col.addWidget(lock_btn)

                del_btn = QPushButton("🗑 Del")
                del_btn.setFixedWidth(80); del_btn.setFixedHeight(30)
                del_btn.setStyleSheet("""
                    QPushButton{background:#E53935;color:white;border:none;
                    border-radius:6px;font-size:8pt;font-weight:bold;}
                    QPushButton:hover{background:#B71C1C;}
                """)
                del_btn.clicked.connect(lambda _, eid=e["id"]: self._delete_entry(eid))
                act_col.addWidget(del_btn)

                act_col.addStretch()
                row.addLayout(act_col)

                row_w = QWidget(); row_w.setLayout(row)
                vl.addWidget(row_w)

        vl.addStretch()
        self._scroll.setWidget(container)

    def _add_entry(self):
        dlg = RaRForm(self.project_id, self._ref_names, parent=self)
        if dlg.exec():
            self._refresh_cards()

    def _edit_entry(self, entry):
        dlg = RaRForm(self.project_id, self._ref_names, entry=entry, parent=self)
        if dlg.exec():
            self._refresh_cards()

    def _lock_score(self, eid):
        if QMessageBox.question(
            self, "Lock 1st Score",
            "Lock this 1st Score permanently? It cannot be changed afterwards.\n"
            "It will be recorded for the current month in the KPI dashboard.",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            lock_rar_1st_score(eid)
            self._refresh_cards()

    def _delete_entry(self, eid):
        if QMessageBox.question(
            self, "Delete Entry", "Delete this R@R entry?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            delete_rar_entry(eid)
            self._refresh_cards()
