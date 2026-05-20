"""
Dashboard View — Modern, Professional Portfolio Dashboard v3.

Layout:
  ┌─────────────────────────────────────────────────────────────┐
  │  HEADER: Title + Filter                                      │
  ├─────────────────────────────────────────────────────────────┤
  │  KPI ROW 1: Total | Active | Completed | Delayed |          │
  │             Risks | Actions                                  │
  ├─────────────────────────────────────────────────────────────┤
  │  KPI ROW 2: Budget | Consumed | Remaining | % | Next Gate   │
  ├─────────────────────────────────────────────────────────────┤
  │  ANALYTICS: Budget Donut (1/3)  |  Budget Bars (2/3)        │
  ├─────────────────────────────────────────────────────────────┤
  │  PROJECT PROGRESS (progress bars per project)               │
  ├─────────────────────────────────────────────────────────────┤
  │  UPCOMING DEADLINES (table)                                 │
  └─────────────────────────────────────────────────────────────┘
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QLinearGradient, QPainter, QBrush

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from app.utils.theme import *
from app.utils.widgets import (
    KpiCard, CardFrame, make_label, StatusBadge,
    add_shadow, StyledProgressBar
)
from app.models.project_model import (
    get_dashboard_stats, get_all_projects,
    get_kpi_dashboard_summary, get_all_kpis,
    get_all_budgets, get_all_budgets_bulk,
)


# ── Matplotlib global style ───────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         9,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.15,
    "grid.linestyle":    "--",
    "grid.color":        "#B0BEC5",
    "figure.dpi":        110,
})


# ─────────────────────────────────────────────────────────────────────────────
# Section divider
# ─────────────────────────────────────────────────────────────────────────────
class _SectionDivider(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)

        left_line = QFrame()
        left_line.setFrameShape(QFrame.HLine)
        left_line.setStyleSheet(f"color:{BORDER};background:{BORDER};max-height:1px;")
        lay.addWidget(left_line, 1)

        lbl = QLabel(title.upper())
        lbl.setFont(QFont(FONT_FAMILY, 7, QFont.Bold))
        lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY};background:transparent;"
            "letter-spacing:1.2px;padding:0 4px;"
        )
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lay.addWidget(lbl, 0)

        right_line = QFrame()
        right_line.setFrameShape(QFrame.HLine)
        right_line.setStyleSheet(f"color:{BORDER};background:{BORDER};max-height:1px;")
        lay.addWidget(right_line, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Budget Health Ring (donut) — custom small widget
# ─────────────────────────────────────────────────────────────────────────────
class _BudgetRingWidget(QWidget):
    """
    Minimal matplotlib donut showing consumed vs remaining.
    Center text shows the % consumed prominently.
    """
    def __init__(self, pct: float, pct_color: str, parent=None):
        super().__init__(parent)
        self.pct = pct
        self.pct_color = pct_color
        self._build(pct, pct_color)

    def _build(self, pct, pct_color):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        consumed  = min(pct, 100)
        remaining = max(100 - pct, 0)

        colors_ring = [pct_color, "#E8F5E9" if pct_color == "#43A047" else "#ECEFF1"]
        sizes = [consumed, remaining] if consumed > 0 else [0.001, 100]

        fig, ax = plt.subplots(figsize=(2.4, 2.4))
        fig.patch.set_facecolor("none")
        ax.set_facecolor("none")

        wedges, _ = ax.pie(
            sizes, colors=colors_ring, startangle=90,
            wedgeprops={"edgecolor": "white", "linewidth": 3, "width": 0.52}
        )

        # Center percentage text
        ax.text(0, 0.06, f"{pct:.1f}%",
                ha="center", va="center", fontsize=14,
                fontweight="bold", color=pct_color)
        ax.text(0, -0.22, "consumed",
                ha="center", va="center", fontsize=7.5,
                color=TEXT_SECONDARY)
        ax.axis("equal")
        ax.grid(False)
        fig.tight_layout(pad=0.1)

        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background:transparent;")
        canvas.setFixedSize(130, 130)
        lay.addWidget(canvas, 0, Qt.AlignCenter)
        plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Main Dashboard View
# ─────────────────────────────────────────────────────────────────────────────
class DashboardView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QScrollArea{border:none;background:transparent;}
            QScrollBar:vertical{background:#F0F4F8;width:7px;border-radius:3px;}
            QScrollBar::handle:vertical{background:#C5D0DC;border-radius:3px;min-height:30px;}
            QScrollBar::handle:vertical:hover{background:#A0B0BF;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}
        """)
        self._inner = QWidget()
        self._inner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(12, 16, 12, 24)
        self._lay.setSpacing(0)
        self.setWidget(self._inner)
        self._selected_project = None
        self._build()

    # ─────────────────────────────────────────────────────────────────────────
    def _build(self):
        stats = get_dashboard_stats(self._selected_project)
        # Cache projects + budgets once for the entire build — eliminates N+1 queries
        filt = {"project_id": self._selected_project} if self._selected_project else None
        self._cached_projects = get_all_projects(filt)
        self._cached_budgets  = get_all_budgets_bulk(
            [p["project_id"] for p in self._cached_projects] if self._cached_projects else None
        )
        self._build_header()
        self._lay.addSpacing(14)
        self._build_kpi_row1(stats)
        self._lay.addSpacing(8)
        self._build_kpi_row2(stats)
        self._lay.addSpacing(20)
        self._lay.addWidget(_SectionDivider("Analytics Overview"))
        self._lay.addSpacing(10)
        self._build_analytics_row(stats)
        self._lay.addSpacing(18)
        self._lay.addWidget(_SectionDivider("Project Progress"))
        self._lay.addSpacing(10)
        self._lay.addWidget(self._build_progress_overview())
        self._lay.addSpacing(18)
        self._lay.addWidget(_SectionDivider("Upcoming Deadlines & Gates"))
        self._lay.addSpacing(10)
        self._lay.addWidget(self._build_deadlines_table(stats))
        self._lay.addSpacing(18)
        self._lay.addWidget(_SectionDivider("📊 Monthly KPI Review"))
        self._lay.addSpacing(10)
        self._lay.addWidget(self._build_kpi_dashboard_section())
        self._lay.addStretch()

    # ── HEADER ────────────────────────────────────────────────────────────────
    def _build_header(self):
        header = QWidget()
        header.setStyleSheet("background:transparent;")
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        col = QVBoxLayout()
        col.setSpacing(3)
        title_lbl = make_label("Portfolio Dashboard", FONT_SIZE_XL, bold=True,
                               color=TEXT_PRIMARY)
        sub_lbl = make_label(
            "Real-time overview of all projects, budgets and risks",
            FONT_SIZE_SM, color=TEXT_SECONDARY
        )
        col.addWidget(title_lbl)
        col.addWidget(sub_lbl)
        row.addLayout(col)
        row.addStretch()

        filter_col = QVBoxLayout()
        filter_col.setSpacing(4)
        filter_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        filter_lbl = make_label("Filter by Project", FONT_SIZE_SM, color=TEXT_SECONDARY)
        filter_lbl.setAlignment(Qt.AlignRight)

        self.proj_combo = QComboBox()
        self.proj_combo.setStyleSheet(INPUT_QSS)
        self.proj_combo.setMinimumWidth(160)
        self.proj_combo.setMaximumWidth(280)
        self.proj_combo.addItem("📁  All Projects", None)
        for p in get_all_projects():
            self.proj_combo.addItem(
                f"{p['project_id']}  –  {p['name']}", p["project_id"]
            )
        if self._selected_project:
            idx = self.proj_combo.findData(self._selected_project)
            if idx >= 0:
                self.proj_combo.setCurrentIndex(idx)
        self.proj_combo.currentIndexChanged.connect(self._on_filter_change)

        filter_col.addWidget(filter_lbl)
        filter_col.addWidget(self.proj_combo)
        row.addLayout(filter_col)

        self._lay.addWidget(header)

    # ── KPI ROW 1: Project Status ─────────────────────────────────────────────
    def _build_kpi_row1(self, stats):
        row = QHBoxLayout()
        row.setSpacing(8)
        cards = [
            ("Total Projects", str(stats["total"]),        "📁", PRIMARY,                    "Portfolio"),
            ("Active",         str(stats["active"]),       "▶",  STATUS_COLORS["Active"],    "In Progress"),
            ("Completed",      str(stats["completed"]),    "✓",  STATUS_COLORS["Completed"], "Finished"),
            ("Delayed",        str(stats["delayed"]),      "⚠",  STATUS_COLORS["Delayed"],   "Behind schedule"),
            ("Open Risks",     str(stats["open_risks"]),   "🔴", "#E53935",                  "Need attention"),
            ("Open Actions",   str(stats["open_actions"]), "📋", "#FB8C00",                  "Current phase"),
        ]
        for title, value, icon, accent, subtitle in cards:
            card = KpiCard(title, value, icon, accent, subtitle=subtitle)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(card, 1)
        self._lay.addLayout(row)

    def _mini_kpi_card(self, title, value, icon, accent, subtitle=""):
        """Row-2 style card — identical look to KpiCard but used for financial row."""
        return KpiCard(title, value, icon, accent, subtitle=subtitle)

    # ── KPI ROW 2: Financial + Gates + R@R ───────────────────────────────────
    def _build_kpi_row2(self, stats):
        import datetime
        now      = datetime.date.today()
        mon_name = now.strftime("%B")          # e.g. "April"

        row = QHBoxLayout()
        row.setSpacing(8)
        planned   = stats.get("planned_budget", 0)
        actual    = stats.get("actual_cost", 0)
        pct       = (actual / planned * 100) if planned > 0 else 0
        pct_color = ("#E53935" if pct > 90 else "#FB8C00" if pct > 75 else STATUS_COLORS["Completed"])

        # Next gate this month
        ng = stats.get("next_gate_this_month")
        gate_val = ng["gate_date"] if ng else f"None in {mon_name}"
        gate_col = PHASE_COLORS.get(ng["phase"], "#607D8B") if ng else TEXT_SECONDARY
        gate_sub = ng["phase"] if ng else mon_name

        # Planned R@R this month
        rar_count = stats.get("planned_rar_this_month", 0)
        rar_col   = STATUS_COLORS["Active"] if rar_count > 0 else TEXT_SECONDARY
        rar_word  = "event" if rar_count == 1 else "events"

        cards = [
            ("Total Budget",
             self._fmt(planned), "€", ACCENT, "Planned budget"),
            ("% Budget Consumed",
             f"{pct:.1f}%", "📈", pct_color, f"of {self._fmt(planned)}"),
            (f"Next Gate\n({mon_name})",
             gate_val, "🚪", gate_col, gate_sub),
            (f"Planned R@R\n({mon_name})",
             str(rar_count), "🏁", rar_col, f"R@R {rar_word}"),
        ]
        for title, value, icon, accent, subtitle in cards:
            card = self._mini_kpi_card(title, value, icon, accent, subtitle)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(card, 1)
        self._lay.addLayout(row)

    # ── ANALYTICS ROW: Budget chart + 2 donut charts side by side ───────────
    def _build_analytics_row(self, stats):
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_budget_by_type_card(stats), 5)
        row.addWidget(self._build_status_donut_card(stats), 3)
        row.addWidget(self._build_phase_donut_card(), 3)
        self._lay.addLayout(row)

    # ── Budget by Type: Consumed vs Remaining ────────────────────────────────
    def _build_budget_by_type_card(self, stats):
        """Grouped bar chart: each budget type → consumed vs remaining bars."""
        card = CardFrame()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        planned = stats.get("planned_budget", 0)
        actual  = stats.get("actual_cost", 0)
        pct     = (actual / planned * 100) if planned > 0 else 0
        pct_col = "#E53935" if pct > 90 else "#FB8C00" if pct > 75 else "#43A047"

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Budget by Type — Consumed vs Remaining",
                                  FONT_SIZE_MD, bold=True))
        hdr.addStretch()
        badge = QLabel(f"  {pct:.1f}% consumed  ")
        badge.setStyleSheet(
            f"background:{pct_col}22;color:{pct_col};border-radius:10px;"
            f"padding:3px 10px;font-size:9pt;font-weight:bold;"
            f"font-family:{FONT_FAMILY};"
        )
        hdr.addWidget(badge)
        lay.addLayout(hdr)

        # Aggregate budget by type across all (filtered) projects
        projects = self._cached_projects
        type_data = {}  # type → {planned, consumed}
        for p in projects:
            budgets = self._cached_budgets.get(p["project_id"], [])
            for b in budgets:
                t = b.get("budget_type") or "Other"
                if t not in type_data:
                    type_data[t] = {"planned": 0, "consumed": 0}
                type_data[t]["planned"]  += float(b.get("planned_budget") or 0)
                type_data[t]["consumed"] += float(b.get("actual_cost") or 0)

        fig, ax = plt.subplots(figsize=(5.5, 2.2))
        fig.patch.set_facecolor("none"); ax.set_facecolor("none")

        if type_data:
            types     = list(type_data.keys())
            planvals  = [type_data[t]["planned"]  for t in types]
            consvals  = [type_data[t]["consumed"] for t in types]
            remvals   = [max(p - c, 0) for p, c in zip(planvals, consvals)]

            x  = range(len(types))
            bw = 0.38
            ax.bar([i - bw/2 for i in x], consvals, bw,
                   label="Consumed", color="#1E88E5", alpha=0.9,
                   edgecolor="white", linewidth=0.5)
            ax.bar([i + bw/2 for i in x], remvals, bw,
                   label="Remaining", color="#90CAF9", alpha=0.75,
                   edgecolor="white", linewidth=0.5)

            for i, (c, r) in enumerate(zip(consvals, remvals)):
                if c > 0:
                    ax.text(i - bw/2, c, self._fmt(c),
                            ha="center", va="bottom", fontsize=6,
                            color="#1565C0", fontweight="bold")
                if r > 0:
                    ax.text(i + bw/2, r, self._fmt(r),
                            ha="center", va="bottom", fontsize=6,
                            color="#1976D2")

            ax.set_xticks(list(x))
            ax.set_xticklabels(types, fontsize=7, color=TEXT_SECONDARY)
            ax.legend(fontsize=7, loc="upper right", framealpha=0.7)
        else:
            ax.text(0.5, 0.5, "No budget data yet", ha="center", va="center",
                    transform=ax.transAxes, color="#B0BEC5", fontsize=10)
            ax.axis("off")

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(BORDER)
        ax.spines["bottom"].set_color(BORDER)
        ax.tick_params(axis="both", labelsize=7, colors=TEXT_SECONDARY, length=0)
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: self._fmt(v) if v >= 1000 else f"{v:.0f}"))
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=0.12)
        fig.tight_layout(pad=0.4)

        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background:transparent;")
        canvas.setFixedHeight(148)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay.addWidget(canvas)
        plt.close(fig)
        lay.addStretch()
        return card

        # Donut ring
        ring = _BudgetRingWidget(pct, pct_color)
        lay.addWidget(ring, 0, Qt.AlignCenter)

        # Legend below ring
        legend_items = [
            ("Consumed",  self._fmt(actual),       pct_color),
            ("Remaining", self._fmt(max(planned - actual, 0)), "#90A4AE"),
        ]
        for label, value, color in legend_items:
            row = QHBoxLayout()
            dot = QLabel("●")
            dot.setFixedWidth(14)
            dot.setStyleSheet(f"color:{color};font-size:10pt;background:transparent;")
            name_l = make_label(label, FONT_SIZE_SM - 1, color=TEXT_SECONDARY)
            val_l  = make_label(value, FONT_SIZE_SM, bold=True, color=color)
            val_l.setAlignment(Qt.AlignRight)
            row.addWidget(dot)
            row.addWidget(name_l)
            row.addStretch()
            row.addWidget(val_l)
            lay.addLayout(row)

        lay.addSpacing(8)

        # Status distribution (smart render)
        sc = stats.get("status_counts", {})
        all_statuses  = ["Active", "Completed", "Delayed", "At Risk", "On Hold"]
        non_zero_statuses = [(s, sc.get(s, 0)) for s in all_statuses if sc.get(s, 0) > 0]

        if len(non_zero_statuses) == 0:
            # No projects
            info_lbl = make_label("No projects yet", FONT_SIZE_SM, color=TEXT_SECONDARY)
            info_lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(info_lbl)
        elif len(non_zero_statuses) == 1:
            # Single status → clean KPI card style
            s, v = non_zero_statuses[0]
            color = STATUS_COLORS.get(s, PRIMARY)
            pill = QLabel(f"All {v} project{'s' if v != 1 else ''} — {s}")
            pill.setAlignment(Qt.AlignCenter)
            pill.setStyleSheet(
                f"background:{color}22;color:{color};border:1px solid {color}55;"
                f"border-radius:12px;padding:6px 12px;font-size:9pt;font-weight:bold;"
                f"font-family:{FONT_FAMILY};"
            )
            lay.addWidget(pill)
        else:
            # Multiple statuses → compact legend
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setStyleSheet(f"color:{BORDER};background:{BORDER};")
            divider.setFixedHeight(1)
            lay.addWidget(divider)
            lay.addWidget(make_label("Status Distribution", FONT_SIZE_SM - 1,
                                     bold=True, color=TEXT_SECONDARY))
            for s, v in non_zero_statuses:
                color = STATUS_COLORS.get(s, "#607D8B")
                s_row = QHBoxLayout()
                s_row.setSpacing(6)
                dot = QLabel("●")
                dot.setFixedWidth(14)
                dot.setStyleSheet(f"color:{color};font-size:10pt;background:transparent;")
                nm = make_label(s, FONT_SIZE_SM - 1, color=TEXT_PRIMARY)
                vl = make_label(str(v), FONT_SIZE_SM, bold=True, color=color)
                vl.setAlignment(Qt.AlignRight)
                s_row.addWidget(dot)
                s_row.addWidget(nm)
                s_row.addStretch()
                s_row.addWidget(vl)
                lay.addLayout(s_row)

        lay.addStretch()
        return card

    # ── Project Status Donut ──────────────────────────────────────────────────
    def _build_status_donut_card(self, stats):
        """Donut chart: % of projects by status (Active / Completed / Delayed …)."""
        card = CardFrame()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        lay.addWidget(make_label("Projects by Status", FONT_SIZE_SM, bold=True))

        sc = stats.get("status_counts", {})
        all_statuses = ["Active", "Completed", "Delayed", "At Risk", "On Hold", "Cancelled"]
        labels  = [s for s in all_statuses if sc.get(s, 0) > 0]
        values  = [sc[s] for s in labels]
        colors  = [STATUS_COLORS.get(s, "#607D8B") for s in labels]
        total   = sum(values)

        fig, ax = plt.subplots(figsize=(2.6, 2.1))
        fig.patch.set_facecolor("none")
        ax.set_facecolor("none")

        if total > 0:
            wedges, _, autotexts = ax.pie(
                values,
                labels=None,
                colors=colors,
                autopct=lambda p: f"{p:.0f}%" if p > 6 else "",
                pctdistance=0.72,
                startangle=90,
                wedgeprops=dict(width=0.50, edgecolor="white", linewidth=1.8),
                explode=[0.03] * len(values),
            )
            for at in autotexts:
                at.set_fontsize(6.5)
                at.set_color("white")
                at.set_fontweight("bold")
            ax.text(0, 0, str(total), ha="center", va="center",
                    fontsize=13, fontweight="bold", color=TEXT_PRIMARY)
            ax.text(0, -0.28, "projects", ha="center", va="center",
                    fontsize=6, color=TEXT_SECONDARY)
        else:
            ax.text(0.5, 0.5, "No projects", ha="center", va="center",
                    transform=ax.transAxes, color="#B0BEC5", fontsize=9)
            ax.axis("off")

        ax.set_aspect("equal")
        ax.grid(False)
        fig.tight_layout(pad=0.2)

        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background:transparent;")
        canvas.setFixedHeight(140)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay.addWidget(canvas)
        plt.close(fig)

        # Compact legend
        for label, val, color in zip(labels, values, colors):
            pct = val / total * 100 if total > 0 else 0
            item_row = QHBoxLayout(); item_row.setSpacing(5)
            dot = QLabel("●"); dot.setFixedWidth(12)
            dot.setStyleSheet(f"color:{color};font-size:9pt;background:transparent;")
            nm = make_label(label, 7, color=TEXT_SECONDARY)
            vl = make_label(f"{val}  ({pct:.0f}%)", 7, bold=True, color=color)
            vl.setAlignment(Qt.AlignRight)
            item_row.addWidget(dot)
            item_row.addWidget(nm)
            item_row.addStretch()
            item_row.addWidget(vl)
            lay.addLayout(item_row)

        lay.addStretch()
        return card

    # ── Project Phase Donut ───────────────────────────────────────────────────
    def _build_phase_donut_card(self):
        """Donut chart: % of projects in each phase (Phase 1 … Phase 5)."""
        card = CardFrame()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        lay.addWidget(make_label("Projects by Phase", FONT_SIZE_SM, bold=True))

        projects = self._cached_projects
        phase_counts = {}
        for p in projects:
            ph = p.get("phase") or "Unknown"
            phase_counts[ph] = phase_counts.get(ph, 0) + 1

        all_phases = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]
        extra = [ph for ph in phase_counts if ph not in all_phases]
        ordered = all_phases + extra
        labels = [ph for ph in ordered if phase_counts.get(ph, 0) > 0]
        values = [phase_counts[ph] for ph in labels]
        colors = [PHASE_COLORS.get(ph, "#90A4AE") for ph in labels]
        total  = sum(values)

        fig, ax = plt.subplots(figsize=(2.6, 2.1))
        fig.patch.set_facecolor("none")
        ax.set_facecolor("none")

        if total > 0:
            wedges, _, autotexts = ax.pie(
                values,
                labels=None,
                colors=colors,
                autopct=lambda p: f"{p:.0f}%" if p > 6 else "",
                pctdistance=0.72,
                startangle=90,
                wedgeprops=dict(width=0.50, edgecolor="white", linewidth=1.8),
                explode=[0.03] * len(values),
            )
            for at in autotexts:
                at.set_fontsize(6.5)
                at.set_color("white")
                at.set_fontweight("bold")
            ax.text(0, 0, str(total), ha="center", va="center",
                    fontsize=13, fontweight="bold", color=TEXT_PRIMARY)
            ax.text(0, -0.28, "projects", ha="center", va="center",
                    fontsize=6, color=TEXT_SECONDARY)
        else:
            ax.text(0.5, 0.5, "No projects", ha="center", va="center",
                    transform=ax.transAxes, color="#B0BEC5", fontsize=9)
            ax.axis("off")

        ax.set_aspect("equal")
        ax.grid(False)
        fig.tight_layout(pad=0.2)

        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background:transparent;")
        canvas.setFixedHeight(140)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay.addWidget(canvas)
        plt.close(fig)

        # Compact legend
        for label, val, color in zip(labels, values, colors):
            pct = val / total * 100 if total > 0 else 0
            item_row = QHBoxLayout(); item_row.setSpacing(5)
            dot = QLabel("●"); dot.setFixedWidth(12)
            dot.setStyleSheet(f"color:{color};font-size:9pt;background:transparent;")
            nm = make_label(label, 7, color=TEXT_SECONDARY)
            vl = make_label(f"{val}  ({pct:.0f}%)", 7, bold=True, color=color)
            vl.setAlignment(Qt.AlignRight)
            item_row.addWidget(dot)
            item_row.addWidget(nm)
            item_row.addStretch()
            item_row.addWidget(vl)
            lay.addLayout(item_row)

        lay.addStretch()
        return card

    # ── Budget Bars Card (horizontal stacked) ─────────────────────────────────
    def _build_budget_bars_card(self, stats):
        """
        Right panel: horizontal stacked bar showing consumed vs remaining.
        Solves the scale imbalance — uses percentage-based bar, always readable.
        Secondary: absolute values labelled directly on bars.
        """
        card = CardFrame()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        planned   = stats.get("planned_budget", 0)
        actual    = stats.get("actual_cost",    0)
        remaining = max(planned - actual, 0)
        pct       = (actual / planned * 100) if planned > 0 else 0
        pct_color = ("#E53935" if pct > 90 else "#FB8C00" if pct > 75 else "#43A047")

        # Card header
        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Budget — Consumed vs Remaining",
                                  FONT_SIZE_MD, bold=True))
        hdr.addStretch()
        badge = QLabel(f"{pct:.1f}% used")
        badge.setStyleSheet(
            f"background:{pct_color}22;color:{pct_color};"
            f"border-radius:10px;padding:3px 12px;"
            f"font-size:9pt;font-weight:bold;font-family:{FONT_FAMILY};"
        )
        hdr.addWidget(badge)
        lay.addLayout(hdr)

        # Build chart
        fig, ax = plt.subplots(figsize=(6.5, 3.2))
        fig.patch.set_facecolor("none")
        ax.set_facecolor("none")

        if planned > 0:
            pct_consumed  = min(pct, 100)
            pct_remaining = max(100 - pct_consumed, 0)

            # Stacked horizontal bar (percentage-based so always visible)
            ax.barh(["Budget"], [pct_consumed],   color=pct_color,   height=0.55,
                    edgecolor="none", alpha=0.9, label=f"Consumed ({self._fmt(actual)})")
            ax.barh(["Budget"], [pct_remaining], left=[pct_consumed],
                    color="#ECEFF1", height=0.55, edgecolor="none", alpha=0.9,
                    label=f"Remaining ({self._fmt(remaining)})")

            # Label consumed part
            if pct_consumed > 8:
                ax.text(pct_consumed / 2, 0, f"{pct_consumed:.1f}%",
                        va="center", ha="center", fontsize=11,
                        fontweight="bold", color="white")
            else:
                ax.text(pct_consumed + 1, 0, f"{pct_consumed:.1f}%",
                        va="center", ha="left", fontsize=10,
                        fontweight="bold", color=pct_color)

            # Label remaining part
            if pct_remaining > 10:
                ax.text(pct_consumed + pct_remaining / 2, 0, self._fmt(remaining),
                        va="center", ha="center", fontsize=9,
                        color=TEXT_SECONDARY)

            ax.set_xlim(0, 105)
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        else:
            ax.text(0.5, 0.5, "No budget defined yet", ha="center", va="center",
                    transform=ax.transAxes, color="#B0BEC5", fontsize=11)
            ax.axis("off")

        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color(BORDER)
        ax.tick_params(axis="x", labelsize=8, colors=TEXT_SECONDARY, length=0)
        ax.tick_params(axis="y", labelsize=9, colors=TEXT_PRIMARY, length=0)
        ax.set_axisbelow(True)
        ax.grid(axis="x", alpha=0.15)

        # Legend
        if planned > 0:
            legend = ax.legend(
                loc="lower center", bbox_to_anchor=(0.5, -0.48),
                ncol=2, fontsize=8.5, frameon=False,
                labelcolor=TEXT_SECONDARY
            )

        fig.tight_layout(pad=0.6)
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background:transparent;")
        canvas.setMinimumHeight(165)
        lay.addWidget(canvas)
        plt.close(fig)

        # ── Secondary: absolute value bars (planned vs consumed) ──────────────
        lay.addSpacing(8)
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"color:{BORDER};background:{BORDER};")
        divider.setFixedHeight(1)
        lay.addWidget(divider)
        lay.addSpacing(6)
        lay.addWidget(make_label("Absolute Values", FONT_SIZE_SM - 1,
                                  bold=True, color=TEXT_SECONDARY))
        lay.addSpacing(4)

        metrics = [
            ("Planned Budget", planned,   PRIMARY,    1.0),
            ("Actual Cost",    actual,     pct_color,  actual / planned if planned > 0 else 0),
            ("Remaining",      remaining,  "#43A047",  remaining / planned if planned > 0 else 0),
        ]
        for label, value, color, ratio in metrics:
            m_row = QHBoxLayout()
            m_row.setSpacing(8)

            name_lbl = make_label(label, FONT_SIZE_SM - 1, color=TEXT_SECONDARY)
            name_lbl.setFixedWidth(110)

            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(int(min(ratio, 1.0) * 1000))
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(
                f"QProgressBar{{border:none;border-radius:4px;background:#ECEFF1;}}"
                f"QProgressBar::chunk{{background:{color};border-radius:4px;}}"
            )

            val_lbl = make_label(self._fmt(value), FONT_SIZE_SM, bold=True, color=color)
            val_lbl.setFixedWidth(80)
            val_lbl.setAlignment(Qt.AlignRight)

            m_row.addWidget(name_lbl)
            m_row.addWidget(bar, 1)
            m_row.addWidget(val_lbl)
            lay.addLayout(m_row)

        lay.addStretch()
        return card

    # ── Progress Overview ─────────────────────────────────────────────────────
    def _build_progress_overview(self):
        card = CardFrame()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        projects = self._cached_projects

        if not projects:
            lay.addWidget(
                make_label(
                    "No projects yet. Import or create a project to get started.",
                    FONT_SIZE_SM, color=TEXT_SECONDARY
                )
            )
            return card

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Completion progress per project",
                                  FONT_SIZE_SM, color=TEXT_SECONDARY))
        hdr.addStretch()
        hdr.addWidget(make_label(f"Showing {min(len(projects), 8)} of {len(projects)}",
                                  FONT_SIZE_SM, color=TEXT_SECONDARY))
        lay.addLayout(hdr)

        for i, p in enumerate(projects[:8]):
            row = QHBoxLayout()
            row.setSpacing(12)

            pid_lbl = make_label(p.get("project_id", "")[:12], FONT_SIZE_SM - 1, color=PRIMARY)
            pid_lbl.setFixedWidth(80)
            pid_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            name_lbl = make_label(p.get("name", "")[:28], FONT_SIZE_SM)
            name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            name_lbl.setMinimumWidth(80)
            name_lbl.setMaximumWidth(180)

            badge = StatusBadge(p.get("status", "Active"))

            prog  = p.get("progress", 0)
            color = STATUS_COLORS.get(p.get("status", "Active"), PRIMARY)
            pb    = StyledProgressBar(prog, color)
            pb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            pct_lbl = make_label(f"{prog:.0f}%", FONT_SIZE_SM, bold=True, color=color)
            pct_lbl.setFixedWidth(42)
            pct_lbl.setAlignment(Qt.AlignRight)

            row.addWidget(pid_lbl)
            row.addWidget(name_lbl)
            row.addWidget(badge)
            row.addWidget(pb, 1)
            row.addWidget(pct_lbl)
            lay.addLayout(row)

            if i < min(len(projects), 8) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet(f"color:{BORDER};background:{BORDER};")
                sep.setFixedHeight(1)
                lay.addWidget(sep)

        return card

    # ── Upcoming Deadlines Table ──────────────────────────────────────────────
    def _build_deadlines_table(self, stats):
        card = CardFrame()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        rows_data = stats.get("upcoming_deadlines", [])

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Open actions in each project's current phase",
                                  FONT_SIZE_SM, color=TEXT_SECONDARY))
        hdr.addStretch()
        cnt_color = "#E53935" if len(rows_data) > 5 else TEXT_SECONDARY
        hdr.addWidget(make_label(f"{len(rows_data)} items", FONT_SIZE_SM, color=cnt_color))
        lay.addLayout(hdr)

        if not rows_data:
            lay.addWidget(make_label("  🎉  No upcoming deadlines", FONT_SIZE_SM, color=TEXT_SECONDARY))
            return card

        table = QTableWidget(len(rows_data), 4)
        table.setHorizontalHeaderLabels(["Project", "Action / Gate", "Due Date", "Status"])
        table.setStyleSheet(TABLE_QSS)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.setFixedHeight(min(54 + len(rows_data) * 40, 300))

        for i, r in enumerate(rows_data):
            table.setRowHeight(i, 40)
            proj_item = QTableWidgetItem(r.get("project_name", ""))
            proj_item.setForeground(QColor(PRIMARY))
            proj_item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
            table.setItem(i, 0, proj_item)
            table.setItem(i, 1, QTableWidgetItem(r.get("action_name", "")))
            table.setItem(i, 2, QTableWidgetItem(r.get("end_date", "")))

            badge  = StatusBadge(r.get("status", "Open"))
            cell_w = QWidget()
            cell_l = QHBoxLayout(cell_w)
            cell_l.setContentsMargins(6, 2, 6, 2)
            cell_l.addStretch()
            cell_l.addWidget(badge)
            cell_l.addStretch()
            table.setCellWidget(i, 3, cell_w)

        lay.addWidget(table)
        return card

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _fmt(self, v) -> str:
        v = v or 0
        if v >= 1_000_000: return f"€{v / 1_000_000:.2f}M"
        if v >= 1_000:     return f"€{v / 1_000:.0f}K"
        return f"€{v:.0f}"

    # ── KPI Dashboard Section ─────────────────────────────────────────────────
    def _build_kpi_dashboard_section(self):
        import datetime, os
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton, QGridLayout
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

        year = datetime.date.today().year
        def _is_hidden_kpi(k):
            name = k.get("name", "").lower()
            # Remove: R@R 1st Score, R@R Released vs Planned, Total Transport Cost %
            if "r@r" in name or "r&r" in name:
                return True
            if "transport" in name and "cost" in name:
                return True
            return False
        kpis = [k for k in get_all_kpis() if not _is_hidden_kpi(k)]

        outer = QWidget(); outer.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(outer); lay.setContentsMargins(0,0,0,0); lay.setSpacing(16)

        if not kpis:
            lbl = make_label("No KPIs configured yet — go to the KPI section in the sidebar to add them.",
                              FONT_SIZE_SM, color=TEXT_SECONDARY)
            lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(lbl)
            return outer

        # ── RAG summary strip ────────────────────────────────────────────────
        from app.models.project_model import get_kpi_scores

        def rag(score, target, unit):
            if score is None: return "#F5F7FA", TEXT_SECONDARY
            try: score, target = float(score), float(target)
            except: return "#F5F7FA", TEXT_SECONDARY
            lower = any(kw in unit.lower() for kw in ["€","mad","days"]) or target == 0
            pct = score / max(target, 0.01)
            if lower:
                if pct <= 1.0: return "#C8E6C9","#1B5E20"
                if pct <= 1.3: return "#FFF9C4","#F57F17"
                return "#FFCDD2","#B71C1C"
            else:
                if pct >= 1.0: return "#C8E6C9","#1B5E20"
                if pct >= 0.8: return "#FFF9C4","#F57F17"
                return "#FFCDD2","#B71C1C"

        strip_card = CardFrame(); strip_lay = QHBoxLayout(strip_card)
        strip_lay.setContentsMargins(16,12,16,12); strip_lay.setSpacing(12)
        add_shadow(strip_card)

        for kpi in kpis:
            scores = get_kpi_scores(kpi["id"], year)
            latest = next((s for s in reversed(scores) if s.get("score") is not None), None)
            score_val = latest["score"] if latest else None
            bg, fg = rag(score_val, kpi["target"], kpi["unit"])

            cell = QFrame()
            cell.setStyleSheet(f"background:{bg};border-radius:{RADIUS}px;border:none;")
            cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            cl = QVBoxLayout(cell); cl.setContentsMargins(10,8,10,8); cl.setSpacing(2)

            name_lbl = QLabel(kpi["name"])
            name_lbl.setWordWrap(True)
            name_lbl.setFont(QFont(FONT_FAMILY, 7, QFont.Bold))
            name_lbl.setStyleSheet(f"color:{fg};background:transparent;")
            name_lbl.setAlignment(Qt.AlignCenter)
            cl.addWidget(name_lbl)

            val_text = f"{score_val:.1f} {kpi['unit']}" if score_val is not None else "—"
            val_lbl = QLabel(val_text)
            val_lbl.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
            val_lbl.setStyleSheet(f"color:{fg};background:transparent;")
            val_lbl.setAlignment(Qt.AlignCenter)
            cl.addWidget(val_lbl)

            cat_lbl = QLabel(kpi["category"])
            cat_lbl.setFont(QFont(FONT_FAMILY, 6))
            cat_lbl.setStyleSheet(f"color:{fg};background:transparent;opacity:0.7;")
            cat_lbl.setAlignment(Qt.AlignCenter)
            cl.addWidget(cat_lbl)

            strip_lay.addWidget(cell, 1)

        lay.addWidget(strip_card)

        # ── 2-column chart grid ──────────────────────────────────────────────
        grid_w = QWidget(); grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w); grid.setSpacing(16); grid.setContentsMargins(0,0,0,0)

        self._dash_kpi_figs = []

        for i, kpi in enumerate(kpis):
            scores     = get_kpi_scores(kpi["id"], year)
            months_idx = ["Jan","Feb","Mar","Apr","May","Jun",
                          "Jul","Aug","Sep","Oct","Nov","Dec"]
            score_map  = {s["month"]: s for s in scores}
            target_val = float(kpi["target"] or 1)
            lower_better = (any(kw in kpi["unit"].lower()
                               for kw in ["€","mad","days","count"])
                            and target_val == 0)

            all_months = list(range(1, 13))
            labels = [months_idx[m-1] for m in all_months]
            vals   = [score_map[m]["score"] if m in score_map
                      and score_map[m].get("score") is not None else None
                      for m in all_months]
            bar_vals = [v if v is not None else 0 for v in vals]

            # Chart card
            chart_card = CardFrame()
            add_shadow(chart_card)
            cc_lay = QVBoxLayout(chart_card)
            cc_lay.setContentsMargins(14,12,14,12); cc_lay.setSpacing(8)

            # Card header
            ch = QHBoxLayout()
            title_lbl = make_label(kpi["name"], FONT_SIZE_SM, bold=True)
            title_lbl.setWordWrap(True)
            ch.addWidget(title_lbl, stretch=1)

            # snapshot button
            snap_btn = QPushButton("📷")
            snap_btn.setFixedSize(28, 26)
            snap_btn.setToolTip("Save chart as image")
            snap_btn.setStyleSheet(f"""
                QPushButton{{background:{ACCENT};color:white;border:none;
                border-radius:6px;font-size:10pt;}}
                QPushButton:hover{{background:#00838F;}}
            """)
            ch.addWidget(snap_btn)
            cc_lay.addLayout(ch)

            cat_lbl = make_label(
                f"{kpi['category']}  ·  Target: {target_val:.4g} {kpi['unit']}",
                7, color=TEXT_SECONDARY)
            cc_lay.addWidget(cat_lbl)

            # Matplotlib chart — full 12 months
            fig, ax = plt.subplots(figsize=(5.2, 2.0))
            fig.patch.set_facecolor("none"); ax.set_facecolor("none")

            bar_colors = []
            bar_alphas = []
            for v in vals:
                if v is None:
                    bar_colors.append("#E8EEF4"); bar_alphas.append(0.35)
                else:
                    good = (v <= target_val) if lower_better else (v >= target_val)
                    bar_colors.append("#4CAF50" if good else "#EF5350")
                    bar_alphas.append(0.85)

            bars = ax.bar(labels, bar_vals, color=bar_colors, width=0.6,
                          edgecolor="white", linewidth=0.5)
            for bar, alpha in zip(bars, bar_alphas):
                bar.set_alpha(alpha)

            ax.axhline(target_val, color="#1565C0", linestyle="--",
                       linewidth=1.2, label=f"Target {target_val:.4g}", zorder=5)
            # Place legend in the corner with fewest bars to avoid obscuring data
            _nonzero = sum(1 for v in bar_vals if v > 0)
            _leg_loc = "upper right" if _nonzero > 6 else "upper left"
            ax.legend(fontsize=5.5, loc=_leg_loc, framealpha=0.7,
                      bbox_to_anchor=(1.0, 1.0) if _leg_loc == "upper right" else None)

            for bar, v in zip(bars, vals):
                if v is not None and v != 0:
                    ax.text(bar.get_x()+bar.get_width()/2,
                            bar.get_height() + max(bar_vals)*0.02,
                            f"{v:.4g}", ha="center", va="bottom",
                            fontsize=5.5, color="#212121", fontweight="bold")

            ax.set_ylabel(kpi["unit"], fontsize=6, color=TEXT_SECONDARY)
            ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
            ax.tick_params(axis="both", labelsize=5.5, colors=TEXT_SECONDARY)
            ax.spines["left"].set_color(BORDER); ax.spines["bottom"].set_color(BORDER)
            y_max_d = max(bar_vals + [float(kpi["target"] or 0)] + [1])
            ax.set_ylim(0, y_max_d * 1.42)
            fig.tight_layout(pad=0.3)

            canvas = FigureCanvas(fig)
            canvas.setStyleSheet("background:transparent;")
            canvas.setFixedHeight(160)
            canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            cc_lay.addWidget(canvas)
            self._dash_kpi_figs.append((fig, kpi["name"]))

            # Wire snapshot button
            def make_snap(f, kname):
                def _snap():
                    default = f"KPI_{kname.replace(' ','_')}_{year}.png"
                    path, _ = QFileDialog.getSaveFileName(
                        self._inner, "Save Chart", default, "PNG Images (*.png)")
                    if path:
                        f.savefig(path, dpi=150, bbox_inches="tight",
                                  facecolor="white", edgecolor="none")
                        QMessageBox.information(self._inner, "Saved",
                                                f"Chart saved:\n{path}")
                return _snap
            snap_btn.clicked.connect(make_snap(fig, kpi["name"]))

            # Stats strip
            valid_vals = [v for v in vals if v is not None]
            if valid_vals:
                avg = sum(valid_vals)/len(valid_vals)
                tgt_val = float(kpi["target"] or 1)
                stats_row = QHBoxLayout(); stats_row.setSpacing(16)
                for lbl_text, val_text in [
                    ("Avg", f"{avg:.1f}"),
                    ("Min", f"{min(valid_vals):.1f}"),
                    ("Max", f"{max(valid_vals):.1f}"),
                    ("vs Target", f"{avg/tgt_val*100:.0f}%"),
                ]:
                    sc = QVBoxLayout(); sc.setSpacing(0)
                    sc.addWidget(make_label(val_text, FONT_SIZE_SM, bold=True, color=PRIMARY))
                    sc.addWidget(make_label(lbl_text, 7, color=TEXT_SECONDARY))
                    stats_row.addLayout(sc)
                stats_row.addStretch()
                cc_lay.addLayout(stats_row)

            row_i, col_i = divmod(i, 2)
            grid.addWidget(chart_card, row_i, col_i)

        lay.addWidget(grid_w)
        return outer

    def _on_filter_change(self, _):
        self._selected_project = self.proj_combo.currentData()
        self.refresh()

    def refresh(self):
        # Close any open matplotlib figures to prevent memory leaks
        if hasattr(self, "_dash_kpi_figs"):
            for fig, _ in self._dash_kpi_figs:
                try:
                    plt.close(fig)
                except Exception:
                    pass
            self._dash_kpi_figs = []

        self._inner.setUpdatesEnabled(False)  # suppress all repaints during rebuild
        try:
            def _clear(layout):
                while layout.count():
                    item = layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                    elif item.layout():
                        _clear(item.layout())
            _clear(self._lay)
            self._build()
        finally:
            self._inner.setUpdatesEnabled(True)

