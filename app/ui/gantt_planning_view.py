"""
gantt_planning_view.py  ·  v10 — Compact Precision Gantt
═══════════════════════════════════════════════════════════════════════════════
Design principles:
  • Thin bars (30 % of row height) — clean industrial look
  • Compact row height — no wasted vertical space
  • Two-level header: Month (taller) / Week-number (shorter)
  • Left table: Task Name | Start | End | Duration — no text overlap
  • Bars start exactly on the task's true start date (pixel-perfect)
  • Today line — red dashed, correctly anchored
  • Progress darker fill inside bar
  • Zero hardcoded tasks — 100 % driven by DB
"""
from __future__ import annotations
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFileDialog,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ── App imports ───────────────────────────────────────────────────────────────
try:
    from app.utils.theme import (
        PRIMARY, BG, BG_CARD, BORDER,
        TEXT_PRIMARY, TEXT_SECONDARY, FONT_FAMILY,
        FONT_SIZE_SM, FONT_SIZE_MD,
    )
    from app.utils.widgets import make_label
    from app.models.project_model import (
        get_industrialisation_actions,
        iso_to_display,
    )
    _HAS_APP = True
except ImportError:
    _HAS_APP = False
    PRIMARY = "#1565C0"; BG = "#F5F7FA"; BG_CARD = "#FFFFFF"; BORDER = "#E0E7EF"
    TEXT_PRIMARY = "#1A2035"; TEXT_SECONDARY = "#607080"
    FONT_FAMILY = "Segoe UI"; FONT_SIZE_SM = 9; FONT_SIZE_MD = 11

    def make_label(text, size=9, bold=False, color=TEXT_PRIMARY):
        lbl = QLabel(text)
        f = QFont(); f.setPointSize(size)
        if bold: f.setBold(True)
        lbl.setFont(f); lbl.setStyleSheet(f"color:{color};background:transparent;")
        return lbl

    def iso_to_display(s):
        try: return date.fromisoformat(s).strftime("%d %b %Y")
        except: return s or ""


# ═══════════════════════════════════════════════════════════════════════════════
# Design tokens — everything tuned for compactness
# ═══════════════════════════════════════════════════════════════════════════════

FIG_BG        = "#F4F6F9"

# Left table
TBL_HDR_BG    = "#1B3A5C"
TBL_HDR_FG    = "#FFFFFF"
TBL_ROW_A     = "#FFFFFF"
TBL_ROW_B     = "#F0F5FB"
TBL_BORDER    = "#D0DCF0"
TBL_TEXT      = "#1C2E44"
TBL_TEXT_DIM  = "#6B7E96"
TBL_SEP       = "#BFD0E8"         # column separator inside header/rows

# Chart area
CHT_ROW_A     = "#FAFCFF"
CHT_ROW_B     = "#EEF4FC"
GRID_MONTH    = "#8FA8C8"          # solid month boundary
GRID_WEEK     = "#D4E2F2"          # faint week tick

# Today
TODAY_COL     = "#E53935"

# Department bar colours — same as v9
DEPT_COLORS = {
    "Purchasing":           "#3A7FD5",
    "Global Buyer":         "#1E5FA8",
    "PM":                   "#1E9E94",
    "Finance":              "#2A7D32",
    "Process Engineering":  "#E67E22",
    "Engineering":          "#D35400",
    "DK team":              "#795548",
    "Quality":              "#7B1FA2",
    "Logistics":            "#B71C6A",
}
DEFAULT_COLOR = "#607D8B"

# ── Compact geometry (all in data-units) ──────────────────────────────────────
ROW_H      = 0.46      # total row height  ← was 0.76
BAR_FRAC   = 0.32      # bar height as fraction of ROW_H  (thin!)
HDR_MONTH  = 0.48      # month header band height
HDR_WEEK   = 0.34      # week-number band height
HDR_H      = HDR_MONTH + HDR_WEEK   # combined header height

# Left table column widths (x = 0 is left edge)
COL_NAME   = 3.00      # task name column
COL_START  = 1.55      # start date
COL_END    = 1.55      # end date
COL_DUR    = 0.90      # duration
TABLE_W    = COL_NAME + COL_START + COL_END + COL_DUR   # ≈ 7.00

TOP_PAD    = 1.60      # space above header for title + legend

# Typography sizes (points-ish in matplotlib)
TITLE_SZ   = 11.5
HDR_SZ     = 7.5
ROW_SZ     = 7.0
MONTH_SZ   = 8.0
WEEK_SZ    = 6.0
LEGEND_SZ  = 6.5

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size":   7,
    "figure.dpi":  130,
    "axes.linewidth": 0.3,
})

# DPI used for canvas sizing
_DPI = 130


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _x(d: date, origin: date) -> float:
    """Days from origin → x coordinate on chart."""
    return float((d - origin).days)

def _fmt_short(d: date) -> str:
    return d.strftime("%d %b")

def _dur_str(sd: date, ed: date) -> str:
    days = max((ed - sd).days, 1)
    if days < 7: return f"{days}d"
    w, r = divmod(days, 7)
    return f"{w}w" if r == 0 else f"{w}w{r}d"

def _month_spans(t0: date, t1: date):
    """Yield (label, x_start, x_end) relative to t0 for each calendar month."""
    cur = date(t0.year, t0.month, 1)
    while cur <= t1:
        nxt = date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)
        m_s = max(cur, t0)
        m_e = min(nxt - timedelta(days=1), t1)
        yield cur.strftime("%b %Y"), _x(m_s, t0), _x(m_e, t0)
        cur = nxt

def _week_ticks(t0: date, t1: date):
    """Yield (label, x) for each Monday in [t0, t1]."""
    cur = t0 + timedelta(days=(7 - t0.weekday()) % 7)
    while cur <= t1:
        yield f"W{cur.isocalendar()[1]}", _x(cur, t0)
        cur += timedelta(weeks=1)

def _darken(hex_col: str, amt: float) -> str:
    h = hex_col.lstrip("#")
    r = max(0, int(h[0:2], 16) - int(255 * amt))
    g = max(0, int(h[2:4], 16) - int(255 * amt))
    b = max(0, int(h[4:6], 16) - int(255 * amt))
    return f"#{r:02X}{g:02X}{b:02X}"

def _rect(ax, x, y, w, h, fc, ec="none", lw=0, **kw):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc,
                            edgecolor=ec, linewidth=lw, **kw))


# ═══════════════════════════════════════════════════════════════════════════════
# Renderer
# ═══════════════════════════════════════════════════════════════════════════════

class GanttRenderer:

    def __init__(self, tasks: list):
        self.tasks  = tasks
        self.today  = date.today()
        if tasks:
            self.t0 = min(t["start_date"] for t in tasks) - timedelta(days=4)
            self.t1 = max(t["end_date"]   for t in tasks) + timedelta(days=8)
        else:
            self.t0 = self.today - timedelta(days=30)
            self.t1 = self.today + timedelta(days=60)
        self.span = (self.t1 - self.t0).days   # total days on chart

    # ── entry point ───────────────────────────────────────────────────────────
    def render(self, fig: Figure):
        fig.clf()
        fig.patch.set_facecolor(FIG_BG)
        n = len(self.tasks)

        if n == 0:
            ax = fig.add_subplot(111)
            ax.set_facecolor(FIG_BG); ax.axis("off")
            ax.text(0.5, 0.5,
                    "No industrialisation actions.\nAdd them in the Planning tab.",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=10, color=TBL_TEXT_DIM)
            return

        total_h = TOP_PAD + HDR_H + n * ROW_H + 0.25
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, TABLE_W + self.span + 0.3)
        ax.set_ylim(0, total_h)
        ax.invert_yaxis()
        ax.axis("off")
        ax.set_facecolor(FIG_BG)

        y0 = TOP_PAD   # y where header row starts

        self._title_legend(ax)
        self._tbl_header(ax, y0)
        self._cht_header(ax, y0)
        self._rows(ax, y0)
        self._today(ax, y0, total_h)

    # ── title + legend ────────────────────────────────────────────────────────
    def _title_legend(self, ax):
        ax.text(0.15, 0.38, "Project Gantt Chart",
                ha="left", va="center",
                fontsize=TITLE_SZ, fontweight="bold", color=TBL_TEXT, zorder=10)
        ax.text(0.15, 0.80, f"Today  {self.today.strftime('%d %b %Y')}",
                ha="left", va="center",
                fontsize=6.5, color=TODAY_COL, zorder=10)

        # Legend — compact inline swatches
        seen = {}
        for t in self.tasks:
            d = t["department"]
            if d not in seen:
                seen[d] = DEPT_COLORS.get(d, DEFAULT_COLOR)

        lx = TABLE_W + 0.8
        ly = 0.60
        sw, sh = 0.40, 0.22
        for dept, col in seen.items():
            label_w = len(dept) * 0.095 + sw + 0.18 + 0.25
            if lx + label_w > TABLE_W + self.span - 0.3:
                lx = TABLE_W + 0.8; ly += 0.38
            _rect(ax, lx, ly - sh / 2, sw, sh, fc=col,
                  ec=_darken(col, 0.18), lw=0.5, zorder=6)
            ax.text(lx + sw + 0.14, ly, dept,
                    ha="left", va="center",
                    fontsize=LEGEND_SZ, color=TBL_TEXT, zorder=6)
            lx += label_w

    # ── left table header ─────────────────────────────────────────────────────
    def _tbl_header(self, ax, y0):
        # Background spanning both month+week rows
        _rect(ax, 0, y0, TABLE_W, HDR_H, fc=TBL_HDR_BG, zorder=3)

        defs = [
            ("Task Name",  COL_NAME / 2,                                    "left",   0.14),
            ("Start",      COL_NAME + COL_START / 2,                        "center", 0),
            ("End",        COL_NAME + COL_START + COL_END / 2,              "center", 0),
            ("Dur.",       TABLE_W - COL_DUR / 2,                           "center", 0),
        ]
        for label, x, ha, off in defs:
            ax.text(x + off, y0 + HDR_H / 2, label,
                    ha=ha, va="center",
                    fontsize=HDR_SZ, fontweight="bold",
                    color=TBL_HDR_FG, zorder=4)

        for xd in [COL_NAME,
                   COL_NAME + COL_START,
                   COL_NAME + COL_START + COL_END]:
            ax.plot([xd, xd], [y0, y0 + HDR_H],
                    color="#3A6FA5", lw=0.5, zorder=4)
        ax.plot([0, TABLE_W], [y0 + HDR_H, y0 + HDR_H],
                color=TBL_BORDER, lw=0.6, zorder=4)

    # ── chart header: month + week ────────────────────────────────────────────
    def _cht_header(self, ax, y0):
        cx = TABLE_W

        # Month band
        _rect(ax, cx, y0, self.span, HDR_MONTH, fc=TBL_HDR_BG, zorder=3)
        for m_lbl, xs, xe in _month_spans(self.t0, self.t1):
            mid = cx + (xs + xe) / 2
            ax.text(mid, y0 + HDR_MONTH / 2, m_lbl,
                    ha="center", va="center",
                    fontsize=MONTH_SZ, fontweight="bold",
                    color=TBL_HDR_FG, zorder=4)
            ax.plot([cx + xs, cx + xs], [y0, y0 + HDR_MONTH],
                    color="#4A7FBF", lw=0.9, zorder=5)

        # Week band
        wy = y0 + HDR_MONTH
        _rect(ax, cx, wy, self.span, HDR_WEEK, fc="#24527A", zorder=3)
        for w_lbl, wx in _week_ticks(self.t0, self.t1):
            ax.text(cx + wx + 3.3, wy + HDR_WEEK / 2, w_lbl,
                    ha="center", va="center",
                    fontsize=WEEK_SZ, color="#C8DFF5", zorder=4)
            ax.plot([cx + wx, cx + wx], [wy, wy + HDR_WEEK],
                    color="#3A6FA5", lw=0.35, zorder=4)

        # Bottom separator
        ax.plot([cx, cx + self.span],
                [y0 + HDR_H, y0 + HDR_H],
                color=TBL_BORDER, lw=0.6, zorder=4)

    # ── rows (table + bars) ───────────────────────────────────────────────────
    def _rows(self, ax, y0):
        row0  = y0 + HDR_H
        cx    = TABLE_W

        # Pre-compute grid x positions
        week_xs  = [cx + wx for _, wx in _week_ticks(self.t0, self.t1)]
        month_xs = [cx + xs for _, xs, _ in _month_spans(self.t0, self.t1)]

        for i, task in enumerate(self.tasks):
            y      = row0 + i * ROW_H
            alt    = i % 2 == 1
            r_bg   = TBL_ROW_B  if alt else TBL_ROW_A
            c_bg   = CHT_ROW_B  if alt else CHT_ROW_A

            # Row backgrounds
            _rect(ax, 0,  y, TABLE_W,    ROW_H, fc=r_bg, zorder=1)
            _rect(ax, cx, y, self.span,  ROW_H, fc=c_bg, zorder=1)

            # Grid lines
            for wx in week_xs:
                ax.plot([wx, wx], [y, y + ROW_H],
                        color=GRID_WEEK, lw=0.30, zorder=2)
            for mx in month_xs:
                ax.plot([mx, mx], [y, y + ROW_H],
                        color=GRID_MONTH, lw=0.70, zorder=2)

            # Row separators
            ax.plot([0, cx + self.span], [y + ROW_H, y + ROW_H],
                    color=TBL_BORDER, lw=0.30, zorder=3)

            # Column dividers (table side)
            for xd in [COL_NAME,
                       COL_NAME + COL_START,
                       COL_NAME + COL_START + COL_END]:
                ax.plot([xd, xd], [y, y + ROW_H],
                        color=TBL_SEP, lw=0.30, zorder=3)
            # Table/chart boundary
            ax.plot([cx, cx], [y, y + ROW_H],
                    color=TBL_BORDER, lw=0.50, zorder=3)

            mid_y = y + ROW_H / 2

            # ── Task name ─────────────────────────────────────────────────────
            name = task["name"]
            # truncate to fit
            max_ch = 30
            if len(name) > max_ch: name = name[:max_ch - 1] + "…"
            ax.text(0.13, mid_y, name,
                    ha="left", va="center",
                    fontsize=ROW_SZ, color=TBL_TEXT, zorder=4,
                    clip_on=True)

            # ── Start date ────────────────────────────────────────────────────
            ax.text(COL_NAME + COL_START / 2, mid_y,
                    _fmt_short(task["start_date"]),
                    ha="center", va="center",
                    fontsize=ROW_SZ - 0.5, color=TBL_TEXT_DIM, zorder=4)

            # ── End date ──────────────────────────────────────────────────────
            ax.text(COL_NAME + COL_START + COL_END / 2, mid_y,
                    _fmt_short(task["end_date"]),
                    ha="center", va="center",
                    fontsize=ROW_SZ - 0.5, color=TBL_TEXT_DIM, zorder=4)

            # ── Duration ──────────────────────────────────────────────────────
            ax.text(TABLE_W - COL_DUR / 2, mid_y,
                    _dur_str(task["start_date"], task["end_date"]),
                    ha="center", va="center",
                    fontsize=ROW_SZ - 0.5, color=TBL_TEXT_DIM, zorder=4)

            # ── Gantt bar — thin, precise ──────────────────────────────────────
            sd    = task["start_date"]
            ed    = task["end_date"]
            bx    = cx + _x(sd, self.t0)          # exact pixel start
            bw    = max(_x(ed, self.t0) - _x(sd, self.t0), 0.40)
            bh    = ROW_H * BAR_FRAC               # thin bar
            by    = y + (ROW_H - bh) / 2           # vertically centred

            col   = DEPT_COLORS.get(task["department"], DEFAULT_COLOR)
            edge  = _darken(col, 0.20)

            # Base bar
            _rect(ax, bx, by, bw, bh,
                  fc=col, ec=edge, lw=0.5, zorder=5, alpha=0.93)

            # Progress fill (darker stripe)
            pct = min(max(task.get("pct", 0) / 100.0, 0.0), 1.0)
            if pct > 0:
                _rect(ax, bx, by, bw * pct, bh,
                      fc=_darken(col, 0.32), lw=0, zorder=6, alpha=0.90)

            # % label — only when bar is wide enough
            if bw >= 3.0 and pct > 0:
                lbl_x = bx + min(bw * pct / 2, bw - 0.2)
                ax.text(lbl_x, by + bh / 2, f"{int(pct*100)}%",
                        ha="center", va="center",
                        fontsize=5.5, color="white",
                        fontweight="bold", zorder=7)

    # ── today line ────────────────────────────────────────────────────────────
    def _today(self, ax, y0, total_h):
        if not (self.t0 <= self.today <= self.t1):
            return
        tx         = TABLE_W + _x(self.today, self.t0)
        rows_start = y0 + HDR_H
        ax.plot([tx, tx], [rows_start, total_h - 0.05],
                color=TODAY_COL, lw=1.4, linestyle="--", zorder=10, alpha=0.88)
        ax.text(tx, rows_start - 0.05, "▼",
                ha="center", va="bottom",
                fontsize=5.5, color=TODAY_COL, zorder=11)


# ═══════════════════════════════════════════════════════════════════════════════
# Data loader
# ═══════════════════════════════════════════════════════════════════════════════

def _load_tasks(project_id) -> list:
    if not _HAS_APP or not project_id:
        return _demo_tasks()
    rows = get_industrialisation_actions(project_id)
    if not rows:
        return []
    out = []
    for r in rows:
        try: sd = date.fromisoformat(r["start_date"])
        except: sd = date.today()
        try: ed = date.fromisoformat(r["end_date"])
        except: ed = sd + timedelta(weeks=float(r.get("lead_time_weeks", 2)))
        out.append({
            "id":         r["id"],
            "name":       r["action"],
            "department": r["department"],
            "start_date": sd,
            "end_date":   ed,
            "pct":        float(r.get("pct_complete", 0)),
            "status":     r.get("status", "Open"),
        })
    return out


def _demo_tasks() -> list:
    today = date.today()
    base  = today - timedelta(days=today.weekday())
    raw = [
        ("Purchasing",          "Quotation",                          -6,  3,  100),
        ("PM",                  "Budget on Zpbm",                     -4,  2,  100),
        ("Process Engineering", "PR Creation & validation",           -1,  4,   75),
        ("Purchasing",          "PO Submission",                       2,  3,   40),
        ("Global Buyer",        "Rubber availability in Dolny plant",  4,  5,   20),
        ("Global Buyer",        "Clamp availability in Dolny plant",   5,  4,    0),
        ("Global Buyer",        "Sleeve availability in Dolny plant",  6,  4,    0),
        ("DK team",             "Machines & LT Dev",                  -2,  8,   55),
        ("Process Engineering", "Validation",                         10,  3,    0),
    ]
    out = []
    for dept, name, wo, lt, pct in raw:
        sd = base + timedelta(weeks=wo)
        ed = sd + timedelta(weeks=lt)
        out.append({
            "id": 0, "name": name, "department": dept,
            "start_date": sd, "end_date": ed,
            "pct": float(pct),
            "status": "Done" if pct == 100 else "In Progress" if pct > 0 else "Open",
        })
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Qt Widget
# ═══════════════════════════════════════════════════════════════════════════════

