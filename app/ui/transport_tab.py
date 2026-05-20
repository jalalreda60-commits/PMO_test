"""
Transport Tab — tracks per-project transport expenses.
Auto-syncs to "Non-Productive Freight Cost" KPI by month.
"""
from __future__ import annotations
import datetime
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QDoubleSpinBox, QSpinBox, QComboBox, QDateEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from app.utils.theme import *
from app.utils.widgets import make_label, add_shadow
from app.models.project_model import (
    get_transport_entries, upsert_transport_entry, delete_transport_entry
)

MODES = ["Road", "Air", "Sea", "Express"]


# ══════════════════════════════════════════════════════════════════════════════
# Transport Entry Form
# ══════════════════════════════════════════════════════════════════════════════
class TransportForm(QDialog):
    def __init__(self, project_id: str, entry: dict = None, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self._entry     = entry or {}
        self.setWindowTitle("Edit Transport Entry" if entry else "Add Transport Entry")
        self.setMinimumWidth(500)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12); lay.setContentsMargins(22, 18, 22, 18)
        lay.addWidget(make_label("Transport / Freight Entry", FONT_SIZE_MD, bold=True))

        form = QFormLayout(); form.setSpacing(9); form.setLabelAlignment(Qt.AlignRight)

        self.desc_edit = QLineEdit(self._entry.get("item_desc",""))
        self.desc_edit.setPlaceholderText("e.g. Prototype mold, validation parts…")
        self.desc_edit.setStyleSheet(INPUT_QSS)
        form.addRow(_lbl("Item Description"), self.desc_edit)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999); self.qty_spin.setStyleSheet(INPUT_QSS)
        self.qty_spin.setValue(int(self._entry.get("quantity",1) or 1))
        form.addRow(_lbl("Quantity (Nbr)"), self.qty_spin)

        dim_row = QHBoxLayout(); dim_row.setSpacing(6)
        self.dim_l = _dspin(self._entry.get("dim_l")); dim_row.addWidget(QLabel("L"))
        dim_row.addWidget(self.dim_l)
        self.dim_w = _dspin(self._entry.get("dim_w")); dim_row.addWidget(QLabel("W"))
        dim_row.addWidget(self.dim_w)
        self.dim_h = _dspin(self._entry.get("dim_h")); dim_row.addWidget(QLabel("H cm"))
        dim_row.addWidget(self.dim_h)
        dim_w = QWidget(); dim_w.setLayout(dim_row)
        form.addRow(_lbl("Dimensions (L×W×H)"), dim_w)

        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0, 99999); self.weight_spin.setDecimals(2)
        self.weight_spin.setSuffix(" kg"); self.weight_spin.setStyleSheet(INPUT_QSS)
        self.weight_spin.setValue(float(self._entry.get("weight_kg") or 0))
        form.addRow(_lbl("Weight (kg)"), self.weight_spin)

        self.origin_edit = QLineEdit(self._entry.get("origin",""))
        self.origin_edit.setPlaceholderText("e.g. Tangier / Germany / China")
        self.origin_edit.setStyleSheet(INPUT_QSS)
        form.addRow(_lbl("From (Origin)"), self.origin_edit)

        self.dest_edit = QLineEdit(self._entry.get("destination",""))
        self.dest_edit.setPlaceholderText("e.g. Customer / Plant")
        self.dest_edit.setStyleSheet(INPUT_QSS)
        form.addRow(_lbl("To (Destination)"), self.dest_edit)

        self.mode_combo = QComboBox(); self.mode_combo.setStyleSheet(INPUT_QSS)
        self.mode_combo.addItems(MODES)
        if self._entry.get("transport_mode") in MODES:
            self.mode_combo.setCurrentText(self._entry["transport_mode"])
        form.addRow(_lbl("Transport Mode"), self.mode_combo)

        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0, 9_999_999); self.cost_spin.setDecimals(2)
        self.cost_spin.setGroupSeparatorShown(True)
        self.cost_spin.setPrefix("€ "); self.cost_spin.setStyleSheet(INPUT_QSS)
        self.cost_spin.setValue(float(self._entry.get("cost_eur") or 0))
        form.addRow(_lbl("Cost (€)"), self.cost_spin)

        self.pr_edit = QLineEdit(self._entry.get("pr_number",""))
        self.pr_edit.setPlaceholderText("Purchase request reference")
        self.pr_edit.setStyleSheet(INPUT_QSS)
        form.addRow(_lbl("PR Number"), self.pr_edit)

        self.date_edit = QDateEdit()
        self.date_edit.setStyleSheet(INPUT_QSS)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        if self._entry.get("entry_date"):
            try:
                d = datetime.date.fromisoformat(self._entry["entry_date"])
                self.date_edit.setDate(QDate(d.year, d.month, d.day))
            except Exception:
                self.date_edit.setDate(QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())
        form.addRow(_lbl("Entry Date"), self.date_edit)

        info = QLabel("💡 Cost will be auto-added to 'Non-Productive Freight Cost' KPI for the entry month.")
        info.setWordWrap(True)
        info.setFont(QFont(FONT_FAMILY, 7))
        info.setStyleSheet("color:#1565C0;background:#EFF6FF;padding:6px;border-radius:4px;")
        form.addRow("", info)

        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setStyleSheet(BUTTON_PRIMARY_QSS)
        lay.addWidget(btns)

    def _save(self):
        qd = self.date_edit.date()
        entry_date = f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"
        data = {
            "id":             self._entry.get("id"),
            "project_id":     self.project_id,
            "item_desc":      self.desc_edit.text().strip(),
            "quantity":       self.qty_spin.value(),
            "dim_l":          self.dim_l.value() or None,
            "dim_w":          self.dim_w.value() or None,
            "dim_h":          self.dim_h.value() or None,
            "weight_kg":      self.weight_spin.value() or None,
            "origin":         self.origin_edit.text().strip(),
            "destination":    self.dest_edit.text().strip(),
            "transport_mode": self.mode_combo.currentText(),
            "cost_eur":       self.cost_spin.value(),
            "pr_number":      self.pr_edit.text().strip(),
            "entry_date":     entry_date,
            "entry_month":    qd.month(),
            "entry_year":     qd.year(),
        }
        upsert_transport_entry(data)
        self.accept()


