"""
KPI View – Monthly Review Dashboard
Sidebar section: KPI
- Full KPI list management (add/edit/delete)
- Monthly score entry per KPI
- Auto-calculated trend, avg, RAG status
- Charts for each KPI with snapshot (save-as-image) button
"""
from __future__ import annotations
import datetime, os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QFrame,
    QDialog, QDialogButtonBox, QLineEdit, QComboBox, QDoubleSpinBox,
    QTextEdit, QGridLayout, QSizePolicy, QMessageBox, QSpinBox,
    QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from app.utils.theme import *
from app.utils.widgets import make_label, add_shadow
from app.models.project_model import (
    get_all_kpis, get_kpi, upsert_kpi, delete_kpi,
    get_kpi_scores, upsert_kpi_score, get_kpi_dashboard_summary,
    get_all_kpi_scores_for_year, get_rar_entry_counts_for_kpi
)

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
CATEGORIES = [
    "Gate Management", "Launch", "R&R", "Scrap", "Logistics", "Process", "Other"
]
UNITS = ["%", "count", "score", "kMAD", "€", "days", "pcs"]

# ── RAG helper ────────────────────────────────────────────────────────────────
def rag_color(score, target, unit):
    """Return (bg_hex, fg_hex) based on RAG logic."""
    if score is None:
        return ("#F5F7FA", TEXT_SECONDARY)
    try:
        score = float(score); target = float(target)
    except:
        return ("#F5F7FA", TEXT_SECONDARY)
    # For "lower is better" KPIs (scrap, cost, late actions)
    lower_better = any(kw in unit.lower() for kw in ["€","mad","days"]) or target == 0
    if lower_better:
        pct = score / max(target, 0.01) if target > 0 else 0
        if pct <= 1.0: return ("#C8E6C9", "#1B5E20")   # green
        if pct <= 1.3: return ("#FFF9C4", "#F57F17")   # amber
        return ("#FFCDD2", "#B71C1C")                   # red
    else:
        pct = score / max(target, 0.01)
        if pct >= 1.0: return ("#C8E6C9", "#1B5E20")
        if pct >= 0.8: return ("#FFF9C4", "#F57F17")
        return ("#FFCDD2", "#B71C1C")