class GanttPlanningView(QWidget):

    def __init__(self, project_id=None, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setStyleSheet(f"background:{FIG_BG};")
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────────────────
        tb = QWidget()
        tb.setFixedHeight(42)
        tb.setStyleSheet(f"background:{BG_CARD};border-bottom:1px solid {BORDER};")
        tbl = QHBoxLayout(tb)
        tbl.setContentsMargins(12, 0, 12, 0)
        tbl.setSpacing(8)

        lbl = QLabel("📊  Project Gantt Chart")
        lbl.setFont(QFont(FONT_FAMILY, FONT_SIZE_MD, QFont.Bold))
        lbl.setStyleSheet(f"color:{TEXT_PRIMARY};background:transparent;")
        tbl.addWidget(lbl)

        chip = QLabel(f"  Today: {date.today().strftime('%d %b %Y')}  ")
        chip.setStyleSheet(
            f"background:#FFF1F1;color:{TODAY_COL};"
            "border:1px solid #FFCDD2;border-radius:9px;"
            "padding:1px 8px;font-size:7.5pt;font-weight:bold;"
        )
        tbl.addWidget(chip)
        tbl.addStretch()

        src = QLabel("🔒 Source: Industrialisation Planning")
        src.setStyleSheet(f"color:{TEXT_SECONDARY};font-size:7.5pt;background:transparent;")
        tbl.addWidget(src)

        for txt, primary, slot in [
            ("⟳ Refresh",     False, "refresh"),
            ("💾 Export PNG",  True,  "_export_png"),
        ]:
            btn = QPushButton(txt)
            btn.setFixedHeight(28)
            if primary:
                btn.setStyleSheet(
                    f"QPushButton{{background:{TBL_HDR_BG};color:white;"
                    "border:none;border-radius:5px;padding:1px 12px;"
                    "font-weight:bold;font-size:8pt;}}"
                    "QPushButton:hover{background:#24527A;}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton{{background:transparent;color:{TEXT_SECONDARY};"
                    f"border:1px solid {BORDER};border-radius:5px;padding:1px 12px;"
                    "font-size:8pt;}}"
                    f"QPushButton:hover{{background:{FIG_BG};}}"
                )
            btn.clicked.connect(getattr(self, slot))
            tbl.addWidget(btn)

        root.addWidget(tb)

        # ── Scroll canvas ─────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:{FIG_BG};}}"
            "QScrollBar:vertical{background:#E4EAF4;width:7px;border-radius:3px;}"
            "QScrollBar::handle:vertical{background:#B0BEC5;border-radius:3px;}"
            "QScrollBar:horizontal{background:#E4EAF4;height:7px;border-radius:3px;}"
            "QScrollBar::handle:horizontal{background:#B0BEC5;border-radius:3px;}"
        )
        wrap = QWidget(); wrap.setStyleSheet(f"background:{FIG_BG};")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(4, 4, 4, 4)
        wl.setSpacing(0)

        self._fig    = Figure(facecolor=FIG_BG)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setStyleSheet("background:transparent;")
        wl.addWidget(self._canvas)

        scroll.setWidget(wrap)
        root.addWidget(scroll, 1)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QLabel("  Loading…")
        self._status.setFixedHeight(18)
        self._status.setStyleSheet(
            f"background:{BG_CARD};border-top:1px solid {BORDER};"
            f"color:{TEXT_SECONDARY};font-size:7pt;padding:0 10px;"
        )
        root.addWidget(self._status)

    # ── refresh ───────────────────────────────────────────────────────────────
    def refresh(self):
        tasks = _load_tasks(self.project_id)
        n     = len(tasks)

        # Compact figure sizing
        fig_h_in = max(3.5, TOP_PAD + HDR_H + n * ROW_H + 0.3)
        if tasks:
            span_d = (max(t["end_date"]   for t in tasks)
                    - min(t["start_date"] for t in tasks)).days + 20
        else:
            span_d = 90
        px_per_day = 10
        fig_w_in = max(13.0, (TABLE_W * 78 + span_d * px_per_day) / _DPI)

        self._fig.set_size_inches(fig_w_in, fig_h_in)
        self._canvas.setMinimumHeight(int(fig_h_in * _DPI))
        self._canvas.setMinimumWidth(int(fig_w_in  * _DPI))

        GanttRenderer(tasks).render(self._fig)
        self._canvas.draw_idle()

        done    = sum(1 for t in tasks if t["pct"] >= 100)
        inprog  = sum(1 for t in tasks if 0 < t["pct"] < 100)
        delayed = sum(1 for t in tasks
                      if t["pct"] < 100 and t["end_date"] < date.today())
        self._status.setText(
            f"  {n} tasks  ·  {done} done  ·  {inprog} in progress  ·  "
            f"{delayed} delayed  ·  {date.today().strftime('%d %b %Y')}"
        )

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Gantt", "gantt_chart.png", "PNG (*.png)"
        )
        if path:
            self._fig.savefig(path, dpi=160, bbox_inches="tight",
                              facecolor=FIG_BG, edgecolor="none")
            self._status.setText(f"  ✅ Exported → {path}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(100, self.refresh)


# ── standalone demo ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = QMainWindow()
    win.setWindowTitle("Gantt — Compact Demo")
    win.resize(1400, 600)
    win.setCentralWidget(GanttPlanningView(project_id=None))
    win.show()
    sys.exit(app.exec())
