"""
Project Detail View - Phases with actions, industrialisation planning, multi-budget,
gate dates, annual volumes, nbr_ref.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QScrollArea, QFrame, QGridLayout, QHeaderView,
    QMessageBox, QDateEdit, QLineEdit, QComboBox, QDoubleSpinBox,
    QCheckBox, QSizePolicy, QSpinBox, QFormLayout, QGroupBox, QDialog,
    QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QFont, QColor

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from app.ui.rar_tab import RaRTab
from app.ui.transport_tab import TransportTab
from app.ui.prpo_tab import PRPOTab
from app.utils.theme import *
from app.utils.widgets import (make_label, CardFrame, SectionHeader,
                                StatusBadge, StyledProgressBar, HDivider, KpiCard)
from app.models.project_model import (
    get_project, get_all_budgets, upsert_budget,
    get_gate_dates, upsert_gate_date,
    get_phase_actions, upsert_phase_action, update_action_status, delete_phase_action,
    get_risks, upsert_risk, delete_risk,
    get_notes, add_note,
    get_volumes, upsert_volume, sync_volumes_for_project,
    get_industrialisation_actions, insert_default_industrialisation_actions,
    add_industrialisation_action, update_industrialisation_action,
    delete_industrialisation_action, reorder_industrialisation_actions,
    display_to_iso, iso_to_display, compute_end_date,
    PHASES, BUDGET_TYPES
)


class ProjectDetailView(QScrollArea):
    back_requested = Signal()
    edit_requested = Signal(str)

    def __init__(self, project_id: str, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QScrollArea{border:none;background:transparent;}
            QScrollBar:vertical{background:#F0F4F8;width:7px;border-radius:3px;}
            QScrollBar::handle:vertical{background:#C5D0DC;border-radius:3px;min-height:30px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}
        """)
        self._inner = QWidget()
        self._inner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(16, 12, 16, 16)
        self._lay.setSpacing(10)
        self.setWidget(self._inner)
        self._build()

    def _build(self):
        project = get_project(self.project_id)
        if not project:
            self._lay.addWidget(make_label("Project not found.", FONT_SIZE_LG, color="#E53935"))
            return

        # Top bar
        top = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setStyleSheet(BUTTON_SECONDARY_QSS)
        back_btn.clicked.connect(self.back_requested)
        top.addWidget(back_btn)
        top.addStretch()
        edit_btn = QPushButton("✏ Edit Project")
        edit_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.project_id))
        top.addWidget(edit_btn)
        self._lay.addLayout(top)

        # Hero card
        self._lay.addWidget(self._build_hero(project))

        # Seed industrialisation planning defaults if project is new
        insert_default_industrialisation_actions(self.project_id)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet(APP_QSS)
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tabs.addTab(self._build_phases_tab(project), "📋 Phases & Actions")
        tabs.addTab(self._build_industrialisation_tab(), "🏭 Industrialisation Planning")
        tabs.addTab(RaRTab(self.project_id, project), "🏁 R@R")
        tabs.addTab(PRPOTab(self.project_id), "🛒 PR/PO")
        tabs.addTab(self._build_budget_tab(), "💰 Budget")
        tabs.addTab(self._build_gates_tab(), "🚪 Gate Dates")
        tabs.addTab(TransportTab(self.project_id), "🚚 Transport")
        tabs.addTab(self._build_volumes_tab(project), "📈 Annual Volumes")
        tabs.addTab(self._build_risks_tab(), "⚠ Risks")
        tabs.addTab(self._build_notes_tab(), "📝 Notes")
        self._lay.addWidget(tabs, 1)  # stretch=1 so tabs fill remaining height

    # ── Hero ──────────────────────────────────────────────────────────────────
    def _build_hero(self, p):
        card = CardFrame()
        lay = QGridLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        left = QVBoxLayout()
        id_row = QHBoxLayout()
        pid_badge = QLabel(p.get("project_id",""))
        pid_badge.setStyleSheet(f"background:{SIDEBAR_BG};color:#90CAF9;border-radius:4px;"
                                 f"padding:2px 10px;font-size:9pt;font-family:monospace;")
        phase = p.get("phase","")
        ph_badge = QLabel(phase)
        ph_badge.setStyleSheet(f"background:{PHASE_COLORS.get(phase,PRIMARY)}22;"
                                f"color:{PHASE_COLORS.get(phase,PRIMARY)};border-radius:4px;"
                                f"padding:2px 10px;font-size:9pt;font-weight:bold;font-family:{FONT_FAMILY};")
        id_row.addWidget(pid_badge); id_row.addWidget(ph_badge); id_row.addStretch()
        left.addLayout(id_row)
        name = make_label(p.get("name",""), FONT_SIZE_XL, bold=True)
        name.setWordWrap(True); left.addWidget(name)
        if p.get("description"):
            d = make_label(p["description"], FONT_SIZE_SM, color=TEXT_SECONDARY)
            d.setWordWrap(True); left.addWidget(d)
        prog = p.get("progress", 0)
        pb = StyledProgressBar(prog, self._prog_color(prog))
        pr = QHBoxLayout()
        pr.addWidget(make_label("Progress:", FONT_SIZE_SM, color=TEXT_SECONDARY))
        pr.addWidget(pb)
        left.addLayout(pr)
        lay.addLayout(left, 0, 0)

        # Meta grid — 3 columns so all fields are visible without cramping
        meta = QGridLayout(); meta.setHorizontalSpacing(18); meta.setVerticalSpacing(8)
        fields = [
            ("Manager",    p.get("manager","—")),
            ("Status",     p.get("status","—")),
            ("Priority",   p.get("priority","—")),
            ("Client",     p.get("client","—")),
            ("Dept.",      p.get("department","—")),
            ("Nbr of Ref", str(p.get("nbr_ref",1))),
            ("Start Date", p.get("start_date","—")),
            ("End Date",   p.get("end_date","—")),
            ("Lifetime",   f"{p.get('lifetime_years',5)} yr(s)"),
        ]
        for i, (lbl, val) in enumerate(fields):
            r, cc = divmod(i, 3)
            col = QVBoxLayout(); col.setSpacing(1)
            col.addWidget(make_label(lbl, FONT_SIZE_SM-1, color=TEXT_SECONDARY))
            if lbl == "Status":
                col.addWidget(StatusBadge(val))
            elif lbl == "Priority":
                col.addWidget(make_label(val, FONT_SIZE_SM, bold=True,
                                         color=PRIORITY_COLORS.get(val, TEXT_PRIMARY)))
            else:
                col.addWidget(make_label(val, FONT_SIZE_SM, bold=True))
            meta.addLayout(col, r, cc)
        lay.addLayout(meta, 0, 1)
        lay.setColumnStretch(0, 3); lay.setColumnStretch(1, 2)
        return card

    # ── Phases & Actions Tab ──────────────────────────────────────────────────
    def _build_phases_tab(self, project):
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        outer.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)
        outer.setWidget(container)

        current_phase = project.get("phase", "")
        for phase in PHASES:
            lay.addWidget(self._phase_section(phase, current_phase))
        return outer

    def _phase_section(self, phase, current_phase=""):
        is_current = (phase == current_phase)
        phase_color = PHASE_COLORS.get(phase, PRIMARY)

        card = CardFrame()
        # Highlight active phase with a left-border accent
        if is_current:
            card.setStyleSheet(f"""
                QFrame {{
                    background: {BG_CARD};
                    border: 1px solid {phase_color};
                    border-left: 4px solid {phase_color};
                    border-radius: {RADIUS}px;
                }}
            """)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        # Phase header
        hdr = QHBoxLayout()
        phase_lbl = make_label(phase, FONT_SIZE_MD, bold=True, color=phase_color)
        hdr.addWidget(phase_lbl)

        # "Current Phase" badge
        if is_current:
            cur_badge = QLabel("  ▶ Current Phase  ")
            cur_badge.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM - 1, QFont.Bold))
            cur_badge.setStyleSheet(
                f"background:{phase_color}22; color:{phase_color};"
                f"border:1px solid {phase_color}66;"
                f"border-radius:8px; padding:2px 6px;"
            )
            hdr.addWidget(cur_badge)

        hdr.addStretch()

        # Fetch actions once (used for both badge and table)
        actions = get_phase_actions(self.project_id, phase)
        open_count = sum(1 for a in actions if a.get("status") == "Open")

        # Open-action count badge
        if open_count > 0:
            badge_color = "#E53935" if open_count >= 5 else "#FB8C00"
            open_badge = QLabel(f"  {open_count} open  ")
            open_badge.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM - 1, QFont.Bold))
            open_badge.setStyleSheet(
                f"background:{badge_color}22; color:{badge_color};"
                f"border:1px solid {badge_color}66;"
                f"border-radius:8px; padding:2px 6px;"
            )
            hdr.addWidget(open_badge)

        add_btn = QPushButton("+ Action")
        add_btn.setStyleSheet(BUTTON_SECONDARY_QSS + "QPushButton{padding:4px 12px;font-size:8pt;}")
        add_btn.clicked.connect(lambda checked, ph=phase: self._add_action_inline(ph))
        hdr.addWidget(add_btn)
        lay.addLayout(hdr)
        lay.addWidget(HDivider())

        # Table
        cols = ["Action", "Lead Time (W)", "Start Date", "End Date", "Status", ""]
        tbl = QTableWidget(len(actions), len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        tbl.setStyleSheet(TABLE_QSS)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setShowGrid(False)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for ci in range(1, len(cols)-1):
            tbl.horizontalHeader().setSectionResizeMode(ci, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(len(cols)-1, QHeaderView.Fixed)
        tbl.setColumnWidth(len(cols)-1, 120)

        for ri, act in enumerate(actions):
            tbl.setRowHeight(ri, 40)
            tbl.setItem(ri, 0, QTableWidgetItem(act.get("action_name","")))
            tbl.setItem(ri, 1, QTableWidgetItem(str(act.get("lead_time_weeks","") or "")))
            tbl.setItem(ri, 2, QTableWidgetItem(act.get("start_date","") or ""))
            tbl.setItem(ri, 3, QTableWidgetItem(act.get("end_date","") or ""))

            # Status toggle
            status = act.get("status","Open")
            status_widget = self._status_toggle(act["id"], status)
            tbl.setCellWidget(ri, 4, status_widget)

            # Action buttons
            btn_w = self._action_btns(act)
            tbl.setCellWidget(ri, 5, btn_w)

        tbl.setFixedHeight(max(50, 44 + len(actions) * 40))
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay.addWidget(tbl)
        return card

    def _status_toggle(self, action_id, current_status):
        w = QWidget()
        h = QHBoxLayout(w); h.setContentsMargins(4, 2, 4, 2); h.setSpacing(4)
        done_btn = QPushButton("✓ Done")
        open_btn = QPushButton("○ Open")
        done_btn.setFixedHeight(26)
        open_btn.setFixedHeight(26)
        if current_status == "Done":
            done_btn.setStyleSheet(f"QPushButton{{background:#43A047;color:white;border:none;"
                                    f"border-radius:5px;padding:2px 8px;font-size:8pt;font-weight:bold;}}")
            open_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{TEXT_SECONDARY};"
                                    f"border:1px solid {BORDER};border-radius:5px;padding:2px 8px;font-size:8pt;}}")
        else:
            open_btn.setStyleSheet(f"QPushButton{{background:#FB8C00;color:white;border:none;"
                                    f"border-radius:5px;padding:2px 8px;font-size:8pt;font-weight:bold;}}")
            done_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{TEXT_SECONDARY};"
                                    f"border:1px solid {BORDER};border-radius:5px;padding:2px 8px;font-size:8pt;}}")
        done_btn.clicked.connect(lambda: self._set_action_status(action_id, "Done"))
        open_btn.clicked.connect(lambda: self._set_action_status(action_id, "Open"))
        h.addWidget(done_btn); h.addWidget(open_btn)
        return w

    def _set_action_status(self, action_id, status):
        update_action_status(action_id, status)
        self._refresh()

    def _action_btns(self, act):
        w = QWidget()
        h = QHBoxLayout(w); h.setContentsMargins(2, 2, 2, 2); h.setSpacing(4)
        edit_btn = QPushButton("✏")
        edit_btn.setFixedSize(28, 28)
        edit_btn.setStyleSheet(f"QPushButton{{background:#E3F2FD;border:none;border-radius:6px;"
                                f"color:{PRIMARY};font-size:11pt;}} QPushButton:hover{{background:#BBDEFB;}}")
        edit_btn.clicked.connect(lambda: self._edit_action_dialog(act))
        del_btn = QPushButton("🗑")
        del_btn.setFixedSize(28, 28)
        del_btn.setStyleSheet(f"QPushButton{{background:#FFEBEE;border:none;border-radius:6px;"
                               f"color:#E53935;font-size:11pt;}} QPushButton:hover{{background:#FFCDD2;}}")
        del_btn.clicked.connect(lambda: self._delete_action(act["id"]))
        h.addWidget(edit_btn); h.addWidget(del_btn)
        return w

    def _add_action_inline(self, phase):
        from app.ui.forms import PhaseActionForm
        dlg = PhaseActionForm(self.project_id, phase, self)
        if dlg.exec(): self._refresh()

    def _edit_action_dialog(self, act):
        from app.ui.forms import PhaseActionForm
        dlg = PhaseActionForm(self.project_id, act["phase"], self, data=act)
        if dlg.exec(): self._refresh()

    def _delete_action(self, action_id):
        r = QMessageBox.question(self, "Delete", "Delete this action?",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            delete_phase_action(action_id)
            self._refresh()

    # ── Industrialisation Planning Tab ────────────────────────────────────────
    def _build_industrialisation_tab(self):
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        outer.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)
        outer.setWidget(container)
        self._indus_container_lay = lay
        self._refresh_industrialisation_tab(lay)
        return outer

    def _refresh_industrialisation_tab(self, lay=None):
        """
        Rebuild the industrialisation planning table with drag-and-drop reordering.
        Columns: ⠿ | Department | Action | Start | Lead Time | End (auto) | % | Status | Buttons
        Drag the grip handle (⠿) column to reorder rows; sort_order is persisted to DB.
        """
        if lay is None:
            if not hasattr(self, '_indus_container_lay'):
                return
            lay = self._indus_container_lay
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        # ── Header bar ────────────────────────────────────────────────────────
        header_card = CardFrame()
        hlay = QVBoxLayout(header_card)
        hlay.setContentsMargins(12, 10, 12, 10)
        hlay.setSpacing(8)

        title_row = QHBoxLayout()
        title_lbl = make_label("🏭  Industrialisation Planning",
                                FONT_SIZE_MD + 1, bold=True, color=PRIMARY)
        sub_lbl = make_label(
            "Enter Start Date (DD/MM/YYYY) and Lead Time (weeks). "
            "End Date is computed automatically. "
            "Drag ⠿ to reorder. Changes instantly reflect in the Gantt.",
            FONT_SIZE_SM, color=TEXT_SECONDARY
        )
        sub_lbl.setWordWrap(True)
        add_btn = QPushButton("+ Add Action")
        add_btn.setStyleSheet(BUTTON_PRIMARY_QSS + "QPushButton{padding:6px 18px;font-size:9pt;}")
        add_btn.clicked.connect(self._add_indus_action_dialog)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        title_row.addWidget(add_btn)
        hlay.addLayout(title_row)
        hlay.addWidget(sub_lbl)
        lay.addWidget(header_card)

        # ── Drag-and-drop table ───────────────────────────────────────────────
        actions = get_industrialisation_actions(self.project_id)
        table_card = CardFrame()
        tlay = QVBoxLayout(table_card)
        tlay.setContentsMargins(0, 0, 0, 0)
        tlay.setSpacing(0)

        if not actions:
            empty = make_label(
                "  No actions yet. Click '+ Add Action' to get started.",
                FONT_SIZE_SM, color=TEXT_SECONDARY
            )
            empty.setContentsMargins(18, 20, 18, 20)
            tlay.addWidget(empty)
        else:
            # ── Build drag-and-drop QTableWidget ─────────────────────────────
            from PySide6.QtCore import QMimeData, QPoint
            from PySide6.QtGui import QDrag, QPixmap, QPainter
            from PySide6.QtWidgets import QProgressBar as _QPB, QAbstractItemView

            COLS = ["", "Department", "Action",
                    "Start Date", "Lead Time", "End Date (auto)",
                    "% Done", "Status", ""]

            tbl = QTableWidget(len(actions), len(COLS))
            tbl.setHorizontalHeaderLabels(COLS)
            tbl.setStyleSheet(TABLE_QSS + """
                QTableWidget::item:selected { background: #E3F2FD; color: #1A2035; }
                QTableWidget { gridline-color: transparent; }
            """)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            tbl.verticalHeader().setVisible(False)
            tbl.setShowGrid(False)
            tbl.setSelectionBehavior(QTableWidget.SelectRows)
            tbl.setAlternatingRowColors(True)

            # Enable internal drag-and-drop via built-in row move
            tbl.setDragEnabled(True)
            tbl.setAcceptDrops(True)
            tbl.setDropIndicatorShown(True)
            tbl.setDragDropMode(QAbstractItemView.InternalMove)
            tbl.setDragDropOverwriteMode(False)
            tbl.setDefaultDropAction(Qt.MoveAction)

            hh = tbl.horizontalHeader()
            hh.setSectionResizeMode(0, QHeaderView.Fixed)             # Grip
            tbl.setColumnWidth(0, 28)
            hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Department
            hh.setSectionResizeMode(2, QHeaderView.Stretch)           # Action
            hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Start Date
            hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Lead Time
            hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # End Date
            hh.setSectionResizeMode(6, QHeaderView.Fixed)             # % Done
            tbl.setColumnWidth(6, 110)
            hh.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Status
            hh.setSectionResizeMode(8, QHeaderView.Fixed)             # Buttons
            tbl.setColumnWidth(8, 90)

            SC = {
                "Open":        ("#E3F2FD", "#1565C0"),
                "In Progress": ("#FFF3E0", "#E65100"),
                "Done":        ("#E8F5E9", "#2E7D32"),
                "Blocked":     ("#FCE4EC", "#C62828"),
            }

            # Store action IDs in row order so we can persist after drop
            self._indus_action_ids = [act["id"] for act in actions]
            self._indus_table_ref  = tbl

            for ri, act in enumerate(actions):
                tbl.setRowHeight(ri, 46)

                # Col 0 – Drag grip
                grip = QTableWidgetItem("⠿")
                grip.setTextAlignment(Qt.AlignCenter)
                grip.setForeground(QColor("#B0BEC5"))
                grip.setFont(QFont(FONT_FAMILY, 14))
                grip.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable
                              | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
                grip.setToolTip("Drag to reorder")
                tbl.setItem(ri, 0, grip)

                # Col 1 – Department
                di = QTableWidgetItem(act.get("department", ""))
                di.setForeground(QColor(PRIMARY_DARK))
                di.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
                tbl.setItem(ri, 1, di)

                # Col 2 – Action name
                ai = QTableWidgetItem(act.get("action", ""))
                ai.setData(Qt.UserRole, act["id"])   # store id for reorder
                tbl.setItem(ri, 2, ai)

                # Col 3 – Start Date
                sd_disp = act.get("start_date_disp") or iso_to_display(act.get("start_date", ""))
                sd_item = QTableWidgetItem(sd_disp)
                sd_item.setTextAlignment(Qt.AlignCenter)
                sd_item.setForeground(QColor(PRIMARY))
                sd_item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
                tbl.setItem(ri, 3, sd_item)

                # Col 4 – Lead time
                lt_val = float(act.get("lead_time_weeks", 2))
                lt_item = QTableWidgetItem(f"{lt_val:.1f} w")
                lt_item.setTextAlignment(Qt.AlignCenter)
                lt_item.setForeground(QColor(TEXT_SECONDARY))
                tbl.setItem(ri, 4, lt_item)

                # Col 5 – End Date (auto-computed)
                ed_disp = act.get("end_date_disp") or iso_to_display(act.get("end_date", ""))
                ed_item = QTableWidgetItem(f"📅 {ed_disp}")
                ed_item.setTextAlignment(Qt.AlignCenter)
                ed_item.setForeground(QColor(TEXT_SECONDARY))
                tbl.setItem(ri, 5, ed_item)

                # Col 6 – % complete
                pct_val = float(act.get("pct_complete", 0))
                pct_color = ("#43A047" if pct_val >= 100 else
                             "#1E88E5" if pct_val > 0 else "#B0BEC5")
                pct_w = QWidget()
                pct_l = QHBoxLayout(pct_w)
                pct_l.setContentsMargins(6, 10, 6, 10)
                pct_l.setSpacing(5)
                pb = _QPB()
                pb.setRange(0, 100)
                pb.setValue(int(pct_val))
                pb.setTextVisible(False)
                pb.setFixedHeight(7)
                pb.setStyleSheet(
                    f"QProgressBar{{border:none;border-radius:3px;background:#ECEFF1;}}"
                    f"QProgressBar::chunk{{background:{pct_color};border-radius:3px;}}"
                )
                pct_num = QLabel(f"{pct_val:.0f}%")
                pct_num.setFixedWidth(34)
                pct_num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                pct_num.setStyleSheet(
                    f"color:{pct_color};font-size:8pt;font-weight:bold;background:transparent;"
                )
                pct_l.addWidget(pb, 1)
                pct_l.addWidget(pct_num)
                tbl.setCellWidget(ri, 6, pct_w)

                # Col 7 – Status badge
                status = act.get("status", "Open")
                bg, fg = SC.get(status, ("#F5F5F5", "#424242"))
                st_lbl = QLabel(status)
                st_lbl.setAlignment(Qt.AlignCenter)
                st_lbl.setStyleSheet(
                    f"background:{bg};color:{fg};border-radius:10px;"
                    f"padding:2px 10px;font-size:8pt;font-weight:bold;"
                    f"font-family:{FONT_FAMILY};"
                )
                st_w = QWidget()
                st_l = QHBoxLayout(st_w)
                st_l.setContentsMargins(6, 2, 6, 2)
                st_l.addWidget(st_lbl)
                tbl.setCellWidget(ri, 7, st_w)

                # Col 8 – Edit / Delete
                btn_w = QWidget()
                btn_l = QHBoxLayout(btn_w)
                btn_l.setContentsMargins(4, 2, 4, 2)
                btn_l.setSpacing(4)
                edit_btn = QPushButton("✏")
                edit_btn.setFixedSize(30, 30)
                edit_btn.setStyleSheet(
                    f"QPushButton{{background:#E3F2FD;border:none;border-radius:6px;"
                    f"color:{PRIMARY};font-size:12pt;}}"
                    f"QPushButton:hover{{background:#BBDEFB;}}"
                )
                edit_btn.clicked.connect(
                    lambda _checked, a=act: self._edit_indus_action_dialog(a)
                )
                del_btn = QPushButton("🗑")
                del_btn.setFixedSize(30, 30)
                del_btn.setStyleSheet(
                    "QPushButton{background:#FFEBEE;border:none;border-radius:6px;"
                    "color:#E53935;font-size:11pt;}"
                    "QPushButton:hover{background:#FFCDD2;}"
                )
                del_btn.clicked.connect(
                    lambda _checked, aid=act["id"]: self._delete_indus_action(aid)
                )
                btn_l.addWidget(edit_btn)
                btn_l.addWidget(del_btn)
                tbl.setCellWidget(ri, 8, btn_w)

            # ── Connect drop-model signal to persist new order ─────────────────
            tbl.model().rowsMoved.connect(self._on_indus_rows_moved)

            tbl.setFixedHeight(min(54 + len(actions) * 46, 580))
            tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            tlay.addWidget(tbl)

        lay.addWidget(table_card)
        lay.addStretch()

    def _on_indus_rows_moved(self, parent, src_start, src_end, dest_parent, dest_row):
        """
        Called by Qt after an internal drag-and-drop row move completes.
        Reads the new row order from the table, extracts action IDs from
        column 2 (UserRole), and persists the new sort_order to the DB.
        """
        tbl = getattr(self, '_indus_table_ref', None)
        if tbl is None:
            return
        new_order = []
        for row in range(tbl.rowCount()):
            item = tbl.item(row, 2)   # Action name column stores the ID
            if item is not None:
                action_id = item.data(Qt.UserRole)
                if action_id is not None:
                    new_order.append(action_id)
        if new_order:
            reorder_industrialisation_actions(self.project_id, new_order)
            self._sync_gantt_if_open()

    def _add_indus_action_dialog(self):
        dlg = _IndustrialisationActionDialog(self)
        if dlg.exec():
            dept, action, status, sd_iso, lt, pct = dlg.get_values()
            add_industrialisation_action(
                self.project_id, dept, action, status,
                start_date=sd_iso, lead_time=lt, pct_complete=pct
            )
            self._refresh_industrialisation_tab()
            self._sync_gantt_if_open()

    def _edit_indus_action_dialog(self, act):
        dlg = _IndustrialisationActionDialog(self, data=act)
        if dlg.exec():
            dept, action, status, sd_iso, lt, pct = dlg.get_values()
            update_industrialisation_action(
                act["id"], dept, action, status,
                start_date=sd_iso, lead_time=lt, pct_complete=pct
            )
            self._refresh_industrialisation_tab()
            self._sync_gantt_if_open()

    def _delete_indus_action(self, action_id):
        r = QMessageBox.question(self, "Delete", "Delete this industrialisation action?",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            delete_industrialisation_action(action_id)
            self._refresh_industrialisation_tab()
            self._sync_gantt_if_open()

    # ── Gantt Planning Tab ────────────────────────────────────────────────────
    def _build_gantt_tab(self):
        from app.ui.gantt_planning_view import GanttPlanningView
        self._gantt_widget = GanttPlanningView(project_id=self.project_id)
        return self._gantt_widget

    def _sync_gantt_if_open(self):
        """Refresh the Gantt if it has been built."""
        if getattr(self, '_gantt_widget', None) is not None:
            self._gantt_widget.refresh()

    def _scrollable(self, widget: QWidget) -> QScrollArea:
        """Wrap any tab widget in a scroll area so content is never clipped."""
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sa.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sa.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{background:#F0F4F8;width:7px;border-radius:3px;}"
            "QScrollBar::handle:vertical{background:#C5D0DC;border-radius:3px;min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}"
            "QScrollBar:horizontal{background:#F0F4F8;height:7px;border-radius:3px;}"
            "QScrollBar::handle:horizontal{background:#C5D0DC;border-radius:3px;min-width:30px;}"
            "QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0px;}"
        )
        sa.setWidget(widget)
        return sa

    # ── Budget Tab ────────────────────────────────────────────────────────────
    def _build_budget_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(16)

        budgets = {b["budget_type"]: b for b in get_all_budgets(self.project_id)}

        total_planned = sum(b["planned_budget"] for b in budgets.values())
        total_actual  = sum(b["actual_cost"] for b in budgets.values())
        total_rem     = total_planned - total_actual
        pct           = (total_actual / total_planned * 100) if total_planned > 0 else 0

        # Summary KPIs
        krow = QHBoxLayout(); krow.setSpacing(12)
        for card_args in [
            ("Total Planned",  self._fmt(total_planned), "€",  PRIMARY),
            ("Total Consumed", self._fmt(total_actual),  "💸", STATUS_COLORS["At Risk"]),
            ("Remaining",      self._fmt(total_rem),     "✅", STATUS_COLORS["Completed"]),
            ("Consumed %",     f"{pct:.1f}%",            "📊", ACCENT),
        ]:
            c = KpiCard(*card_args)
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            krow.addWidget(c, 1)
        lay.addLayout(krow)

        # Per-type cards
        for btype in BUDGET_TYPES:
            b = budgets.get(btype, {})
            section = self._budget_type_card(btype, b)
            lay.addWidget(section)

        # Combined chart
        lay.addWidget(self._budget_chart(budgets))
        lay.addStretch()
        return self._scrollable(w)

    def _budget_type_card(self, btype, b):
        card = CardFrame()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        # Title row
        hdr = QHBoxLayout()
        color = {"CPT Cash": PRIMARY, "CAPEX": "#8E24AA", "ED&T Amortization": "#00ACC1"}.get(btype, PRIMARY)
        hdr.addWidget(make_label(btype, FONT_SIZE_MD, bold=True, color=color))
        hdr.addStretch()
        edit_btn = QPushButton("Edit")
        edit_btn.setStyleSheet(BUTTON_SECONDARY_QSS + "QPushButton{padding:4px 14px;font-size:8pt;}")
        edit_btn.clicked.connect(lambda checked, bt=btype: self._edit_budget(bt))
        hdr.addWidget(edit_btn)
        lay.addLayout(hdr)

        # Values row
        vrow = QHBoxLayout(); vrow.setSpacing(20)
        planned = b.get("planned_budget", 0) or 0
        actual  = b.get("actual_cost", 0) or 0
        remaining = planned - actual

        for label, value, color2 in [
            ("Planned",   planned,   TEXT_PRIMARY),
            ("Consumed",  actual,    STATUS_COLORS["At Risk"]),
            ("Remaining", remaining, STATUS_COLORS["Completed"]),
        ]:
            col = QVBoxLayout(); col.setSpacing(2)
            col.addWidget(make_label(label, FONT_SIZE_SM-1, color=TEXT_SECONDARY))
            col.addWidget(make_label(self._fmt(value), FONT_SIZE_LG, bold=True, color=color2))
            vrow.addLayout(col)
        vrow.addStretch()
        lay.addLayout(vrow)

        # Progress bar
        if planned > 0:
            pct = min(actual / planned * 100, 100)
            pb = StyledProgressBar(pct, color)
            pb_row = QHBoxLayout()
            pb_row.addWidget(make_label("Consumption:", FONT_SIZE_SM-1, color=TEXT_SECONDARY))
            pb_row.addWidget(pb)
            lay.addLayout(pb_row)
        return card

    def _budget_chart(self, budgets):
        card = CardFrame()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.addWidget(make_label("Budget by Type – Planned vs Consumed", FONT_SIZE_MD, bold=True))

        types  = list(BUDGET_TYPES)
        planned_vals = [budgets.get(t, {}).get("planned_budget", 0) or 0 for t in types]
        actual_vals  = [budgets.get(t, {}).get("actual_cost", 0) or 0 for t in types]

        x = range(len(types))
        fig, ax = plt.subplots(figsize=(7, 2.8))
        fig.patch.set_facecolor("none"); ax.set_facecolor("none")
        w = 0.35
        bars1 = ax.bar([i - w/2 for i in x], planned_vals, w, label="Planned", color=PRIMARY, edgecolor="none")
        bars2 = ax.bar([i + w/2 for i in x], actual_vals,  w, label="Consumed", color="#FB8C00", edgecolor="none")
        max_val = max(planned_vals + actual_vals) if any(planned_vals + actual_vals) else 1
        for bar in list(bars1) + list(bars2):
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width()/2, h + max_val*0.01,
                        self._fmt(h), ha="center", va="bottom", fontsize=7, color=TEXT_PRIMARY)
        ax.set_xticks(list(x))
        ax.set_xticklabels(types, fontsize=8)
        ax.set_ylim(0, max_val * 1.3)
        ax.legend(fontsize=8, frameon=False)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        ax.tick_params(axis="y", labelsize=8)

        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background:transparent;")
        canvas.setMaximumHeight(220)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        lay.addWidget(canvas)
        plt.close(fig)
        return card

    def _edit_budget(self, budget_type):
        from app.ui.forms import BudgetForm
        budgets = {b["budget_type"]: b for b in get_all_budgets(self.project_id)}
        dlg = BudgetForm(self.project_id, budget_type, budgets.get(budget_type, {}), self)
        if dlg.exec(): self._refresh()

    # ── Gate Dates Tab ────────────────────────────────────────────────────────
    def _build_gates_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(14)
        lay.addWidget(make_label("Gate Exit Dates", FONT_SIZE_LG, bold=True))
        lay.addWidget(make_label("Set the planned date for each phase gate review.",
                                  FONT_SIZE_SM, color=TEXT_SECONDARY))

        gate_dates = get_gate_dates(self.project_id)

        for phase in PHASES:
            card = CardFrame()
            cl = QHBoxLayout(card)
            cl.setContentsMargins(18, 12, 18, 12)
            cl.setSpacing(16)

            color = PHASE_COLORS.get(phase, PRIMARY)
            cl.addWidget(make_label(phase, FONT_SIZE_MD, bold=True, color=color))

            gate = gate_dates.get(phase, {})
            date_str = gate.get("gate_date", "")
            date_lbl = make_label(date_str or "Not set", FONT_SIZE_MD,
                                   bold=True, color=TEXT_PRIMARY if date_str else TEXT_SECONDARY)
            cl.addWidget(date_lbl)
            cl.addStretch()

            status = gate.get("status", "Pending")
            cl.addWidget(StatusBadge(status))

            edit_btn = QPushButton("Set Date")
            edit_btn.setStyleSheet(BUTTON_PRIMARY_QSS + "QPushButton{padding:5px 14px;font-size:8pt;}")
            edit_btn.clicked.connect(lambda checked, ph=phase: self._set_gate_date(ph))
            cl.addWidget(edit_btn)
            lay.addWidget(card)

        lay.addStretch()
        return self._scrollable(w)

    def _set_gate_date(self, phase):
        from app.ui.forms import GateDateForm
        gate_dates = get_gate_dates(self.project_id)
        dlg = GateDateForm(self.project_id, phase, gate_dates.get(phase, {}), self)
        if dlg.exec(): self._refresh()

    # ── Annual Volumes Tab ────────────────────────────────────────────────────
    def _build_volumes_tab(self, project):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(14)

        nbr_ref  = max(int(project.get("nbr_ref", 1) or 1), 1)
        lifetime = project.get("lifetime_years", 5)

        # Parse ref names
        raw_names = (project.get("ref_names") or "").split("|")
        ref_names = []
        for i in range(nbr_ref):
            name = raw_names[i].strip() if i < len(raw_names) and raw_names[i].strip() else f"Ref {i+1}"
            ref_names.append(name)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Annual Volumes", FONT_SIZE_LG, bold=True))
        hdr.addStretch()
        hdr.addWidget(make_label(
            f"Lifetime: {lifetime} year(s)  |  Refs: {nbr_ref}",
            FONT_SIZE_SM, color=TEXT_SECONDARY))
        lay.addLayout(hdr)

        sync_volumes_for_project(self.project_id, lifetime)
        volumes = get_volumes(self.project_id)

        vol_card = CardFrame()
        vc = QVBoxLayout(vol_card)
        vc.setContentsMargins(12, 10, 12, 10)
        vc.setSpacing(8)
        vc.addWidget(make_label(
            "Volume per Year  (enter volume for each reference)",
            FONT_SIZE_MD, bold=True))

        self._vol_spinboxes = {}   # (ref_name, year_label) -> QDoubleSpinBox

        vol_by_year = {v["year_label"]: float(v.get("volume", 0) or 0) for v in volumes}
        year_labels = [v["year_label"] for v in volumes]

        # QTableWidget handles many years cleanly with horizontal scroll
        vol_tbl = QTableWidget(nbr_ref, len(year_labels))
        vol_tbl.setStyleSheet(TABLE_QSS)
        vol_tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        vol_tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        vol_tbl.setShowGrid(True)
        vol_tbl.setAlternatingRowColors(True)
        vol_tbl.verticalHeader().setVisible(True)
        vol_tbl.verticalHeader().setDefaultSectionSize(40)
        vol_tbl.setHorizontalHeaderLabels(year_labels)
        vol_tbl.setVerticalHeaderLabels(ref_names)
        vol_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for ri, ref_name in enumerate(ref_names):
            for ci, yr in enumerate(year_labels):
                total_vol = vol_by_year.get(yr, 0)
                ref_vol   = total_vol / nbr_ref if nbr_ref > 0 else total_vol
                sb = QDoubleSpinBox()
                sb.setRange(0, 99_999_999)
                sb.setGroupSeparatorShown(True)
                sb.setSuffix(" u")
                sb.setValue(ref_vol)
                sb.setStyleSheet("QDoubleSpinBox{border:none;background:transparent;padding:2px 4px;}")
                sb.setAlignment(Qt.AlignCenter)
                sb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self._vol_spinboxes[(ref_name, yr)] = sb
                vol_tbl.setCellWidget(ri, ci, sb)

        vol_tbl.setFixedHeight(min(max(42 * nbr_ref + 32, 80), 260))
        vc.addWidget(vol_tbl)

        vc.addSpacing(8)
        save_btn = QPushButton("💾 Save All Volumes")
        save_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        save_btn.clicked.connect(self._save_volumes)
        vc.addWidget(save_btn, alignment=Qt.AlignLeft)
        lay.addWidget(vol_card)

        if volumes:
            lay.addWidget(self._volumes_chart(volumes))
        lay.addStretch()
        return self._scrollable(w)

    def _save_volumes(self):
        year_totals = {}
        for (ref_name, yr), sb in self._vol_spinboxes.items():
            year_totals[yr] = year_totals.get(yr, 0) + sb.value()
        for yr, total in year_totals.items():
            upsert_volume(self.project_id, yr, total)
        QMessageBox.information(self, "Saved", "Annual volumes saved successfully.")
        self._refresh()

    def _volumes_chart(self, volumes):
        card = CardFrame()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.addWidget(make_label("Volume by Year", FONT_SIZE_MD, bold=True))
        labels = [v["year_label"] for v in volumes]
        vals   = [v.get("volume", 0) or 0 for v in volumes]
        fig, ax = plt.subplots(figsize=(7, 2.6))
        fig.patch.set_facecolor("none"); ax.set_facecolor("none")
        bars = ax.bar(labels, vals, color=PRIMARY, width=0.5, edgecolor="none")
        max_val = max(vals) if any(v > 0 for v in vals) else 1
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width()/2, h + max_val*0.02,
                        f"{h:,.0f}", ha="center", va="bottom", fontsize=8, color=TEXT_PRIMARY)
        ax.set_ylim(0, max_val * 1.25)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        ax.tick_params(axis="both", labelsize=8)
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background:transparent;")
        canvas.setMaximumHeight(200)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        cl.addWidget(canvas)
        plt.close(fig)
        return card

    # ── Risks Tab ─────────────────────────────────────────────────────────────
    def _build_risks_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10); lay.setSpacing(10)
        hdr = SectionHeader("Risks & Issues", "＋ Add Risk")
        if hdr.btn: hdr.btn.clicked.connect(self._add_risk)
        lay.addWidget(hdr)
        risks = get_risks(self.project_id)
        cols = ["Description", "Impact", "Probability", "Mitigation", "Owner", "Status", ""]
        tbl = self._generic_table(cols, risks,
                                   ["description","impact","probability","mitigation","owner","status"],
                                   delete_fn=delete_risk)
        lay.addWidget(tbl)
        lay.addStretch()
        return self._scrollable(w)

    def _add_risk(self):
        from app.ui.forms import RiskForm
        dlg = RiskForm(self.project_id, self)
        if dlg.exec(): self._refresh()

    # ── Notes Tab ─────────────────────────────────────────────────────────────
    def _build_notes_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10); lay.setSpacing(10)
        lay.addWidget(make_label("Notes & Comments", FONT_SIZE_MD, bold=True))
        nr = QHBoxLayout()
        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("Add a note...")
        self.note_input.setStyleSheet(INPUT_QSS); self.note_input.setMaximumHeight(80)
        nr.addWidget(self.note_input, 4)
        sb = QPushButton("Add Note"); sb.setStyleSheet(BUTTON_PRIMARY_QSS)
        sb.clicked.connect(self._save_note); nr.addWidget(sb, 1)
        lay.addLayout(nr)
        lay.addWidget(HDivider())
        for note in get_notes(self.project_id):
            card = CardFrame()
            cl = QVBoxLayout(card); cl.setContentsMargins(14,10,14,10); cl.setSpacing(4)
            mr = QHBoxLayout()
            mr.addWidget(make_label(note.get("author","User"), FONT_SIZE_SM, bold=True, color=PRIMARY))
            mr.addStretch()
            mr.addWidget(make_label(note.get("created_at",""), FONT_SIZE_SM-1, color=TEXT_SECONDARY))
            cl.addLayout(mr)
            ct = make_label(note.get("content",""), FONT_SIZE_SM); ct.setWordWrap(True); cl.addWidget(ct)
            lay.addWidget(card)
        lay.addStretch()
        return self._scrollable(w)

    def _save_note(self):
        text = self.note_input.toPlainText().strip()
        if text:
            add_note(self.project_id, text)
            self.note_input.clear()
            self._refresh()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _generic_table(self, col_labels, rows, fields, delete_fn=None):
        tbl = QTableWidget(len(rows), len(col_labels))
        tbl.setHorizontalHeaderLabels(col_labels)
        tbl.setStyleSheet(TABLE_QSS)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.verticalHeader().setVisible(False); tbl.setShowGrid(False)
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(col_labels)-1):
            tbl.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(len(col_labels)-1, QHeaderView.Fixed)
        tbl.setColumnWidth(len(col_labels)-1, 80)
        for ri, row in enumerate(rows):
            tbl.setRowHeight(ri, 40)
            for ci, field in enumerate(fields):
                val = str(row.get(field,"") or "")
                if field == "status":
                    badge = StatusBadge(val or "Open")
                    cw = QWidget(); ch = QHBoxLayout(cw)
                    ch.setContentsMargins(4,2,4,2); ch.addStretch(); ch.addWidget(badge); ch.addStretch()
                    tbl.setCellWidget(ri, ci, cw)
                elif field == "impact":
                    item = QTableWidgetItem(val)
                    item.setForeground(QColor({"High":"#E53935","Medium":"#FB8C00","Low":"#43A047"}.get(val,TEXT_SECONDARY)))
                    item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
                    tbl.setItem(ri, ci, item)
                else:
                    tbl.setItem(ri, ci, QTableWidgetItem(val))
            if delete_fn:
                rid = row.get("id")
                db = QPushButton("🗑"); db.setFixedSize(32,28)
                db.setStyleSheet(f"QPushButton{{background:#FFEBEE;border:none;border-radius:6px;color:#E53935;font-size:12pt;}} QPushButton:hover{{background:#FFCDD2;}}")
                db.clicked.connect(lambda ch, r2=rid: self._do_delete(delete_fn, r2))
                cw = QWidget(); ch2 = QHBoxLayout(cw)
                ch2.setContentsMargins(4,2,4,2); ch2.addStretch(); ch2.addWidget(db); ch2.addStretch()
                tbl.setCellWidget(ri, len(col_labels)-1, cw)
        return tbl

    def _do_delete(self, fn, row_id):
        if QMessageBox.question(self,"Delete","Delete this record?",
                                QMessageBox.Yes|QMessageBox.No,QMessageBox.No) == QMessageBox.Yes:
            fn(row_id); self._refresh()

    def _refresh(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._build()

    def _prog_color(self, p):
        if p >= 80: return STATUS_COLORS["Completed"]
        if p >= 50: return PRIMARY
        return STATUS_COLORS["At Risk"]

    def _fmt(self, v):
        v = v or 0
        if v >= 1_000_000: return f"€{v/1_000_000:.2f}M"
        if v >= 1_000:     return f"€{v:,.0f}"
        return f"€{v:.0f}"


# ─────────────────────────────────────────────────────────────────────────────
# Dialog for adding / editing Industrialisation Planning actions
# ─────────────────────────────────────────────────────────────────────────────
# Industrialisation Action Dialog
# ─────────────────────────────────────────────────────────────────────────────
class _IndustrialisationActionDialog(QDialog):
    """
    Add / Edit dialog for a single Industrialisation Planning action.

    User inputs:
        - Department (combo)
        - Action name (text)
        - Status (combo)
        - Start Date (DD/MM/YYYY)  ← primary time input
        - Lead Time in weeks       ← primary duration input
        - % Complete (0-100)

    End Date is displayed read-only, auto-computed = Start Date + Lead Time.
    End date is NEVER editable here or anywhere else.
    """
    DEPARTMENTS = [
        "Purchasing", "PM", "Process Engineering", "Global Buyer",
        "DK team", "Quality", "Logistics", "Engineering", "Finance", "Other"
    ]
    STATUSES = ["Open", "In Progress", "Done", "Blocked"]

    def __init__(self, parent=None, data: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Add Action" if data is None else "Edit Action")
        self.setMinimumWidth(500)
        self.setFixedWidth(500)
        self.setStyleSheet(
            f"background:{BG_CARD};color:{TEXT_PRIMARY};font-family:{FONT_FAMILY};"
        )
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        SEC = (
            f"background:#F0F4F8;border-bottom:1px solid {BORDER};"
            f"padding:8px 24px;font-size:8pt;font-weight:bold;"
            f"color:{TEXT_SECONDARY};letter-spacing:1px;"
        )

        # ══ Section 1: Action details ════════════════════════════════════════
        root.addWidget(self._sec_label("  ACTION DETAILS", SEC))

        f1 = QFormLayout()
        f1.setSpacing(12)
        f1.setContentsMargins(24, 16, 24, 16)
        f1.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._dept = QComboBox()
        self._dept.setStyleSheet(INPUT_QSS)
        self._dept.addItems(self.DEPARTMENTS)
        if data:
            i = self._dept.findText(data.get("department", ""))
            if i >= 0: self._dept.setCurrentIndex(i)
        f1.addRow(self._lbl("Department *"), self._dept)

        self._action = QLineEdit()
        self._action.setStyleSheet(INPUT_QSS)
        self._action.setPlaceholderText("Describe the action…")
        if data: self._action.setText(data.get("action", ""))
        f1.addRow(self._lbl("Action *"), self._action)

        self._status = QComboBox()
        self._status.setStyleSheet(INPUT_QSS)
        self._status.addItems(self.STATUSES)
        if data:
            i = self._status.findText(data.get("status", "Open"))
            if i >= 0: self._status.setCurrentIndex(i)
        f1.addRow(self._lbl("Status"), self._status)

        root.addLayout(f1)

        # ══ Section 2: Schedule ══════════════════════════════════════════════
        root.addWidget(self._sec_label("  GANTT SCHEDULE", SEC))

        f2 = QFormLayout()
        f2.setSpacing(12)
        f2.setContentsMargins(24, 16, 24, 20)
        f2.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Start Date — user enters DD/MM/YYYY
        sd_init = ""
        if data:
            sd_init = data.get("start_date_disp") or iso_to_display(data.get("start_date",""))
        self._start_date = QLineEdit()
        self._start_date.setStyleSheet(INPUT_QSS)
        self._start_date.setPlaceholderText("DD/MM/YYYY")
        self._start_date.setInputMask("99/99/9999")
        self._start_date.setFixedWidth(130)
        self._start_date.setText(sd_init)
        self._start_date.textChanged.connect(self._recompute_end)
        f2.addRow(self._lbl("Start Date *"), self._start_date)

        # Lead Time — weeks
        lt_init = float(data.get("lead_time_weeks", 2)) if data else 2.0
        self._lead_time = QDoubleSpinBox()
        self._lead_time.setRange(0.5, 104)
        self._lead_time.setSingleStep(0.5)
        self._lead_time.setDecimals(1)
        self._lead_time.setValue(lt_init)
        self._lead_time.setSuffix("  weeks")
        self._lead_time.setStyleSheet(INPUT_QSS)
        self._lead_time.setFixedWidth(130)
        self._lead_time.valueChanged.connect(self._recompute_end)
        f2.addRow(self._lbl("Lead Time *"), self._lead_time)

        # End Date — read-only computed display
        self._end_disp = QLabel()
        self._end_disp.setStyleSheet(
            f"color:{PRIMARY};font-weight:bold;font-size:9pt;"
            f"background:#EEF4FF;border:1px solid #C5D8F8;"
            f"border-radius:6px;padding:4px 12px;"
        )
        self._end_disp.setFixedWidth(160)
        end_row = QHBoxLayout()
        end_row.setSpacing(8)
        end_row.addWidget(self._end_disp)
        lock_lbl = QLabel("🔒 auto-computed")
        lock_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY};font-size:7.5pt;background:transparent;"
        )
        end_row.addWidget(lock_lbl)
        end_row.addStretch()
        f2.addRow(self._lbl("End Date"), end_row)

        # % Complete
        pct_init = float(data.get("pct_complete", 0)) if data else 0.0
        self._pct = QDoubleSpinBox()
        self._pct.setRange(0, 100)
        self._pct.setSingleStep(5)
        self._pct.setDecimals(0)
        self._pct.setValue(pct_init)
        self._pct.setSuffix("  %")
        self._pct.setStyleSheet(INPUT_QSS)
        self._pct.setFixedWidth(100)
        f2.addRow(self._lbl("% Complete"), self._pct)

        root.addLayout(f2)

        # Compute initial end date display
        self._recompute_end()

        # ══ Buttons ══════════════════════════════════════════════════════════
        btn_bar = QWidget()
        btn_bar.setStyleSheet(
            f"background:{BG};border-top:1px solid {BORDER};"
        )
        btn_row = QHBoxLayout(btn_bar)
        btn_row.setContentsMargins(24, 12, 24, 12)
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(BUTTON_SECONDARY_QSS)
        cancel.setFixedHeight(36)
        cancel.clicked.connect(self.reject)
        save = QPushButton("  Save Action  ")
        save.setStyleSheet(BUTTON_PRIMARY_QSS)
        save.setFixedHeight(36)
        save.clicked.connect(self._on_save)
        btn_row.addWidget(cancel)
        btn_row.addSpacing(10)
        btn_row.addWidget(save)
        root.addWidget(btn_bar)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _sec_label(text, style):
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        lbl.setFixedHeight(34)
        return lbl

    @staticmethod
    def _lbl(text):
        return make_label(text, FONT_SIZE_SM, bold=True)

    def _recompute_end(self):
        """Recompute and display end date whenever start date or lead time changes."""
        try:
            sd_iso = display_to_iso(self._start_date.text().strip())
            lt = self._lead_time.value()
            ed_iso = compute_end_date(sd_iso, lt)
            ed_disp = iso_to_display(ed_iso)
            self._end_disp.setText(f"📅  {ed_disp}")
            self._end_disp.setStyleSheet(
                f"color:{PRIMARY};font-weight:bold;font-size:9pt;"
                f"background:#EEF4FF;border:1px solid #C5D8F8;"
                f"border-radius:6px;padding:4px 12px;"
            )
            self._end_iso = ed_iso
        except Exception:
            self._end_disp.setText("—  (invalid date)")
            self._end_disp.setStyleSheet(
                "color:#E53935;font-weight:bold;font-size:9pt;"
                "background:#FFF5F5;border:1px solid #FFCDD2;"
                "border-radius:6px;padding:4px 12px;"
            )
            self._end_iso = None

    def _on_save(self):
        # Validate action name
        if not self._action.text().strip():
            QMessageBox.warning(self, "Validation", "Action name cannot be empty.")
            return
        # Validate start date
        try:
            display_to_iso(self._start_date.text().strip())
        except Exception:
            QMessageBox.warning(
                self, "Validation",
                "Start Date must be in DD/MM/YYYY format.\nExample: 19/04/2026"
            )
            return
        self.accept()

    def get_values(self):
        """
        Returns:
            (department, action, status, start_date_iso, lead_time_weeks, pct_complete)
        End date is intentionally NOT returned — the model computes it.
        """
        sd_iso = display_to_iso(self._start_date.text().strip())
        return (
            self._dept.currentText(),
            self._action.text().strip(),
            self._status.currentText(),
            sd_iso,
            self._lead_time.value(),
            self._pct.value(),
        )
