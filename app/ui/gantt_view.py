"""
Gantt Chart View — Week-based Industrialisation Planning Gantt.

Replaces the old phase/action timeline view with the professional
industrialisation Gantt (GanttPlanningView), adding a project-selector
combo at the top so users can switch between projects without leaving
the Gantt page.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.utils.theme import (
    FONT_FAMILY, FONT_SIZE_XL, FONT_SIZE_SM, FONT_SIZE_MD,
    TEXT_PRIMARY, TEXT_SECONDARY, BG, BG_CARD, BORDER, INPUT_QSS
)
from app.utils.widgets import make_label, CardFrame
from app.models.project_model import get_all_projects
from app.ui.gantt_planning_view import GanttPlanningView


class GanttView(QWidget):
    """
    Top-level Gantt page shown in the main sidebar navigation.

    Layout:
        ┌──────────────────────────────────────────┐
        │  Page title + subtitle                   │
        │  [Project combo ▾]                       │
        ├──────────────────────────────────────────┤
        │  GanttPlanningView (week-based Gantt)    │
        └──────────────────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_pid = None
        self._gantt_widget = None
        self._build()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(10)

        # ── Page header ───────────────────────────────────────────────────────
        root.addWidget(make_label("Gantt Planning", FONT_SIZE_XL, bold=True))
        root.addWidget(make_label(
            "Week-based industrialisation planning — planned vs. actual progress",
            FONT_SIZE_SM, color=TEXT_SECONDARY
        ))

        # ── Controls row ──────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        ctrl.addWidget(make_label("Project:", FONT_SIZE_SM, color=TEXT_SECONDARY))

        self._combo = QComboBox()
        self._combo.setStyleSheet(INPUT_QSS)
        self._combo.setMinimumWidth(300)
        self._combo.addItem("— Select a project —", None)
        for p in get_all_projects():
            self._combo.addItem(f"{p['project_id']} – {p['name']}", p["project_id"])
        self._combo.currentIndexChanged.connect(self._on_project_changed)
        ctrl.addWidget(self._combo)
        ctrl.addStretch()

        root.addLayout(ctrl)

        # ── Divider ───────────────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color:{BORDER};")
        root.addWidget(line)

        # ── Placeholder shown before a project is selected ────────────────────
        self._placeholder = make_label(
            "👆  Select a project above to display the week-based Gantt chart.",
            FONT_SIZE_MD, color=TEXT_SECONDARY
        )
        self._placeholder.setAlignment(Qt.AlignCenter)
        root.addWidget(self._placeholder, 1)

        # ── Gantt container (shown after selection) ───────────────────────────
        self._gantt_container = QWidget()
        self._gantt_container.setVisible(False)
        self._gantt_layout = QVBoxLayout(self._gantt_container)
        self._gantt_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._gantt_container, 1)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_project_changed(self, _idx):
        pid = self._combo.currentData()
        self._selected_pid = pid

        # Remove old GanttPlanningView if present
        if self._gantt_widget is not None:
            self._gantt_layout.removeWidget(self._gantt_widget)
            self._gantt_widget.deleteLater()
            self._gantt_widget = None

        if not pid:
            self._gantt_container.setVisible(False)
            self._placeholder.setVisible(True)
            return

        # Create a fresh GanttPlanningView for the selected project
        self._gantt_widget = GanttPlanningView(project_id=pid)
        self._gantt_layout.addWidget(self._gantt_widget)
        self._gantt_container.setVisible(True)
        self._placeholder.setVisible(False)

    # ── Called by MainWindow when navigating to this page ────────────────────

    def refresh(self):
        """Reload the project combo and re-render the current selection."""
        pid = self._selected_pid

        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem("— Select a project —", None)
        for p in get_all_projects():
            self._combo.addItem(f"{p['project_id']} – {p['name']}", p["project_id"])

        if pid:
            idx = self._combo.findData(pid)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
                self._combo.blockSignals(False)
                if self._gantt_widget is not None:
                    self._gantt_widget.project_id = pid
                    self._gantt_widget.refresh()
                return

        self._combo.blockSignals(False)
