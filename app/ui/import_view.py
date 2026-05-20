"""
Import View - Excel file import with preview and progress feedback.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QTableWidget, QTableWidgetItem, QProgressBar,
    QTextEdit, QFrame, QScrollArea, QComboBox, QHeaderView,
    QTabWidget, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from app.utils.theme import *
from app.utils.widgets import make_label, CardFrame, SectionHeader, HDivider
from app.services.excel_import import preview_excel, import_excel, import_multiple_excel


# ─────────────────────────────────────────────────────────────────────────────
# Background import thread
# ─────────────────────────────────────────────────────────────────────────────

class ImportThread(QThread):
    progress_msg = Signal(str)
    finished_import = Signal(dict)

    def __init__(self, filepaths: list[str]):
        super().__init__()
        self.filepaths = filepaths

    def run(self):
        result = import_multiple_excel(self.filepaths, callback=self.progress_msg.emit)
        self.finished_import.emit(result)


# ─────────────────────────────────────────────────────────────────────────────
# Import View
# ─────────────────────────────────────────────────────────────────────────────

class ImportView(QWidget):
    import_completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(20)

        # Header
        lay.addWidget(make_label("Import Projects from Excel", FONT_SIZE_XL, bold=True))
        lay.addWidget(make_label(
            "Import one or multiple Excel files. The app will auto-detect sheets "
            "(Projects, Milestones, Budget, Risks, Actions) and map columns intelligently.",
            FONT_SIZE_SM, color=TEXT_SECONDARY
        ))

        # ── File Selection Card ───────────────────────────────────────────────
        file_card = CardFrame()
        fc_lay = QVBoxLayout(file_card)
        fc_lay.setContentsMargins(20, 16, 20, 16)
        fc_lay.setSpacing(12)
        fc_lay.addWidget(make_label("1. Select Excel File(s)", FONT_SIZE_MD, bold=True))

        btn_row = QHBoxLayout()
        self.select_btn = QPushButton("📂 Browse Files...")
        self.select_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        self.select_btn.setFixedHeight(40)
        self.select_btn.clicked.connect(self._select_files)
        btn_row.addWidget(self.select_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(BUTTON_SECONDARY_QSS)
        self.clear_btn.clicked.connect(self._clear_files)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        fc_lay.addLayout(btn_row)

        self.file_list_lbl = make_label("No files selected.", FONT_SIZE_SM, color=TEXT_SECONDARY)
        fc_lay.addWidget(self.file_list_lbl)
        lay.addWidget(file_card)

        # ── Preview Card ──────────────────────────────────────────────────────
        prev_card = CardFrame()
        pc_lay = QVBoxLayout(prev_card)
        pc_lay.setContentsMargins(20, 16, 20, 16)
        pc_lay.setSpacing(10)

        ph = QHBoxLayout()
        ph.addWidget(make_label("2. Preview & Validate", FONT_SIZE_MD, bold=True))
        ph.addStretch()
        self.preview_btn = QPushButton("Preview Selected File")
        self.preview_btn.setStyleSheet(BUTTON_SECONDARY_QSS)
        self.preview_btn.clicked.connect(self._run_preview)
        ph.addWidget(self.preview_btn)
        pc_lay.addLayout(ph)

        self.preview_tabs = QTabWidget()
        self.preview_tabs.setStyleSheet(APP_QSS)
        self.preview_tabs.setMinimumHeight(220)
        pc_lay.addWidget(self.preview_tabs)
        lay.addWidget(prev_card)

        # ── Log Card ──────────────────────────────────────────────────────────
        log_card = CardFrame()
        lc_lay = QVBoxLayout(log_card)
        lc_lay.setContentsMargins(20, 16, 20, 16)
        lc_lay.setSpacing(10)
        lc_lay.addWidget(make_label("3. Import Log", FONT_SIZE_MD, bold=True))

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(130)
        self.log_box.setStyleSheet(f"""
            QTextEdit {{
                background: {SIDEBAR_BG}; color: #A5D6A7;
                font-family: Consolas, monospace; font-size: 9pt;
                border-radius: {RADIUS}px; padding: 8px;
                border: none;
            }}
        """)
        lc_lay.addWidget(self.log_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background: {BORDER}; border-radius: 3px; border: none; }}
            QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 3px; }}
        """)
        lc_lay.addWidget(self.progress_bar)
        lay.addWidget(log_card)

        # ── Import Button ─────────────────────────────────────────────────────
        import_row = QHBoxLayout()
        import_row.addStretch()
        self.import_btn = QPushButton("⬇ Import Now")
        self.import_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        self.import_btn.setFixedHeight(44)
        self.import_btn.setMinimumWidth(180)
        self.import_btn.clicked.connect(self._run_import)
        import_row.addWidget(self.import_btn)
        lay.addLayout(import_row)

        # ── Format Guide ──────────────────────────────────────────────────────
        guide_card = CardFrame()
        gl = QVBoxLayout(guide_card)
        gl.setContentsMargins(20, 16, 20, 16)
        gl.setSpacing(6)
        gl.addWidget(make_label("Expected Excel Format (Optional Multi-Sheet)", FONT_SIZE_MD, bold=True))
        guide_text = (
            "The importer auto-detects your columns. For best results, name sheets:\n"
            "  • Projects  — project_id, name, status, phase, priority, manager, client, "
            "start_date, end_date, progress\n"
            "  • Milestones — project_id, name, due_date, status, phase\n"
            "  • Budget — project_id, budget_type, planned_budget, actual_cost\n"
            "  • Risks — project_id, description, impact, mitigation, owner, status\n"
            "  • Actions — project_id, task_name, owner, due_date, status\n\n"
            "If sheets are not named correctly, the app tries to find them automatically."
        )
        guide_lbl = make_label(guide_text, FONT_SIZE_SM, color=TEXT_SECONDARY)
        guide_lbl.setWordWrap(True)
        gl.addWidget(guide_lbl)
        lay.addWidget(guide_card)
        lay.addStretch()

    def _select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Excel Files", "",
            "Excel Files (*.xlsx *.xls *.xlsm)"
        )
        if files:
            self._files = files
            names = "\n  • ".join([f.split("/")[-1] for f in files])
            self.file_list_lbl.setText(f"Selected ({len(files)} file(s)):\n  • {names}")
            self.file_list_lbl.setStyleSheet(f"color: {PRIMARY}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_SM}pt;")
            self._log(f"Selected {len(files)} file(s) for import.")

    def _clear_files(self):
        self._files = []
        self.file_list_lbl.setText("No files selected.")
        self.file_list_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-family: {FONT_FAMILY}; font-size: {FONT_SIZE_SM}pt;")
        while self.preview_tabs.count():
            self.preview_tabs.removeTab(0)

    def _run_preview(self):
        if not self._files:
            QMessageBox.information(self, "Preview", "Please select at least one file first.")
            return
        filepath = self._files[0]
        self._log(f"Previewing: {filepath.split('/')[-1]}")
        try:
            preview = preview_excel(filepath)
            while self.preview_tabs.count():
                self.preview_tabs.removeTab(0)

            for sheet_name, sheet_data in preview["sheets"].items():
                if "error" in sheet_data:
                    continue
                tab = self._build_preview_table(sheet_data)
                self.preview_tabs.addTab(tab, sheet_name)
            self._log(f"Preview complete. Sheets detected: {list(preview['sheets'].keys())}")
        except Exception as e:
            self._log(f"[ERROR] Preview failed: {e}")
            QMessageBox.critical(self, "Preview Error", str(e))

    def _build_preview_table(self, sheet_data: dict) -> QWidget:
        cols = sheet_data.get("columns", [])
        rows = sheet_data.get("rows", [])
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 6, 0, 6)
        total = sheet_data.get("total_rows", 0)
        lay.addWidget(make_label(f"Showing first {len(rows)} of {total} rows",
                                 FONT_SIZE_SM, color=TEXT_SECONDARY))
        table = QTableWidget(len(rows), len(cols))
        table.setHorizontalHeaderLabels([str(c) for c in cols])
        table.setStyleSheet(TABLE_QSS)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        for r_idx, row in enumerate(rows):
            for c_idx, col in enumerate(cols):
                val = str(row.get(col, "") or "")
                table.setItem(r_idx, c_idx, QTableWidgetItem(val))
        lay.addWidget(table)
        return w

    def _run_import(self):
        if not self._files:
            QMessageBox.information(self, "Import", "Please select at least one Excel file first.")
            return

        self.import_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self._log("Starting import...")

        self._thread = ImportThread(self._files)
        self._thread.progress_msg.connect(self._log)
        self._thread.finished_import.connect(self._import_done)
        self._thread.start()

    def _import_done(self, result: dict):
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(True)
        self._log(f"✅ Import complete.")
        self._log(f"   Projects imported/updated: {result['imported']}")
        if result.get("errors"):
            for e in result["errors"][:5]:
                self._log(f"   [!] {e}")
        self.import_completed.emit()
        QMessageBox.information(
            self, "Import Complete",
            f"Import finished successfully.\n\n"
            f"Projects: {result['imported']}\n"
            f"Errors: {len(result.get('errors', []))}"
        )

    def _log(self, msg: str):
        self.log_box.append(f"> {msg}")
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )
