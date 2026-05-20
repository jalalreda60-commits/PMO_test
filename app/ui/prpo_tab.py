"""
PR/PO Tab — tracks Purchase Requisitions and Purchase Orders per project.
Mirrors the "Pre-conditioning Tracking" Excel structure:
  RFQ section  → Reception of 3 quotations
  PR section   → PR creation & approval
  PO section   → PO submission
  Reception    → Item reception tracking
"""
from __future__ import annotations
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QDoubleSpinBox, QComboBox, QDateEdit, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QFrame, QSizePolicy, QTabBar, QSplitter,
    QGridLayout, QGroupBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor

from app.utils.theme import *
from app.utils.widgets import make_label, add_shadow, CardFrame, KpiCard
from app.models.project_model import (
    get_prpo_entries, upsert_prpo_entry, delete_prpo_entry
)

# ── Status options ────────────────────────────────────────────────────────────
RFQ_STATUSES   = ["Pending", "Submitted", "Received on time", "Received with delay", "Overdue", "Cancelled"]
PR_STATUSES    = ["Pending", "Validated", "Rejected", "In Approval"]
REC_STATUSES   = ["Pending", "Received on time", "Received with delay", "Overdue", "Ongoing"]

# Status → (background, foreground)
STATUS_STYLE = {
    "Validated":          ("#C8E6C9", "#1B5E20"),
    "Received on time":   ("#C8E6C9", "#1B5E20"),
    "Pending":            ("#FFF9C4", "#F57F17"),
    "In Approval":        ("#FFF9C4", "#F57F17"),
    "Submitted":          ("#E3F2FD", "#1565C0"),
    "Ongoing":            ("#E3F2FD", "#1565C0"),
    "Received with delay":("#FFCDD2", "#B71C1C"),
    "Overdue":            ("#FFCDD2", "#B71C1C"),
    "Rejected":           ("#FFCDD2", "#B71C1C"),
    "Cancelled":          ("#ECEFF1", "#607D8B"),
}


def _status_badge(text: str) -> QLabel:
    lbl = QLabel(f"  {text}  ")
    bg, fg = STATUS_STYLE.get(text, ("#F5F5F5", "#424242"))
    lbl.setStyleSheet(
        f"background:{bg};color:{fg};border-radius:8px;"
        f"padding:2px 6px;font-size:7pt;font-weight:bold;font-family:{FONT_FAMILY};"
    )
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        d = datetime.date.fromisoformat(iso)
        return d.strftime("%d/%m/%Y")
    except Exception:
        return iso or "—"


