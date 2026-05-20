"""
Reports View - Export projects to Excel and PDF.
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QComboBox, QFrame, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.utils.theme import *
from app.utils.widgets import make_label, CardFrame, SectionHeader
from app.models.project_model import get_all_projects
from app.services.export_service import (
    export_all_projects_excel, export_project_detail_excel, export_project_pdf
)


class ReportsView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(20)
        self.setWidget(inner)
        self._build(lay)

    def _build(self, lay):
        lay.addWidget(make_label("Reports & Exports", FONT_SIZE_XL, bold=True))
        lay.addWidget(make_label("Generate and download project reports in Excel or PDF format.",
                                 FONT_SIZE_SM, color=TEXT_SECONDARY))

        # ── Export All Projects ───────────────────────────────────────────────
        card1 = self._report_card(
            "📊 Portfolio Summary (Excel)",
            "Export the full list of all projects with their key information to an Excel file.",
            "Export All to Excel",
            self._export_all_excel
        )
        lay.addWidget(card1)

        # ── Export Single Project (Excel) ────────────────────────────────────
        card2 = CardFrame()
        cl = QVBoxLayout(card2)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.setSpacing(12)
        cl.addWidget(make_label("📋 Single Project Detail (Excel)", FONT_SIZE_MD, bold=True))
        cl.addWidget(make_label("Export one project with all milestones, budget, risks, and actions.",
                                FONT_SIZE_SM, color=TEXT_SECONDARY))

        project_row = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.setStyleSheet(INPUT_QSS)
        self.project_combo.setMinimumWidth(280)
        self._load_project_combo()
        project_row.addWidget(self.project_combo, 2)
        xl_btn = QPushButton("Export to Excel")
        xl_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        xl_btn.clicked.connect(self._export_single_excel)
        project_row.addWidget(xl_btn)
        pdf_btn = QPushButton("Export to PDF")
        pdf_btn.setStyleSheet(BUTTON_SECONDARY_QSS)
        pdf_btn.clicked.connect(self._export_single_pdf)
        project_row.addWidget(pdf_btn)
        project_row.addStretch()
        cl.addLayout(project_row)
        lay.addWidget(card2)

        lay.addWidget(make_label("Output files are saved to your chosen location.",
                                 FONT_SIZE_SM, color=TEXT_SECONDARY))
        lay.addStretch()

    def _report_card(self, title: str, desc: str, btn_label: str, fn) -> CardFrame:
        card = CardFrame()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.setSpacing(10)
        cl.addWidget(make_label(title, FONT_SIZE_MD, bold=True))
        cl.addWidget(make_label(desc, FONT_SIZE_SM, color=TEXT_SECONDARY))
        btn_row = QHBoxLayout()
        btn = QPushButton(btn_label)
        btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        btn.clicked.connect(fn)
        btn_row.addWidget(btn)
        btn_row.addStretch()
        cl.addLayout(btn_row)
        return card

    def _load_project_combo(self):
        self.project_combo.clear()
        projects = get_all_projects()
        for p in projects:
            self.project_combo.addItem(f"{p['project_id']} – {p['name']}", p["project_id"])

    def _export_all_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Portfolio Report", "PMO_Portfolio.xlsx",
            "Excel Files (*.xlsx)"
        )
        if path:
            try:
                out = export_all_projects_excel(path)
                QMessageBox.information(self, "Export Complete",
                                        f"Portfolio exported to:\n{out}")
                os.startfile(os.path.dirname(out))
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _export_single_excel(self):
        pid = self.project_combo.currentData()
        if not pid:
            QMessageBox.information(self, "Select Project", "Please select a project first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project Report", f"Project_{pid}.xlsx",
            "Excel Files (*.xlsx)"
        )
        if path:
            try:
                out = export_project_detail_excel(pid, path)
                QMessageBox.information(self, "Export Complete", f"Project exported to:\n{out}")
                os.startfile(os.path.dirname(out))
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _export_single_pdf(self):
        pid = self.project_combo.currentData()
        if not pid:
            QMessageBox.information(self, "Select Project", "Please select a project first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", f"Project_{pid}.pdf",
            "PDF Files (*.pdf)"
        )
        if path:
            try:
                out = export_project_pdf(pid, path)
                QMessageBox.information(self, "Export Complete", f"PDF exported to:\n{out}")
                os.startfile(os.path.dirname(out))
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def refresh(self):
        self._load_project_combo()