# ── Reusable card frame ───────────────────────────────────────────────────────
class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background:{BG_CARD}; border:1px solid {BORDER};
                border-radius:{RADIUS}px;
            }}
        """)
        add_shadow(self)


# ══════════════════════════════════════════════════════════════════════════════
# KPI Form Dialog
# ══════════════════════════════════════════════════════════════════════════════
class KPIForm(QDialog):
    def __init__(self, kpi_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add KPI" if not kpi_data else "Edit KPI")
        self.setMinimumWidth(460)
        self._data = kpi_data or {}
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14); lay.setContentsMargins(24,20,24,20)

        lay.addWidget(make_label("KPI Details", FONT_SIZE_MD, bold=True))

        grid = QGridLayout(); grid.setSpacing(10)

        grid.addWidget(make_label("KPI Name *", FONT_SIZE_SM, bold=True), 0, 0)
        self.name_edit = QLineEdit(self._data.get("name",""))
        self.name_edit.setStyleSheet(INPUT_QSS); self.name_edit.setPlaceholderText("e.g. % Programs on Time")
        grid.addWidget(self.name_edit, 0, 1)

        grid.addWidget(make_label("Category *", FONT_SIZE_SM, bold=True), 1, 0)
        self.cat_combo = QComboBox(); self.cat_combo.addItems(CATEGORIES)
        self.cat_combo.setStyleSheet(INPUT_QSS)
        idx = self.cat_combo.findText(self._data.get("category","Gate Management"))
        if idx >= 0: self.cat_combo.setCurrentIndex(idx)
        grid.addWidget(self.cat_combo, 1, 1)

        grid.addWidget(make_label("Unit", FONT_SIZE_SM, bold=True), 2, 0)
        self.unit_combo = QComboBox(); self.unit_combo.addItems(UNITS)
        self.unit_combo.setStyleSheet(INPUT_QSS); self.unit_combo.setEditable(True)
        idx = self.unit_combo.findText(self._data.get("unit","%"))
        if idx >= 0: self.unit_combo.setCurrentIndex(idx)
        else: self.unit_combo.setCurrentText(self._data.get("unit","%"))
        grid.addWidget(self.unit_combo, 2, 1)

        grid.addWidget(make_label("Target", FONT_SIZE_SM, bold=True), 3, 0)
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0, 999999); self.target_spin.setDecimals(2)
        self.target_spin.setValue(float(self._data.get("target", 100) or 100))
        self.target_spin.setStyleSheet(INPUT_QSS)
        grid.addWidget(self.target_spin, 3, 1)

        grid.addWidget(make_label("Description", FONT_SIZE_SM, bold=True), 4, 0)
        self.desc_edit = QTextEdit(self._data.get("description",""))
        self.desc_edit.setMaximumHeight(70); self.desc_edit.setStyleSheet(INPUT_QSS)
        grid.addWidget(self.desc_edit, 4, 1)

        lay.addLayout(grid)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save); btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setStyleSheet(BUTTON_PRIMARY_QSS)
        lay.addWidget(btns)

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Required", "KPI name is required.")
            return
        data = {
            "id":          self._data.get("id"),
            "name":        name,
            "category":    self.cat_combo.currentText(),
            "unit":        self.unit_combo.currentText(),
            "target":      self.target_spin.value(),
            "description": self.desc_edit.toPlainText().strip(),
            "sort_order":  self._data.get("sort_order", 0),
        }
        upsert_kpi(data)
        self.accept()


# ══════════════════════════════════════════════════════════════════════════════
# Monthly Score Entry Dialog
# ══════════════════════════════════════════════════════════════════════════════
class ScoreEntryDialog(QDialog):
    def __init__(self, kpi, year, parent=None):
        super().__init__(parent)
        self.kpi  = kpi
        self.year = year
        self.setWindowTitle(f"Enter Scores – {kpi['name']} ({year})")
        self.setMinimumWidth(560)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(14); lay.setContentsMargins(24,20,24,20)

        is_rvp = "released" in self.kpi["name"].lower() or \
                 "vs planned" in self.kpi["name"].lower()

        hdr = QHBoxLayout()
        hdr.addWidget(make_label(self.kpi['name'], FONT_SIZE_MD, bold=True))
        hdr.addStretch()
        if is_rvp:
            hdr.addWidget(make_label("Count-based: score = Released, target = Planned",
                                     FONT_SIZE_SM, color=TEXT_SECONDARY))
        else:
            hdr.addWidget(make_label(f"Target: {self.kpi['target']} {self.kpi['unit']}",
                                     FONT_SIZE_SM, color=TEXT_SECONDARY))
        lay.addLayout(hdr)

        # ── Unit selector (only for non-RvP KPIs) ──────────────────────────
        if not is_rvp:
            unit_row = QHBoxLayout()
            unit_row.addWidget(make_label("Unit for this KPI:", FONT_SIZE_SM))
            self._unit_combo = QComboBox()
            self._unit_combo.setStyleSheet(INPUT_QSS)
            self._unit_combo.setFixedWidth(160)
            _unit_choices = ["%", "€", "MAD", "Nombre", "Jours", "Days",
                             "count", "score", "pts", "h", "min", "kg", "pcs"]
            for u in _unit_choices:
                self._unit_combo.addItem(u)
            # Editable so user can type a custom unit
            self._unit_combo.setEditable(True)
            _cur = self.kpi.get("unit", "%")
            _idx = self._unit_combo.findText(_cur)
            if _idx >= 0:
                self._unit_combo.setCurrentIndex(_idx)
            else:
                self._unit_combo.setCurrentText(_cur)
            unit_row.addWidget(self._unit_combo)
            unit_row.addStretch()
            lay.addLayout(unit_row)
        else:
            self._unit_combo = None

        if is_rvp:
            note = QLabel("ℹ  This KPI is auto-updated by R@R entries — "
                          "the average is recalculated whenever a first score is entered or changed. "
                          "Manual edits here are possible but will be overwritten on the next R@R save.")
            note.setWordWrap(True)
            note.setStyleSheet("color:#1565C0;background:#E3F2FD;"
                               "padding:6px;border-radius:4px;font-size:8pt;")
            lay.addWidget(note)

        scores = {s["month"]: s for s in get_kpi_scores(self.kpi["id"], self.year)}

        score_col_lbl  = "Released (count)" if is_rvp else "Score"
        target_col_lbl = "Planned (count)"  if is_rvp else "Target Override"

        grid = QGridLayout(); grid.setSpacing(10)
        grid.addWidget(make_label("Month",          FONT_SIZE_SM, bold=True), 0, 0)
        grid.addWidget(make_label(score_col_lbl,    FONT_SIZE_SM, bold=True), 0, 1)
        grid.addWidget(make_label(target_col_lbl,   FONT_SIZE_SM, bold=True), 0, 2)
        grid.addWidget(make_label("Comment",         FONT_SIZE_SM, bold=True), 0, 3)

        self._rows = {}
        for i, mon in enumerate(MONTHS):
            m = i + 1
            s = scores.get(m, {})
            grid.addWidget(make_label(mon, FONT_SIZE_SM, bold=True, color=PRIMARY), i+1, 0)

            score_sb = QDoubleSpinBox()
            score_sb.setRange(-99999, 999999)
            score_sb.setDecimals(0 if is_rvp else 2)
            score_sb.setSpecialValueText("—"); score_sb.setMinimum(-99999)
            score_sb.setStyleSheet(INPUT_QSS)
            if s.get("score") is not None:
                score_sb.setValue(float(s["score"]))
            else:
                score_sb.setValue(-99999)  # show "—"
            grid.addWidget(score_sb, i+1, 1)

            tgt_sb = QDoubleSpinBox()
            tgt_sb.setRange(0, 999999)
            tgt_sb.setDecimals(0 if is_rvp else 2)
            tgt_sb.setStyleSheet(INPUT_QSS)
            tgt_sb.setValue(float(s.get("target") or self.kpi["target"]))
            grid.addWidget(tgt_sb, i+1, 2)

            comment_edit = QLineEdit(s.get("comment",""))
            comment_edit.setStyleSheet(INPUT_QSS)
            comment_edit.setPlaceholderText("Optional note…")
            grid.addWidget(comment_edit, i+1, 3)

            self._rows[m] = (score_sb, tgt_sb, comment_edit)

        scroll_w = QWidget(); scroll_w.setLayout(grid)
        sa = QScrollArea(); sa.setWidget(scroll_w); sa.setWidgetResizable(True)
        sa.setMaximumHeight(380)
        sa.setStyleSheet("""
            QScrollArea{border:none;background:transparent;}
            QScrollBar:vertical{background:#F0F4F8;width:6px;border-radius:3px;}
            QScrollBar::handle:vertical{background:#C5D0DC;border-radius:3px;min-height:20px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}
        """)
        lay.addWidget(sa)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save); btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setStyleSheet(BUTTON_PRIMARY_QSS)
        lay.addWidget(btns)

    def _save(self):
        # Persist chosen unit back to the KPI definition
        if self._unit_combo is not None:
            new_unit = self._unit_combo.currentText().strip()
            if new_unit and new_unit != self.kpi.get("unit", ""):
                from app.database.db_manager import get_connection
                conn = get_connection()
                conn.execute("UPDATE kpis SET unit=? WHERE id=?",
                             (new_unit, self.kpi["id"]))
                conn.commit()

        for m, (score_sb, tgt_sb, comment_edit) in self._rows.items():
            raw = score_sb.value()
            score = None if raw <= -99999 else raw
            upsert_kpi_score(
                self.kpi["id"], self.year, m,
                score, tgt_sb.value(), comment_edit.text().strip()
            )
        self.accept()


# ══════════════════════════════════════════════════════════════════════════════
# Single KPI Chart Widget
# ══════════════════════════════════════════════════════════════════════════════
class KPIChartWidget(QFrame):
    def __init__(self, kpi, scores, year, parent=None):
        super().__init__(parent)
        self.kpi    = kpi
        self.scores = scores
        self.year   = year
        # Pre-fetch per-month R@R entry counts for "1st Score" KPI annotation
        is_1st_score = ("1st score" in kpi["name"].lower() or
                        "1st score" in kpi.get("description","").lower())
        self._rar_counts = get_rar_entry_counts_for_kpi(year) if is_1st_score else {}
        self.setStyleSheet(f"""
            QFrame {{background:{BG_CARD};border:1px solid {BORDER};border-radius:{RADIUS}px;}}
        """)
        add_shadow(self)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(14,12,14,12); lay.setSpacing(8)

        # Header row
        hdr = QHBoxLayout()
        name_lbl = make_label(self.kpi["name"], FONT_SIZE_SM, bold=True)
        name_lbl.setWordWrap(True)
        hdr.addWidget(name_lbl, stretch=1)

        # RAG badge – use per-month target for the latest score
        latest = next((s for s in reversed(self.scores) if s.get("score") is not None), None)
        if latest:
            month_target = latest.get("target") or self.kpi["target"]
            bg, fg = rag_color(latest["score"], month_target, self.kpi["unit"])
            rag_lbl = QLabel(f"  {latest['score']:.1f} {self.kpi['unit']}  ")
            rag_lbl.setStyleSheet(f"""
                background:{bg};color:{fg};border-radius:10px;
                font-weight:bold;font-size:8pt;padding:2px 6px;
            """)
            hdr.addWidget(rag_lbl)

        # Camera button
        cam_btn = QPushButton("📷 Snapshot")
        cam_btn.setFixedHeight(26)
        cam_btn.setStyleSheet(f"""
            QPushButton{{background:{ACCENT};color:white;border:none;
            border-radius:6px;padding:2px 10px;font-size:8pt;font-weight:bold;}}
            QPushButton:hover{{background:#00838F;}}
        """)
        cam_btn.clicked.connect(self._save_snapshot)
        hdr.addWidget(cam_btn)
        lay.addLayout(hdr)

        # Category tag
        cat_lbl = make_label(self.kpi["category"], 7, color=TEXT_SECONDARY)
        lay.addWidget(cat_lbl)

        # Build chart
        self._fig, self._canvas = self._make_chart()
        lay.addWidget(self._canvas)

        # Summary stats row
        stats = self._calc_stats()
        stats_row = QHBoxLayout()
        for label, val in stats:
            cell = QVBoxLayout(); cell.setSpacing(1)
            cell.addWidget(make_label(val, FONT_SIZE_SM, bold=True, color=PRIMARY))
            cell.addWidget(make_label(label, 7, color=TEXT_SECONDARY))
            stats_row.addLayout(cell)
            if label != stats[-1][0]:
                sep = QFrame(); sep.setFrameShape(QFrame.VLine)
                sep.setStyleSheet(f"color:{BORDER};"); stats_row.addWidget(sep)
        lay.addLayout(stats_row)

    def _make_chart(self):  # noqa: C901
        import matplotlib.lines as mlines
        import matplotlib.patches as mpatches

        # ── Data preparation ──────────────────────────────────────────────────
        all_months = list(range(1, 13))
        # Ensure month keys are ints (sqlite can return them as int already, but be safe)
        score_map  = {int(s["month"]): s for s in self.scores}

        is_rvp = ("released" in self.kpi["name"].lower() or
                  "vs planned" in self.kpi["name"].lower())
        is_1st = bool(self._rar_counts)   # True only for R@R 1st Score KPI
        kpi_target = float(self.kpi["target"] or 0)

        # vals: actual score per month (None = no data)
        vals = [
            score_map[m]["score"]
            if m in score_map and score_map[m].get("score") is not None
            else None
            for m in all_months
        ]

        # tgts: per-month targets
        # For R@R 1st Score → flat target = kpi["target"] (90%)
        # For Released vs Planned → per-month planned count stored in score row;
        #   months without a score row have target=0 (nothing planned yet)
        if is_rvp:
            tgts = [
                float(score_map[m]["target"])
                if m in score_map and score_map[m].get("target") is not None
                else 0.0
                for m in all_months
            ]
        else:
            tgts = [kpi_target] * 12   # flat target line

        bar_vals = [v if v is not None else 0.0 for v in vals]

        # ── Figure ────────────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(5.8, 2.6))
        fig.patch.set_facecolor("none")
        ax.set_facecolor("none")

        # ── Bar colours ───────────────────────────────────────────────────────
        bar_colors, bar_alphas = [], []
        for m_idx, (v, t) in enumerate(zip(vals, tgts)):
            if v is None:
                bar_colors.append("#E8EEF4"); bar_alphas.append(0.35)
            else:
                if is_rvp:
                    good = t > 0 and v >= t   # released >= planned
                else:
                    good = v >= kpi_target     # score >= target %
                bar_colors.append("#4CAF50" if good else "#EF5350")
                bar_alphas.append(0.88)

        bars = ax.bar(
            [MONTHS[m-1] for m in all_months],
            bar_vals, color=bar_colors, width=0.62,
            edgecolor="white", linewidth=0.5, zorder=3,
        )
        for bar, alpha in zip(bars, bar_alphas):
            bar.set_alpha(alpha)

        # ── Target line ───────────────────────────────────────────────────────
        target_line = None
        y_anchor = max(bar_vals + tgts + [1.0])

        if is_rvp:
            # Stepped line — one step per month, height = planned count
            # Only draw if at least one month has a planned count > 0
            if any(t > 0 for t in tgts):
                (target_line,) = ax.step(
                    range(12), tgts, where="mid",
                    color="#1565C0", linestyle="--", linewidth=1.5,
                    label="Planned (target)", zorder=5,
                )
                # Planned-count annotation above each active step segment
                for xi, yt in enumerate(tgts):
                    if yt > 0:
                        ax.text(
                            xi, yt + y_anchor * 0.05,
                            f"P={int(yt)}", ha="center", va="bottom",
                            fontsize=5.5, color="#1565C0", fontweight="bold",
                        )
        else:
            if kpi_target > 0:
                target_line = ax.axhline(
                    kpi_target, color="#1565C0", linestyle="--",
                    linewidth=1.5, zorder=5,
                    label=f"Target {kpi_target:.4g} {self.kpi['unit']}",
                )

        # ── Value labels on bars ──────────────────────────────────────────────
        for xi, (bar, v) in enumerate(zip(bars, vals)):
            m = all_months[xi]
            t = tgts[xi]
            bh = bar.get_height()
            if is_rvp:
                if t > 0:          # only label months that have planned events
                    released_int = int(v) if v is not None else 0
                    label_txt = f"{released_int}/{int(t)}"
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bh + y_anchor * 0.025,
                        label_txt, ha="center", va="bottom",
                        fontsize=6, color="#212121", fontweight="bold",
                    )
            elif v is not None and v > 0:
                # Score value above bar
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bh + y_anchor * 0.025,
                    f"{v:.1f}", ha="center", va="bottom",
                    fontsize=6, color="#212121", fontweight="bold",
                )
                # Sample size n=X centred inside bar (only for 1st Score KPI)
                if is_1st and m in self._rar_counts and bh > 0:
                    n = self._rar_counts[m]
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bh * 0.45,
                        f"n={n}", ha="center", va="center",
                        fontsize=5, color="white", fontweight="bold", alpha=0.9,
                    )

        # ── Legend (safe — never calls get_lines()[0]) ────────────────────────
        legend_handles = []
        if target_line is not None:
            legend_handles.append(target_line)
        legend_handles += [
            mpatches.Patch(facecolor="#4CAF50", alpha=0.88, label="✓ Meets target"),
            mpatches.Patch(facecolor="#EF5350", alpha=0.88, label="✗ Below target"),
        ]
        # Place legend where fewest bars are — avoids obscuring data
        _filled = sum(1 for v in bar_vals if v > 0)
        _leg_loc = "upper right" if _filled <= 4 else "lower right"
        ax.legend(handles=legend_handles, fontsize=5.5, loc=_leg_loc,
                  framealpha=0.80, edgecolor=BORDER)

        # ── Axes styling ──────────────────────────────────────────────────────
        ax.set_ylabel(self.kpi["unit"], fontsize=6.5, color=TEXT_SECONDARY)
        ax.set_xticks(range(12))
        ax.set_xticklabels([MONTHS[m-1] for m in all_months], fontsize=6.5, rotation=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(BORDER)
        ax.spines["bottom"].set_color(BORDER)
        ax.tick_params(axis="both", labelsize=6.5, colors=TEXT_SECONDARY)
        ax.set_ylim(0, max(y_anchor * 1.40, 1.0))
        fig.tight_layout(pad=0.6)

        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background:transparent;")
        canvas.setFixedHeight(195)
        return fig, canvas

    def _calc_stats(self):
        is_rvp = "released" in self.kpi["name"].lower() or \
                 "vs planned" in self.kpi["name"].lower()

        if is_rvp:
            # For Released vs Planned show cumulative counts, not averages
            total_planned  = sum(s.get("target") or 0 for s in self.scores)
            total_released = sum(s["score"] for s in self.scores
                                 if s.get("score") is not None)
            months_active  = sum(1 for s in self.scores
                                 if s.get("target") and s["target"] > 0)
            pct = (total_released / total_planned * 100) if total_planned else 0
            return [
                ("Total Planned",  f"{int(total_planned)}"),
                ("Total Released", f"{int(total_released)}"),
                ("Rate",           f"{pct:.0f}%"),
                ("Months Active",  str(months_active)),
            ]

        vals = [s["score"] for s in self.scores if s.get("score") is not None]
        if not vals:
            return [("Avg", "—"), ("Min", "—"), ("Max", "—"), ("Months", "0")]
        avg = sum(vals) / len(vals)
        tgt = float(self.kpi["target"] or 1)
        return [
            ("Avg", f"{avg:.1f}"),
            ("Min", f"{min(vals):.1f}"),
            ("Max", f"{max(vals):.1f}"),
            ("vs Target", f"{avg/tgt*100:.0f}%"),
        ]

    def _save_snapshot(self):
        default_name = f"KPI_{self.kpi['name'].replace(' ','_')}_{self.year}.png"
        path, _ = QFileDialog.getSaveFileName(self, "Save Chart Snapshot",
                                               default_name, "PNG Images (*.png)")
        if path:
            # Render with white background for saved image
            self._fig.savefig(path, dpi=150, bbox_inches="tight",
                              facecolor="white", edgecolor="none")
            QMessageBox.information(self, "Saved", f"Chart saved to:\n{path}")


# ══════════════════════════════════════════════════════════════════════════════
# KPI Management Tab (list + CRUD)
# ══════════════════════════════════════════════════════════════════════════════
class KPIManagementWidget(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(16,12,16,12); lay.setSpacing(12)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("KPI Registry", FONT_SIZE_LG, bold=True))
        hdr.addStretch()
        add_btn = QPushButton("＋ Add KPI")
        add_btn.setStyleSheet(BUTTON_PRIMARY_QSS); add_btn.setFixedHeight(34)
        add_btn.clicked.connect(self._add_kpi)
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)
        lay.addWidget(make_label(
            "Manage your KPI definitions. Click a row to enter monthly scores.",
            FONT_SIZE_SM, color=TEXT_SECONDARY))

        # Table
        self.tbl = QTableWidget()
        self.tbl.setStyleSheet(TABLE_QSS)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(["KPI Name","Category","Unit","Target","Description","Actions"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        for c in [1,2,3,5]: self.tbl.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setShowGrid(False)
        lay.addWidget(self.tbl)

        self.refresh()

    def refresh(self):
        kpis = get_all_kpis()
        self.tbl.setRowCount(len(kpis))
        for row, k in enumerate(kpis):
            for col, val in enumerate([k["name"], k["category"], k["unit"],
                                        str(k["target"]), k.get("description","")]):
                item = QTableWidgetItem(val)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.tbl.setItem(row, col, item)

            act_w = QWidget(); act_lay = QHBoxLayout(act_w)
            act_lay.setContentsMargins(4,2,4,2); act_lay.setSpacing(6)

            edit_btn = QPushButton("✏"); edit_btn.setFixedSize(28,26)
            edit_btn.setToolTip("Edit KPI")
            edit_btn.setStyleSheet(f"QPushButton{{background:{PRIMARY};color:white;border:none;border-radius:5px;font-size:10pt;}}")
            edit_btn.clicked.connect(lambda _, kd=k: self._edit_kpi(kd))

            del_btn = QPushButton("🗑"); del_btn.setFixedSize(28,26)
            del_btn.setToolTip("Delete KPI")
            del_btn.setStyleSheet("QPushButton{background:#E53935;color:white;border:none;border-radius:5px;font-size:10pt;}")
            del_btn.clicked.connect(lambda _, kid=k["id"]: self._delete_kpi(kid))

            act_lay.addWidget(edit_btn); act_lay.addWidget(del_btn)
            self.tbl.setCellWidget(row, 5, act_w)
            self.tbl.setRowHeight(row, 38)

    def _add_kpi(self):
        dlg = KPIForm(parent=self)
        if dlg.exec(): self.refresh(); self.refresh_requested.emit()

    def _edit_kpi(self, kd):
        dlg = KPIForm(kpi_data=kd, parent=self)
        if dlg.exec(): self.refresh(); self.refresh_requested.emit()

    def _delete_kpi(self, kid):
        if QMessageBox.question(self, "Delete KPI",
                "Delete this KPI and all its scores?",
                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            delete_kpi(kid)
            self.refresh(); self.refresh_requested.emit()


# ══════════════════════════════════════════════════════════════════════════════
# Monthly Scores Tab
# ══════════════════════════════════════════════════════════════════════════════
class MonthlyScoresWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._year = datetime.date.today().year
        lay = QVBoxLayout(self); lay.setContentsMargins(16,12,16,12); lay.setSpacing(12)

        # Toolbar
        tb = QHBoxLayout()
        tb.addWidget(make_label("Monthly KPI Scores", FONT_SIZE_LG, bold=True))
        tb.addStretch()
        tb.addWidget(make_label("Year:", FONT_SIZE_SM, color=TEXT_SECONDARY))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2035)
        self.year_spin.setValue(self._year)
        self.year_spin.setStyleSheet(INPUT_QSS); self.year_spin.setFixedWidth(80)
        self.year_spin.valueChanged.connect(self._on_year_change)
        tb.addWidget(self.year_spin)
        lay.addLayout(tb)

        # Summary table
        self.tbl = QTableWidget()
        self.tbl.setStyleSheet(TABLE_QSS)
        self.tbl.setAlternatingRowColors(True)
        cols = ["KPI Name", "Category"] + MONTHS + ["Avg", "vs Target"]
        self.tbl.setColumnCount(len(cols))
        self.tbl.setHorizontalHeaderLabels(cols)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        for c in range(2, len(cols)):
            self.tbl.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setShowGrid(False)
        self.tbl.doubleClicked.connect(self._on_row_double_click)
        lay.addWidget(self.tbl)

        lay.addWidget(make_label("💡 Double-click a KPI row to enter/edit monthly scores.",
                                   FONT_SIZE_SM, color=TEXT_SECONDARY))
        self.refresh()

    def _on_year_change(self, val):
        self._year = val; self.refresh()

    def refresh(self):
        kpis = get_all_kpis()
        self.tbl.setRowCount(len(kpis))
        self._kpi_list = kpis
        for row, k in enumerate(kpis):
            scores = {s["month"]: s for s in get_kpi_scores(k["id"], self._year)}
            self.tbl.setItem(row, 0, QTableWidgetItem(k["name"]))
            self.tbl.setItem(row, 1, QTableWidgetItem(k["category"]))

            is_rvp = "released" in k["name"].lower() or "vs planned" in k["name"].lower()

            monthly_vals = []
            monthly_tgts = []
            for m in range(1, 13):
                s = scores.get(m)
                val = s["score"] if s and s.get("score") is not None else None
                # Use per-month target when available (essential for Released vs Planned)
                month_tgt = float(s["target"]) if s and s.get("target") is not None \
                            else float(k["target"])
                monthly_vals.append(val)
                monthly_tgts.append(month_tgt)

                if is_rvp and s:
                    planned = int(s.get("target") or 0)
                    released = int(val) if val is not None else 0
                    text = f"{released}/{planned}" if planned > 0 else "—"
                else:
                    text = f"{val:.1f}" if val is not None else "—"

                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if val is not None:
                    bg, fg = rag_color(val, month_tgt, k["unit"])
                    item.setBackground(QColor(bg))
                    item.setForeground(QColor(fg))
                self.tbl.setItem(row, 2+m-1, item)

            valid_pairs = [(v, t) for v, t in zip(monthly_vals, monthly_tgts)
                           if v is not None]

            if is_rvp:
                total_released = sum(v for v, _ in valid_pairs)
                total_planned  = sum(t for _, t in valid_pairs)
                avg_text = f"{int(total_released)}/{int(total_planned)}"
                vs_tgt   = f"{total_released/total_planned*100:.0f}%" \
                           if total_planned else "—"
                avg_item = QTableWidgetItem(avg_text)
                avg_item.setTextAlignment(Qt.AlignCenter)
                avg_item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
                self.tbl.setItem(row, 14, avg_item)

                vt_item = QTableWidgetItem(vs_tgt)
                vt_item.setTextAlignment(Qt.AlignCenter)
                if total_planned:
                    pct = total_released / total_planned * 100
                    bg, fg = rag_color(pct, 100, "%")
                    vt_item.setBackground(QColor(bg)); vt_item.setForeground(QColor(fg))
                self.tbl.setItem(row, 15, vt_item)
            else:
                valid = [v for v, _ in valid_pairs]
                avg = sum(valid) / len(valid) if valid else None
                avg_tgt = float(k["target"]) or 1
                vs_tgt = f"{avg/avg_tgt*100:.0f}%" if avg is not None and avg_tgt else "—"
                avg_text = f"{avg:.1f}" if avg is not None else "—"

                avg_item = QTableWidgetItem(avg_text)
                avg_item.setTextAlignment(Qt.AlignCenter)
                avg_item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
                self.tbl.setItem(row, 14, avg_item)

                vt_item = QTableWidgetItem(vs_tgt)
                vt_item.setTextAlignment(Qt.AlignCenter)
                if avg is not None:
                    bg, fg = rag_color(avg, avg_tgt, k["unit"])
                    vt_item.setBackground(QColor(bg)); vt_item.setForeground(QColor(fg))
                self.tbl.setItem(row, 15, vt_item)

            self.tbl.setRowHeight(row, 36)

    def _on_row_double_click(self, idx):
        row = idx.row()
        if row < len(self._kpi_list):
            kpi = self._kpi_list[row]
            dlg = ScoreEntryDialog(kpi, self._year, self)
            if dlg.exec(): self.refresh()


# ══════════════════════════════════════════════════════════════════════════════
# Charts Tab
# ══════════════════════════════════════════════════════════════════════════════
class KPIChartsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._year = datetime.date.today().year
        self._main_lay = QVBoxLayout(self)
        self._main_lay.setContentsMargins(16,12,16,12); self._main_lay.setSpacing(12)

        # Toolbar
        tb = QHBoxLayout()
        tb.addWidget(make_label("KPI Charts", FONT_SIZE_LG, bold=True))
        tb.addStretch()

        snap_all_btn = QPushButton("📷 Save All Charts")
        snap_all_btn.setStyleSheet(f"QPushButton{{background:{ACCENT};color:white;border:none;border-radius:{RADIUS}px;padding:6px 14px;font-size:9pt;font-weight:bold;}} QPushButton:hover{{background:#00838F;}}")
        snap_all_btn.clicked.connect(self._save_all)
        tb.addWidget(snap_all_btn)

        tb.addWidget(make_label("Year:", FONT_SIZE_SM, color=TEXT_SECONDARY))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2035)
        self.year_spin.setValue(self._year)
        self.year_spin.setStyleSheet(INPUT_QSS); self.year_spin.setFixedWidth(80)
        self.year_spin.valueChanged.connect(self._on_year_change)
        tb.addWidget(self.year_spin)
        self._main_lay.addLayout(tb)

        # Scroll area for charts
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea{border:none;background:transparent;}
            QScrollBar:vertical{background:#F0F4F8;width:7px;border-radius:3px;}
            QScrollBar::handle:vertical{background:#C5D0DC;border-radius:3px;min-height:30px;}
            QScrollBar::handle:vertical:hover{background:#A0B0BF;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}
        """)
        self._main_lay.addWidget(self._scroll)

        self.refresh()

    def _on_year_change(self, val):
        self._year = val; self.refresh()

    def refresh(self):
        # Free old matplotlib figures to avoid memory leaks
        if hasattr(self, '_chart_widgets'):
            for cw in self._chart_widgets:
                try: plt.close(cw._fig)
                except: pass

        kpis = get_all_kpis()
        self._chart_widgets = []

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        grid = QGridLayout(container)
        grid.setSpacing(16)
        grid.setContentsMargins(4, 4, 4, 4)

        for i, kpi in enumerate(kpis):
            scores = get_kpi_scores(kpi["id"], self._year)
            cw = KPIChartWidget(kpi, scores, self._year)
            cw.setMinimumWidth(380)
            cw.setMaximumWidth(620)
            row, col = divmod(i, 2)
            grid.addWidget(cw, row, col)
            self._chart_widgets.append(cw)

        if not kpis:
            no_data = make_label(
                "No KPIs defined yet. Add KPIs in the 'KPI Registry' tab.",
                FONT_SIZE_MD, color=TEXT_SECONDARY
            )
            no_data.setAlignment(Qt.AlignCenter)
            grid.addWidget(no_data, 0, 0)

        self._scroll.setWidget(container)

    def _save_all(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder to save all charts")
        if not folder:
            return
        saved = 0
        for cw in self._chart_widgets:
            fname = f"KPI_{cw.kpi['name'].replace(' ','_')}_{self._year}.png"
            path = os.path.join(folder, fname)
            cw._fig.savefig(path, dpi=150, bbox_inches="tight",
                            facecolor="white", edgecolor="none")
            saved += 1
        QMessageBox.information(self, "Done", f"{saved} charts saved to:\n{folder}")


# ══════════════════════════════════════════════════════════════════════════════
# Main KPI View (combines all tabs)
# ══════════════════════════════════════════════════════════════════════════════
class KPIView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(APP_QSS)

        self.mgmt_tab    = KPIManagementWidget()
        self.scores_tab  = MonthlyScoresWidget()
        self.charts_tab  = KPIChartsWidget()

        self.tabs.addTab(self.mgmt_tab,   "📋 KPI Registry")
        self.tabs.addTab(self.scores_tab, "📊 Monthly Scores")
        self.tabs.addTab(self.charts_tab, "📈 Charts")

        # Propagate refresh signals
        self.mgmt_tab.refresh_requested.connect(self.scores_tab.refresh)
        self.mgmt_tab.refresh_requested.connect(self.charts_tab.refresh)

        lay.addWidget(self.tabs)

    def refresh(self):
        self.mgmt_tab.refresh()
        self.scores_tab.refresh()
        self.charts_tab.refresh()