# ══════════════════════════════════════════════════════════════════════════════
# Entry Form Dialog
# ══════════════════════════════════════════════════════════════════════════════
class PRPOForm(QDialog):
    def __init__(self, project_id: str, entry: dict = None, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self._entry = entry or {}
        self.setWindowTitle("Edit PR/PO Entry" if entry else "Add PR/PO Entry")
        self.setMinimumWidth(580)
        self.setStyleSheet(f"background:{BG_CARD};color:{TEXT_PRIMARY};font-family:{FONT_FAMILY};")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Scroll area for form ───────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)
        scroll.setWidget(inner)
        root.addWidget(scroll)

        SEC = (f"background:#F0F4F8;border-bottom:1px solid {BORDER};"
               f"padding:6px 0;font-size:8pt;font-weight:bold;color:{TEXT_SECONDARY};letter-spacing:1px;")

        # ── Item info ─────────────────────────────────────────────────────
        lay.addWidget(self._sec("  ITEM", SEC))
        f0 = QFormLayout(); f0.setSpacing(10); f0.setLabelAlignment(Qt.AlignRight)
        self.item_edit = QLineEdit(self._entry.get("item", ""))
        self.item_edit.setStyleSheet(INPUT_QSS)
        self.item_edit.setPlaceholderText("Item / equipment description")
        f0.addRow(_lbl("Item"), self.item_edit)

        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0, 99_999_999); self.cost_spin.setDecimals(2)
        self.cost_spin.setGroupSeparatorShown(True); self.cost_spin.setPrefix("€ ")
        self.cost_spin.setStyleSheet(INPUT_QSS)
        self.cost_spin.setValue(float(self._entry.get("cost") or 0))
        f0.addRow(_lbl("Cost (€)"), self.cost_spin)

        self.io_edit = QLineEdit(self._entry.get("internal_order", "") or "")
        self.io_edit.setStyleSheet(INPUT_QSS)
        f0.addRow(_lbl("Internal Order"), self.io_edit)

        self.supplier_edit = QLineEdit(self._entry.get("supplier", "") or "")
        self.supplier_edit.setStyleSheet(INPUT_QSS)
        f0.addRow(_lbl("Supplier"), self.supplier_edit)

        self.contact_edit = QLineEdit(self._entry.get("contact", "") or "")
        self.contact_edit.setStyleSheet(INPUT_QSS)
        f0.addRow(_lbl("Contact"), self.contact_edit)
        lay.addLayout(f0)

        # ── RFQ section ───────────────────────────────────────────────────
        lay.addWidget(self._sec("  📋 RFQ — RECEPTION OF 3 QUOTATIONS", SEC))
        f1 = QFormLayout(); f1.setSpacing(10); f1.setLabelAlignment(Qt.AlignRight)

        self.rfq_sub_date  = _date_edit(self._entry.get("rfq_submitted_date"))
        self.rfq_fore_date = _date_edit(self._entry.get("rfq_forecasted_date"))
        self.rfq_rec_date  = _date_edit(self._entry.get("rfq_reception_date"))
        self.rfq_status    = _combo(RFQ_STATUSES, self._entry.get("rfq_status", "Pending"))

        f1.addRow(_lbl("Submitted Request Date"), self.rfq_sub_date)
        f1.addRow(_lbl("Forecasted Date"),         self.rfq_fore_date)
        f1.addRow(_lbl("Reception Date"),          self.rfq_rec_date)
        f1.addRow(_lbl("RFQ Status"),              self.rfq_status)
        lay.addLayout(f1)

        # ── PR section ────────────────────────────────────────────────────
        lay.addWidget(self._sec("  🧾 PR — CREATION OF PR", SEC))
        f2 = QFormLayout(); f2.setSpacing(10); f2.setLabelAlignment(Qt.AlignRight)

        self.pr_nbr      = QLineEdit(self._entry.get("pr_number", "") or "")
        self.pr_nbr.setStyleSheet(INPUT_QSS)
        self.pr_flow     = QLineEdit(self._entry.get("pr_approval_flow", "") or "")
        self.pr_flow.setStyleSheet(INPUT_QSS)
        self.pr_status   = _combo(PR_STATUSES, self._entry.get("pr_status", "Pending"))
        self.pr_val_date = _date_edit(self._entry.get("pr_validation_date"))

        f2.addRow(_lbl("PR Number"),         self.pr_nbr)
        f2.addRow(_lbl("Approval Flow"),     self.pr_flow)
        f2.addRow(_lbl("PR Status"),         self.pr_status)
        f2.addRow(_lbl("Validation Date"),   self.pr_val_date)
        lay.addLayout(f2)

        # ── PO section ────────────────────────────────────────────────────
        lay.addWidget(self._sec("  📦 PO — SUBMISSION", SEC))
        f3 = QFormLayout(); f3.setSpacing(10); f3.setLabelAlignment(Qt.AlignRight)

        self.po_fore_date = _date_edit(self._entry.get("po_forecasted_date"))
        self.po_sub_date  = _date_edit(self._entry.get("po_submission_date"))
        self.po_nbr       = QLineEdit(self._entry.get("po_number", "") or "")
        self.po_nbr.setStyleSheet(INPUT_QSS)
        self.po_lt        = QDoubleSpinBox()
        self.po_lt.setRange(0, 999); self.po_lt.setDecimals(1); self.po_lt.setSuffix(" weeks")
        self.po_lt.setStyleSheet(INPUT_QSS)
        self.po_lt.setValue(float(self._entry.get("po_lead_time_weeks") or 0))

        f3.addRow(_lbl("Forecasted Date"),   self.po_fore_date)
        f3.addRow(_lbl("Submission Date"),   self.po_sub_date)
        f3.addRow(_lbl("PO Number"),         self.po_nbr)
        f3.addRow(_lbl("Lead Time (weeks)"), self.po_lt)
        lay.addLayout(f3)

        # ── Reception section ─────────────────────────────────────────────
        lay.addWidget(self._sec("  📥 RECEPTION", SEC))
        f4 = QFormLayout(); f4.setSpacing(10); f4.setLabelAlignment(Qt.AlignRight)

        self.rec_fore_date = _date_edit(self._entry.get("reception_forecasted"))
        self.rec_date      = _date_edit(self._entry.get("reception_date"))
        self.rec_status    = _combo(REC_STATUSES, self._entry.get("reception_status", "Pending"))

        f4.addRow(_lbl("Forecasted Date"), self.rec_fore_date)
        f4.addRow(_lbl("Reception Date"),  self.rec_date)
        f4.addRow(_lbl("Status"),          self.rec_status)
        lay.addLayout(f4)

        # ── Buttons ───────────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setStyleSheet(BUTTON_PRIMARY_QSS)
        btns.button(QDialogButtonBox.Cancel).setStyleSheet(BUTTON_SECONDARY_QSS)
        root.addWidget(btns)
        root.setContentsMargins(0, 0, 0, 8)

    def _sec(self, text, style):
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(style)
        return lbl

    def get_values(self) -> dict:
        def _iso(de: QDateEdit):
            if de.date() == QDate(2000, 1, 1):
                return None
            return de.date().toString("yyyy-MM-dd")

        return {
            "project_id":          self.project_id,
            "item":                self.item_edit.text().strip(),
            "cost":                self.cost_spin.value(),
            "internal_order":      self.io_edit.text().strip(),
            "supplier":            self.supplier_edit.text().strip(),
            "contact":             self.contact_edit.text().strip(),
            "rfq_submitted_date":  _iso(self.rfq_sub_date),
            "rfq_forecasted_date": _iso(self.rfq_fore_date),
            "rfq_reception_date":  _iso(self.rfq_rec_date),
            "rfq_status":          self.rfq_status.currentText(),
            "pr_number":           self.pr_nbr.text().strip(),
            "pr_approval_flow":    self.pr_flow.text().strip(),
            "pr_status":           self.pr_status.currentText(),
            "pr_validation_date":  _iso(self.pr_val_date),
            "po_forecasted_date":  _iso(self.po_fore_date),
            "po_submission_date":  _iso(self.po_sub_date),
            "po_number":           self.po_nbr.text().strip(),
            "po_lead_time_weeks":  self.po_lt.value() or None,
            "reception_forecasted":_iso(self.rec_fore_date),
            "reception_date":      _iso(self.rec_date),
            "reception_status":    self.rec_status.currentText(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# PR/PO Tab Widget
# ══════════════════════════════════════════════════════════════════════════════
class PRPOTab(QWidget):
    def __init__(self, project_id: str, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.addWidget(make_label("PR / PO Tracking", FONT_SIZE_LG, bold=True))
        hdr.addStretch()
        add_btn = QPushButton("＋ Add Entry")
        add_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        add_btn.setFixedHeight(32)
        add_btn.clicked.connect(self._add)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        lay.addWidget(make_label(
            "Track Purchase Requisitions and Purchase Orders — from RFQ reception through "
            "PR creation, PO submission, and item delivery.",
            FONT_SIZE_SM, color=TEXT_SECONDARY))

        # ── KPI summary strip ─────────────────────────────────────────────
        self._kpi_card = QWidget()
        self._kpi_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._kpi_lay = QHBoxLayout(self._kpi_card)
        self._kpi_lay.setContentsMargins(0, 0, 0, 0)
        self._kpi_lay.setSpacing(10)
        lay.addWidget(self._kpi_card)

        # ── Main table ────────────────────────────────────────────────────
        self.tbl = QTableWidget()
        self.tbl.setStyleSheet(TABLE_QSS)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setShowGrid(False)
        self.tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        cols = [
            "Item", "Supplier", "Cost (€)",
            # RFQ
            "RFQ Submitted", "RFQ Forecast", "RFQ Received", "RFQ Status",
            # PR
            "PR Nbr", "PR Status", "PR Validated",
            # PO
            "PO Forecast", "PO Submitted", "PO Nbr", "LT (W)",
            # Reception
            "Rec. Forecast", "Rec. Date", "Reception Status",
            # Actions
            "",
        ]
        self.tbl.setColumnCount(len(cols))
        self.tbl.setHorizontalHeaderLabels(cols)

        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)   # Item stretches
        hh.setSectionResizeMode(len(cols)-1, QHeaderView.Fixed)
        self.tbl.setColumnWidth(len(cols)-1, 68)

        lay.addWidget(self.tbl)

        self._refresh()

    # ── Data ──────────────────────────────────────────────────────────────
    def _refresh(self):
        entries = get_prpo_entries(self.project_id)
        self._rebuild_kpis(entries)
        self._rebuild_table(entries)

    def _rebuild_kpis(self, entries):
        # Clear existing KPI cards
        while self._kpi_lay.count():
            item = self._kpi_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total   = len(entries)
        total_cost = sum(float(e.get("cost") or 0) for e in entries)
        pr_done = sum(1 for e in entries if e.get("pr_status") == "Validated")
        po_done = sum(1 for e in entries if e.get("po_number"))
        rec_done= sum(1 for e in entries if e.get("reception_date"))
        overdue = sum(1 for e in entries if "overdue" in (e.get("rfq_status") or "").lower()
                      or "overdue" in (e.get("reception_status") or "").lower())

        def _fmt(v):
            if v >= 1_000_000: return f"€{v/1_000_000:.2f}M"
            if v >= 1_000:     return f"€{v/1_000:.0f}K"
            return f"€{v:.0f}"

        kpi_data = [
            ("Total Items",    str(total),      "📋", PRIMARY),
            ("Total Cost",     _fmt(total_cost),"€",  ACCENT),
            ("PR Validated",   str(pr_done),    "✅", STATUS_COLORS["Completed"]),
            ("PO Submitted",   str(po_done),    "📦", STATUS_COLORS["Active"]),
            ("Items Received", str(rec_done),   "📥", "#43A047"),
            ("Overdue",        str(overdue),    "⚠",  "#E53935"),
        ]
        for title, value, icon, color in kpi_data:
            card = KpiCard(title, value, icon, color)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._kpi_lay.addWidget(card, 1)

    def _rebuild_table(self, entries):
        self.tbl.setRowCount(len(entries))

        for ri, e in enumerate(entries):
            self.tbl.setRowHeight(ri, 38)

            def _cell(text, bold=False, color=None, align=Qt.AlignLeft | Qt.AlignVCenter):
                item = QTableWidgetItem(str(text) if text else "—")
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setTextAlignment(align)
                if bold:
                    item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
                if color:
                    item.setForeground(QColor(color))
                return item

            # Col 0 – Item
            self.tbl.setItem(ri, 0, _cell(e.get("item"), bold=True, color=TEXT_PRIMARY))
            # Col 1 – Supplier
            self.tbl.setItem(ri, 1, _cell(e.get("supplier"), color=PRIMARY))
            # Col 2 – Cost
            cost = float(e.get("cost") or 0)
            cost_txt = f"€{cost:,.0f}" if cost else "—"
            self.tbl.setItem(ri, 2, _cell(cost_txt, bold=True,
                             color="#E53935" if cost > 10000 else TEXT_PRIMARY,
                             align=Qt.AlignRight | Qt.AlignVCenter))

            # RFQ columns 3-6
            self.tbl.setItem(ri, 3, _cell(_fmt_date(e.get("rfq_submitted_date")), align=Qt.AlignCenter))
            self.tbl.setItem(ri, 4, _cell(_fmt_date(e.get("rfq_forecasted_date")), align=Qt.AlignCenter))
            self.tbl.setItem(ri, 5, _cell(_fmt_date(e.get("rfq_reception_date")), align=Qt.AlignCenter))
            # RFQ Status badge
            rfq_s = e.get("rfq_status", "Pending")
            self._set_badge(ri, 6, rfq_s)

            # PR columns 7-9
            self.tbl.setItem(ri, 7, _cell(e.get("pr_number"), align=Qt.AlignCenter))
            pr_s = e.get("pr_status", "Pending")
            self._set_badge(ri, 8, pr_s)
            self.tbl.setItem(ri, 9, _cell(_fmt_date(e.get("pr_validation_date")), align=Qt.AlignCenter))

            # PO columns 10-13
            self.tbl.setItem(ri, 10, _cell(_fmt_date(e.get("po_forecasted_date")), align=Qt.AlignCenter))
            self.tbl.setItem(ri, 11, _cell(_fmt_date(e.get("po_submission_date")), align=Qt.AlignCenter))
            self.tbl.setItem(ri, 12, _cell(e.get("po_number"), align=Qt.AlignCenter))
            lt = e.get("po_lead_time_weeks")
            self.tbl.setItem(ri, 13, _cell(f"{lt:.0f}w" if lt else "—", align=Qt.AlignCenter))

            # Reception columns 14-16
            self.tbl.setItem(ri, 14, _cell(_fmt_date(e.get("reception_forecasted")), align=Qt.AlignCenter))
            self.tbl.setItem(ri, 15, _cell(_fmt_date(e.get("reception_date")), align=Qt.AlignCenter))
            rec_s = e.get("reception_status", "Pending")
            self._set_badge(ri, 16, rec_s)

            # Action buttons col 17
            act_w = QWidget()
            al = QHBoxLayout(act_w)
            al.setContentsMargins(2, 2, 2, 2); al.setSpacing(3)

            edit_btn = QPushButton("✏")
            edit_btn.setFixedSize(28, 26)
            edit_btn.setStyleSheet(
                f"QPushButton{{background:{PRIMARY};color:white;border:none;"
                f"border-radius:5px;font-size:9pt;}}"
                f"QPushButton:hover{{background:#0D47A1;}}"
            )
            edit_btn.clicked.connect(lambda _, en=e: self._edit(en))

            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(28, 26)
            del_btn.setStyleSheet(
                "QPushButton{background:#E53935;color:white;border:none;"
                "border-radius:5px;font-size:9pt;}"
                "QPushButton:hover{background:#B71C1C;}"
            )
            del_btn.clicked.connect(lambda _, eid=e["id"]: self._delete(eid))

            al.addWidget(edit_btn)
            al.addWidget(del_btn)
            self.tbl.setCellWidget(ri, 17, act_w)

    def _set_badge(self, row, col, status):
        bg, fg = STATUS_STYLE.get(status, ("#F5F5F5", "#424242"))
        lbl = QLabel(f"  {status}  ")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:8px;"
            f"font-size:7pt;font-weight:bold;font-family:{FONT_FAMILY};"
        )
        cell_w = QWidget()
        cell_l = QHBoxLayout(cell_w)
        cell_l.setContentsMargins(3, 2, 3, 2)
        cell_l.addWidget(lbl)
        self.tbl.setCellWidget(row, col, cell_w)

    # ── CRUD ──────────────────────────────────────────────────────────────
    def _add(self):
        dlg = PRPOForm(self.project_id, parent=self)
        if dlg.exec():
            upsert_prpo_entry(dlg.get_values())
            self._refresh()

    def _edit(self, entry):
        dlg = PRPOForm(self.project_id, entry=entry, parent=self)
        if dlg.exec():
            data = dlg.get_values()
            data["id"] = entry["id"]
            upsert_prpo_entry(data)
            self._refresh()

    def _delete(self, entry_id):
        if QMessageBox.question(
            self, "Delete", "Delete this PR/PO entry?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            delete_prpo_entry(entry_id)
            self._refresh()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM - 1))
    l.setStyleSheet(f"color:{TEXT_SECONDARY};background:transparent;")
    return l


def _date_edit(iso_val: str | None) -> QDateEdit:
    de = QDateEdit()
    de.setCalendarPopup(True)
    de.setDisplayFormat("dd/MM/yyyy")
    de.setStyleSheet(INPUT_QSS)
    if iso_val:
        try:
            d = datetime.date.fromisoformat(iso_val)
            de.setDate(QDate(d.year, d.month, d.day))
        except Exception:
            de.setDate(QDate(2000, 1, 1))
    else:
        de.setDate(QDate(2000, 1, 1))
    return de


def _combo(options: list, current: str = "") -> QComboBox:
    cb = QComboBox()
    cb.setStyleSheet(INPUT_QSS)
    cb.addItems(options)
    if current in options:
        cb.setCurrentText(current)
    return cb