def _lbl(text):
    l = QLabel(text)
    l.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM - 1))
    l.setStyleSheet(f"color:{TEXT_SECONDARY};background:transparent;")
    return l

def _dspin(val=None):
    sb = QDoubleSpinBox()
    sb.setRange(0, 99999); sb.setDecimals(1)
    sb.setStyleSheet(INPUT_QSS); sb.setFixedWidth(70)
    if val is not None:
        try: sb.setValue(float(val))
        except: pass
    return sb


# ══════════════════════════════════════════════════════════════════════════════
# Transport Tab Widget
# ══════════════════════════════════════════════════════════════════════════════
class TransportTab(QWidget):
    def __init__(self, project_id: str, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self._bar_fig = None
        self._donut_fig = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(7)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        hdr.addWidget(make_label("Transport / Freight", FONT_SIZE_LG, bold=True))
        hdr.addStretch()
        add_btn = QPushButton("＋ Add Entry")
        add_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        add_btn.setFixedHeight(30)
        add_btn.clicked.connect(self._add)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        # ── Summary strip ───────────────────────────────────────────────────
        self._summary_lbl = QLabel()
        self._summary_lbl.setStyleSheet(
            f"background:#EFF6FF;border:1px solid #BFDBFE;border-radius:{RADIUS}px;"
            "padding:4px 10px;font-size:9pt;color:#1565C0;"
        )
        lay.addWidget(self._summary_lbl)

        # ── Charts row ──────────────────────────────────────────────────────
        charts_row = QHBoxLayout()
        charts_row.setSpacing(8)
        charts_row.setContentsMargins(0, 0, 0, 0)

        # Bar chart card
        bar_card = QFrame()
        bar_card.setStyleSheet(
            f"QFrame{{background:{BG_CARD};border:1px solid {BORDER};"
            f"border-radius:{RADIUS}px;}}"
        )
        bar_card_lay = QVBoxLayout(bar_card)
        bar_card_lay.setContentsMargins(10, 7, 10, 7)
        bar_card_lay.setSpacing(2)
        bar_title = QLabel("Cost per Month (€)")
        bar_title.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
        bar_title.setStyleSheet(f"color:{TEXT_PRIMARY};background:transparent;border:none;")
        bar_card_lay.addWidget(bar_title)
        self._bar_canvas_holder = QVBoxLayout()
        self._bar_canvas_holder.setContentsMargins(0, 0, 0, 0)
        bar_card_lay.addLayout(self._bar_canvas_holder)
        charts_row.addWidget(bar_card, stretch=3)

        # Donut chart card
        donut_card = QFrame()
        donut_card.setStyleSheet(
            f"QFrame{{background:{BG_CARD};border:1px solid {BORDER};"
            f"border-radius:{RADIUS}px;}}"
        )
        donut_card_lay = QVBoxLayout(donut_card)
        donut_card_lay.setContentsMargins(10, 7, 10, 7)
        donut_card_lay.setSpacing(2)
        donut_title = QLabel("Transport Type Mix")
        donut_title.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
        donut_title.setStyleSheet(f"color:{TEXT_PRIMARY};background:transparent;border:none;")
        donut_card_lay.addWidget(donut_title)
        self._donut_canvas_holder = QVBoxLayout()
        self._donut_canvas_holder.setContentsMargins(0, 0, 0, 0)
        donut_card_lay.addLayout(self._donut_canvas_holder)
        charts_row.addWidget(donut_card, stretch=2)

        lay.addLayout(charts_row)

        # ── Table ───────────────────────────────────────────────────────────
        self.tbl = QTableWidget()
        self.tbl.setStyleSheet(TABLE_QSS)
        self.tbl.setAlternatingRowColors(True)
        cols = ["Date","Item","Qty","Dims (cm)","Weight","From","To","Mode","Cost (€)","PR#","Actions"]
        self.tbl.setColumnCount(len(cols))
        self.tbl.setHorizontalHeaderLabels(cols)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setShowGrid(False)
        lay.addWidget(self.tbl)

        self._refresh()

    # ── Chart builders ───────────────────────────────────────────────────────
    def _build_bar_chart(self, monthly_costs: dict):
        if self._bar_fig is not None:
            plt.close(self._bar_fig)
            self._bar_fig = None
        while self._bar_canvas_holder.count():
            item = self._bar_canvas_holder.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        months_order = ["Jan","Feb","Mar","Apr","May","Jun",
                        "Jul","Aug","Sep","Oct","Nov","Dec"]
        labels = months_order
        values = [monthly_costs.get(i, 0.0) for i in range(1, 13)]

        fig, ax = plt.subplots(figsize=(5.5, 2.0))
        fig.patch.set_facecolor("none")
        ax.set_facecolor("none")

        bar_colors = [PRIMARY_LIGHT if v > 0 else "#D1D5DB" for v in values]
        bars = ax.bar(labels, values, color=bar_colors, width=0.6,
                      zorder=3, edgecolor="none")

        max_v = max(values) if max(values) > 0 else 1
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max_v * 0.03,
                        f"€{val:,.0f}", ha="center", va="bottom",
                        fontsize=5.2, color=PRIMARY, fontweight="bold")

        ax.set_ylim(0, max_v * 1.3)
        ax.set_ylabel("€", fontsize=6, color=TEXT_SECONDARY)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(BORDER)
        ax.spines["bottom"].set_color(BORDER)
        ax.tick_params(axis="both", labelsize=6, colors=TEXT_SECONDARY)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
        ax.grid(axis="y", color=BORDER, linewidth=0.5, zorder=0)
        fig.tight_layout(pad=0.4)

        canvas = FigureCanvas(fig)
        canvas.setFixedHeight(155)
        canvas.setStyleSheet("background:transparent;")
        self._bar_canvas_holder.addWidget(canvas)
        self._bar_fig = fig

    def _build_donut_chart(self, mode_costs: dict):
        if self._donut_fig is not None:
            plt.close(self._donut_fig)
            self._donut_fig = None
        while self._donut_canvas_holder.count():
            item = self._donut_canvas_holder.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        mode_colors_map = {
            "Road":    "#43A047",
            "Air":     "#E53935",
            "Sea":     "#1E88E5",
            "Express": "#FB8C00",
        }

        filtered = {m: v for m, v in mode_costs.items() if v > 0}
        if not filtered:
            filtered = {"No data": 1.0}
            colors = ["#E0E7EF"]
            labels = ["No data"]
            explode = [0]
        else:
            labels = list(filtered.keys())
            colors = [mode_colors_map.get(m, PRIMARY) for m in labels]
            explode = [0.03] * len(labels)

        values = list(filtered.values())
        total = sum(v for m, v in mode_costs.items() if v > 0)

        fig, ax = plt.subplots(figsize=(2.8, 2.0))
        fig.patch.set_facecolor("none")
        ax.set_facecolor("none")

        wedges, texts, autotexts = ax.pie(
            values,
            labels=None,
            colors=colors,
            explode=explode,
            autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
            pctdistance=0.75,
            startangle=90,
            wedgeprops=dict(width=0.52, edgecolor="white", linewidth=1.5),
        )
        for at in autotexts:
            at.set_fontsize(6)
            at.set_color("white")
            at.set_fontweight("bold")

        if total > 0 and "No data" not in filtered:
            ax.text(0, 0, f"€{total:,.0f}", ha="center", va="center",
                    fontsize=6, fontweight="bold", color=TEXT_PRIMARY)

        legend_handles = [
            plt.Line2D([0], [0], marker="o", color="w",
                       markerfacecolor=c, markersize=7, label=l)
            for l, c in zip(labels, colors) if l != "No data"
        ]
        if legend_handles:
            ax.legend(handles=legend_handles, loc="lower center",
                      bbox_to_anchor=(0.5, -0.18), ncol=2,
                      fontsize=5.5, frameon=False,
                      labelcolor=TEXT_SECONDARY)

        ax.set_aspect("equal")
        fig.tight_layout(pad=0.3)

        canvas = FigureCanvas(fig)
        canvas.setFixedHeight(155)
        canvas.setStyleSheet("background:transparent;")
        self._donut_canvas_holder.addWidget(canvas)
        self._donut_fig = fig

    # ── Refresh ──────────────────────────────────────────────────────────────
    def _refresh(self):
        entries = get_transport_entries(self.project_id)
        self.tbl.setRowCount(len(entries))
        total = 0.0
        mode_counts: dict = {}
        mode_costs: dict = defaultdict(float)
        monthly_costs: dict = defaultdict(float)

        for row, e in enumerate(entries):
            dims = ""
            if e.get("dim_l") and e.get("dim_w") and e.get("dim_h"):
                dims = f"{e['dim_l']:.0f}×{e['dim_w']:.0f}×{e['dim_h']:.0f}"
            cost = float(e.get("cost_eur") or 0)
            total += cost
            mode = e.get("transport_mode", "Road")
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            mode_costs[mode] += cost

            month = e.get("entry_month")
            if month:
                monthly_costs[int(month)] += cost

            mode_colors = {"Air":"#E53935","Road":"#43A047","Sea":"#1E88E5","Express":"#FB8C00"}
            mc = mode_colors.get(mode, PRIMARY)

            vals = [
                e.get("entry_date",""),
                e.get("item_desc",""),
                str(e.get("quantity",1)),
                dims,
                f"{e['weight_kg']:.1f} kg" if e.get("weight_kg") else "—",
                e.get("origin",""),
                e.get("destination",""),
                mode,
                f"€{cost:,.2f}",
                e.get("pr_number",""),
            ]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignCenter if col != 1 else Qt.AlignLeft | Qt.AlignVCenter)
                if col == 7:
                    item.setForeground(QColor(mc))
                    item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM - 1, QFont.Bold))
                if col == 8:
                    item.setForeground(QColor("#E53935" if cost > 5000 else "#1565C0"))
                    item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM - 1, QFont.Bold))
                self.tbl.setItem(row, col, item)

            act_w = QWidget(); al = QHBoxLayout(act_w)
            al.setContentsMargins(4, 2, 4, 2); al.setSpacing(4)

            edit_btn = QPushButton("✏"); edit_btn.setFixedSize(26, 24)
            edit_btn.setStyleSheet(f"QPushButton{{background:{PRIMARY};color:white;border:none;border-radius:4px;font-size:9pt;}}")
            edit_btn.clicked.connect(lambda _, en=e: self._edit(en))
            al.addWidget(edit_btn)

            del_btn = QPushButton("🗑"); del_btn.setFixedSize(26, 24)
            del_btn.setStyleSheet("QPushButton{background:#E53935;color:white;border:none;border-radius:4px;font-size:9pt;}")
            del_btn.clicked.connect(lambda _, en=e: self._delete(en))
            al.addWidget(del_btn)

            self.tbl.setCellWidget(row, 10, act_w)
            self.tbl.setRowHeight(row, 32)

        mode_str = ", ".join(f"{m}: {c}" for m, c in mode_counts.items()) or "No entries"
        self._summary_lbl.setText(
            f"  Total freight cost: <b>€{total:,.2f}</b>   |   "
            f"Entries: <b>{len(entries)}</b>   |   {mode_str}"
        )

        self._build_bar_chart(dict(monthly_costs))
        self._build_donut_chart(dict(mode_costs))

    def _add(self):
        dlg = TransportForm(self.project_id, parent=self)
        if dlg.exec(): self._refresh()

    def _edit(self, entry):
        dlg = TransportForm(self.project_id, entry=entry, parent=self)
        if dlg.exec(): self._refresh()

    def _delete(self, entry):
        if QMessageBox.question(self, "Delete", "Delete this transport entry?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            delete_transport_entry(
                entry["id"],
                entry.get("entry_year", datetime.date.today().year),
                entry.get("entry_month", datetime.date.today().month)
            )
            self._refresh()
