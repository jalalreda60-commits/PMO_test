"""
Project List View - Filterable, searchable table of all projects.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QComboBox,
    QHeaderView, QMenu, QMessageBox, QAbstractItemView, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QCursor

from app.utils.theme import *
from app.utils.widgets import (make_label, SectionHeader, StatusBadge,
                                StyledProgressBar, CardFrame, HDivider)
from app.models.project_model import get_all_projects, delete_project


class ProjectListView(QWidget):
    project_selected = Signal(str)   # emits project_id
    add_project_requested = Signal()
    edit_project_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filters = {}
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_filters)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.addWidget(make_label("Projects", FONT_SIZE_XL, bold=True))
        title_col.addWidget(make_label("Manage and monitor all projects",
                                       FONT_SIZE_SM, color=TEXT_SECONDARY))
        header_row.addLayout(title_col)
        header_row.addStretch()
        add_btn = QPushButton("+ New Project")
        add_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        add_btn.clicked.connect(self.add_project_requested)
        header_row.addWidget(add_btn)
        lay.addLayout(header_row)

        # ── Filter Bar ────────────────────────────────────────────────────────
        filter_card = CardFrame()
        filter_lay = QHBoxLayout(filter_card)
        filter_lay.setContentsMargins(10, 8, 10, 8)
        filter_lay.setSpacing(8)

        # Search
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Search project, manager, client...")
        self.search_box.setStyleSheet(INPUT_QSS)
        self.search_box.setMinimumWidth(240)
        self.search_box.textChanged.connect(lambda: self._search_timer.start(300))
        filter_lay.addWidget(self.search_box, 2)

        # Status filter
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All Status", "Active", "Completed", "Delayed", "At Risk", "On Hold"])
        self.status_combo.setStyleSheet(INPUT_QSS)
        self.status_combo.currentTextChanged.connect(self._apply_filters)
        filter_lay.addWidget(self.status_combo, 1)

        # Phase filter
        self.phase_combo = QComboBox()
        self.phase_combo.addItems(["All Phases", "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"])
        self.phase_combo.setStyleSheet(INPUT_QSS)
        self.phase_combo.currentTextChanged.connect(self._apply_filters)
        filter_lay.addWidget(self.phase_combo, 1)

        # Priority filter
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["All Priorities", "Critical", "High", "Medium", "Low"])
        self.priority_combo.setStyleSheet(INPUT_QSS)
        self.priority_combo.currentTextChanged.connect(self._apply_filters)
        filter_lay.addWidget(self.priority_combo, 1)

        # Reset
        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet(BUTTON_SECONDARY_QSS)
        reset_btn.clicked.connect(self._reset_filters)
        filter_lay.addWidget(reset_btn)

        lay.addWidget(filter_card)

        # ── Result count ──────────────────────────────────────────────────────
        self.count_lbl = make_label("", FONT_SIZE_SM, color=TEXT_SECONDARY)
        lay.addWidget(self.count_lbl)

        # ── Table ─────────────────────────────────────────────────────────────
        cols = ["Project ID", "Project Name", "Phase", "Status",
                "Progress", "Manager", "Client", "Priority", "Start Date", "End Date", ""]
        self.table = QTableWidget(0, len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setStyleSheet(TABLE_QSS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(self._on_double_click)

        hdr = self.table.horizontalHeader()
        hdr.setMinimumSectionSize(60)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # Project ID
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)            # Name — fills space
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # Phase
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # Status
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)              # Progress
        self.table.setColumnWidth(4, 140)
        hdr.setSectionResizeMode(5, QHeaderView.Interactive)        # Manager
        self.table.setColumnWidth(5, 110)
        hdr.setSectionResizeMode(6, QHeaderView.Interactive)        # Client
        self.table.setColumnWidth(6, 110)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)   # Priority
        hdr.setSectionResizeMode(8, QHeaderView.Interactive)        # Start Date
        self.table.setColumnWidth(8, 90)
        hdr.setSectionResizeMode(9, QHeaderView.Interactive)        # End Date
        self.table.setColumnWidth(9, 90)
        hdr.setSectionResizeMode(10, QHeaderView.Fixed)             # Actions
        self.table.setColumnWidth(10, 80)
        hdr.setStretchLastSection(False)

        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        lay.addWidget(self.table, 1)   # stretch=1 so table fills remaining height
        self._load_data()

    def _load_data(self, filters: dict | None = None):
        projects = get_all_projects(filters)
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)  # suppress repaints during fill
        self.table.setRowCount(len(projects))

        for row_idx, p in enumerate(projects):
            self.table.setRowHeight(row_idx, 44)

            self.table.setItem(row_idx, 0, self._item(p.get("project_id", "")))
            self.table.setItem(row_idx, 1, self._bold_item(p.get("name", "")))

            # Phase badge
            phase = p.get("phase", "")
            phase_item = QTableWidgetItem(phase)
            phase_item.setForeground(QColor(PHASE_COLORS.get(phase, TEXT_SECONDARY)))
            phase_item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
            self.table.setItem(row_idx, 2, phase_item)

            # Status badge widget
            badge = StatusBadge(p.get("status", "Active"))
            self.table.setCellWidget(row_idx, 3, self._center_wrap(badge))

            # Progress bar
            prog = p.get("progress", 0)
            pb = StyledProgressBar(prog, self._progress_color(prog))
            self.table.setCellWidget(row_idx, 4, self._pad_wrap(pb))

            self.table.setItem(row_idx, 5, self._item(p.get("manager", "")))
            self.table.setItem(row_idx, 6, self._item(p.get("client", "")))

            # Priority
            prio = p.get("priority", "Medium")
            prio_item = QTableWidgetItem(prio)
            prio_item.setForeground(QColor(PRIORITY_COLORS.get(prio, TEXT_SECONDARY)))
            prio_item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
            self.table.setItem(row_idx, 7, prio_item)

            self.table.setItem(row_idx, 8, self._item(p.get("start_date", "")))
            self.table.setItem(row_idx, 9, self._item(p.get("end_date", "")))

            # Action buttons
            btn_widget = self._make_row_actions(p["project_id"])
            self.table.setCellWidget(row_idx, 10, btn_widget)

        self.count_lbl.setText(f"{len(projects)} project{'s' if len(projects) != 1 else ''} found")
        self.table.setUpdatesEnabled(True)  # re-enable after fill
        self.table.setSortingEnabled(True)

    def _apply_filters(self):
        filters = {}
        search = self.search_box.text().strip()
        if search:
            filters["search"] = search
        status = self.status_combo.currentText()
        if status != "All Status":
            filters["status"] = status
        phase = self.phase_combo.currentText()
        if phase != "All Phases":
            filters["phase"] = phase
        priority = self.priority_combo.currentText()
        if priority != "All Priorities":
            filters["priority"] = priority
        self._load_data(filters)

    def _reset_filters(self):
        self.search_box.clear()
        self.status_combo.setCurrentIndex(0)
        self.phase_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self._load_data()

    def _on_double_click(self, index):
        row = index.row()
        item = self.table.item(row, 0)
        if item:
            self.project_selected.emit(item.text())

    def _context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        pid_item = self.table.item(row, 0)
        if not pid_item:
            return
        pid = pid_item.text()

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {BG_CARD}; border: 1px solid {BORDER};
                     border-radius: {RADIUS}px; padding: 4px; }}
            QMenu::item {{ padding: 8px 20px; color: {TEXT_PRIMARY}; font-family: {FONT_FAMILY}; }}
            QMenu::item:selected {{ background: #E3F2FD; color: {PRIMARY}; border-radius: 4px; }}
        """)
        open_act = menu.addAction("📂  Open Details")
        edit_act = menu.addAction("✏️  Edit Project")
        menu.addSeparator()
        del_act = menu.addAction("🗑  Delete Project")
        del_act.setProperty("danger", True)

        action = menu.exec(QCursor.pos())
        if action == open_act:
            self.project_selected.emit(pid)
        elif action == edit_act:
            self.edit_project_requested.emit(pid)
        elif action == del_act:
            self._confirm_delete(pid)

    def _confirm_delete(self, project_id: str):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete project '{project_id}'?\n"
            "This will also remove all milestones, risks, actions, and budget data.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_project(project_id)
            self.refresh()

    def _make_row_actions(self, pid: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(4)
        view_btn = QPushButton("View")
        view_btn.setFixedHeight(28)
        view_btn.setStyleSheet(BUTTON_PRIMARY_QSS + "QPushButton { padding: 4px 10px; font-size: 8pt; }")
        view_btn.clicked.connect(lambda: self.project_selected.emit(pid))
        h.addWidget(view_btn)
        return w

    def refresh(self):
        self._apply_filters()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM))
        return item

    def _bold_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        item.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM, QFont.Bold))
        return item

    def _center_wrap(self, widget: QWidget) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 2, 4, 2)
        h.addStretch()
        h.addWidget(widget)
        h.addStretch()
        return w

    def _pad_wrap(self, widget: QWidget) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(8, 8, 8, 8)
        h.addWidget(widget)
        return w

    def _progress_color(self, progress: float) -> str:
        if progress >= 80:
            return STATUS_COLORS["Completed"]
        if progress >= 50:
            return PRIMARY
        if progress >= 25:
            return STATUS_COLORS["At Risk"]
        return STATUS_COLORS["Delayed"]
