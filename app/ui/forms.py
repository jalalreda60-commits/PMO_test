"""
Forms - All dialog windows (project, budget per type, gate date, phase action, risk).
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTextEdit, QDateEdit, QDoubleSpinBox, QSpinBox,
    QScrollArea, QWidget, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont

from app.utils.theme import *
from app.utils.widgets import make_label
from app.models.project_model import (
    upsert_project, upsert_budget, upsert_gate_date, upsert_phase_action, upsert_risk,
    get_project, get_all_budgets, insert_default_phase_actions, sync_volumes_for_project,
    PHASES, BUDGET_TYPES
)

STATUSES   = ["Active", "Completed", "Delayed", "At Risk", "On Hold", "Cancelled"]
PRIORITIES = ["Critical", "High", "Medium", "Low"]
GATE_STATUSES   = ["Pending", "Completed", "Delayed", "Cancelled"]
ACTION_STATUSES = ["Open", "Done"]
RISK_IMPACTS    = ["High", "Medium", "Low"]


def _lbl(text):
    l = QLabel(text)
    l.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM))
    l.setStyleSheet(f"color:{TEXT_SECONDARY};")
    return l


class BaseDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        self.setStyleSheet(APP_QSS + INPUT_QSS)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        hdr = QWidget()
        hdr.setStyleSheet(f"background:{SIDEBAR_BG};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(18,12,18,12)
        tl = QLabel(title); tl.setFont(QFont(FONT_FAMILY, FONT_SIZE_LG, QFont.Bold))
        tl.setStyleSheet("color:white;background:transparent;")
        hl.addWidget(tl)
        outer.addWidget(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        self.form_widget = QWidget()
        self.form_widget.setStyleSheet(f"background:{BG};")
        self.form_layout = QVBoxLayout(self.form_widget)
        self.form_layout.setContentsMargins(18,14,18,10); self.form_layout.setSpacing(10)
        scroll.setWidget(self.form_widget)
        outer.addWidget(scroll)

        footer = QWidget()
        footer.setStyleSheet(f"background:{BG_CARD};border-top:1px solid {BORDER};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(18,10,18,10); fl.addStretch()
        cancel = QPushButton("Cancel"); cancel.setStyleSheet(BUTTON_SECONDARY_QSS)
        cancel.clicked.connect(self.reject); fl.addWidget(cancel)
        self.save_btn = QPushButton("Save"); self.save_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
        self.save_btn.clicked.connect(self._on_save); fl.addWidget(self.save_btn)
        outer.addWidget(footer)

    def _section(self, title):
        gb = QGroupBox(title)
        gb.setStyleSheet(f"""QGroupBox{{font-weight:bold;font-family:{FONT_FAMILY};
            font-size:{FONT_SIZE_SM}pt;color:{PRIMARY};border:1px solid {BORDER};
            border-radius:{RADIUS}px;margin-top:12px;padding:14px 12px 10px;background:{BG_CARD};}}
            QGroupBox::title{{subcontrol-origin:margin;left:12px;padding:0 6px;}}""")
        return gb

    def _field(self, ph=""):
        f = QLineEdit(); f.setPlaceholderText(ph); f.setStyleSheet(INPUT_QSS); return f
    def _combo(self, items):
        c = QComboBox(); c.addItems(items); c.setStyleSheet(INPUT_QSS); return c
    def _date(self):
        d = QDateEdit(); d.setCalendarPopup(True); d.setDate(QDate.currentDate())
        d.setDisplayFormat("yyyy-MM-dd"); d.setStyleSheet(INPUT_QSS); return d
    def _double(self, prefix="€"):
        s = QDoubleSpinBox(); s.setPrefix(prefix); s.setMaximum(999_999_999)
        s.setGroupSeparatorShown(True); s.setStyleSheet(INPUT_QSS); return s
    def _textarea(self, ph=""):
        t = QTextEdit(); t.setPlaceholderText(ph); t.setFixedHeight(72); t.setStyleSheet(INPUT_QSS); return t
    def _on_save(self): raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# Project Form
# ─────────────────────────────────────────────────────────────────────────────
class ProjectForm(BaseDialog):
    def __init__(self, project_id=None, parent=None):
        self._pid = project_id
        super().__init__("Edit Project" if project_id else "New Project", parent)
        self.setMinimumWidth(660)
        self._build_form()
        if project_id: self._populate()

    def _build_form(self):
        fl = self.form_layout
        gen = self._section("General Information")
        gl = QFormLayout(gen); gl.setLabelAlignment(Qt.AlignRight); gl.setSpacing(10)
        self.pid_f    = self._field("e.g. PRJ-001")
        self.name_f   = self._field("Project name")
        self.status_c = self._combo(STATUSES)
        self.phase_c  = self._combo(PHASES)
        self.prio_c   = self._combo(PRIORITIES); self.prio_c.setCurrentText("Medium")
        self.mgr_f    = self._field("Project manager")
        self.dept_f   = self._field("Department / BU")
        self.client_f = self._field("Client / Customer")
        self.desc_f   = self._textarea("Brief description...")
        self.ref_spin = QSpinBox(); self.ref_spin.setRange(1,99); self.ref_spin.setStyleSheet(INPUT_QSS)
        self.ref_spin.valueChanged.connect(self._rebuild_ref_names)
        self.life_spin= QSpinBox(); self.life_spin.setRange(1,30); self.life_spin.setValue(5); self.life_spin.setStyleSheet(INPUT_QSS)
        gl.addRow(_lbl("Project ID *"),    self.pid_f)
        gl.addRow(_lbl("Project Name *"),  self.name_f)
        gl.addRow(_lbl("Status"),          self.status_c)
        gl.addRow(_lbl("Phase"),           self.phase_c)
        gl.addRow(_lbl("Priority"),        self.prio_c)
        gl.addRow(_lbl("Manager"),         self.mgr_f)
        gl.addRow(_lbl("Department"),      self.dept_f)
        gl.addRow(_lbl("Client"),          self.client_f)
        gl.addRow(_lbl("Nbr of Ref"),      self.ref_spin)
        gl.addRow(_lbl("Lifetime (years)"),self.life_spin)
        gl.addRow(_lbl("Description"),     self.desc_f)
        fl.addWidget(gen)

        # Ref Names section (dynamic)
        self._ref_section = self._section("Reference Names")
        self._ref_lay = QFormLayout(self._ref_section)
        self._ref_lay.setLabelAlignment(Qt.AlignRight); self._ref_lay.setSpacing(8)
        self._ref_edits = []
        fl.addWidget(self._ref_section)
        self._rebuild_ref_names(1)

        dates = self._section("Dates & Progress")
        dl = QFormLayout(dates); dl.setLabelAlignment(Qt.AlignRight); dl.setSpacing(10)
        self.start_d = self._date(); self.end_d = self._date()
        self.prog_sp = QSpinBox(); self.prog_sp.setRange(0,100); self.prog_sp.setSuffix(" %"); self.prog_sp.setStyleSheet(INPUT_QSS)
        dl.addRow(_lbl("Start Date"),  self.start_d)
        dl.addRow(_lbl("End Date"),    self.end_d)
        dl.addRow(_lbl("Progress"),    self.prog_sp)
        fl.addWidget(dates)

    def _rebuild_ref_names(self, count=None):
        """Rebuild the Ref name input fields based on current ref count."""
        if count is None:
            count = self.ref_spin.value()
        # Clear existing
        while self._ref_lay.rowCount():
            self._ref_lay.removeRow(0)
        self._ref_edits = []
        for i in range(1, count + 1):
            ed = QLineEdit()
            ed.setPlaceholderText(f"e.g. Ref {i} name")
            ed.setStyleSheet(INPUT_QSS)
            self._ref_lay.addRow(_lbl(f"Ref {i} Name"), ed)
            self._ref_edits.append(ed)

    def _get_ref_names_str(self):
        return "|".join(e.text().strip() or f"Ref {i+1}"
                        for i, e in enumerate(self._ref_edits))

    def _populate(self):
        p = get_project(self._pid)
        if not p: return
        self.pid_f.setText(p.get("project_id","")); self.pid_f.setReadOnly(True)
        self.name_f.setText(p.get("name",""))
        self.status_c.setCurrentText(p.get("status","Active"))
        self.phase_c.setCurrentText(p.get("phase","Phase 1"))
        self.prio_c.setCurrentText(p.get("priority","Medium"))
        self.mgr_f.setText(p.get("manager",""))
        self.dept_f.setText(p.get("department",""))
        self.client_f.setText(p.get("client",""))
        self.desc_f.setPlainText(p.get("description",""))
        nbr = int(p.get("nbr_ref",1) or 1)
        self.ref_spin.setValue(nbr)
        self._rebuild_ref_names(nbr)
        existing_names = (p.get("ref_names") or "").split("|")
        for i, ed in enumerate(self._ref_edits):
            if i < len(existing_names) and existing_names[i]:
                ed.setText(existing_names[i])
        self.life_spin.setValue(int(p.get("lifetime_years",5) or 5))
        if p.get("start_date"):
            self.start_d.setDate(QDate.fromString(p["start_date"],"yyyy-MM-dd"))
        if p.get("end_date"):
            self.end_d.setDate(QDate.fromString(p["end_date"],"yyyy-MM-dd"))
        self.prog_sp.setValue(int(p.get("progress",0) or 0))

    def _on_save(self):
        pid  = self.pid_f.text().strip()
        name = self.name_f.text().strip()
        if not pid:  QMessageBox.warning(self,"Validation","Project ID required."); return
        if not name: QMessageBox.warning(self,"Validation","Project Name required."); return
        lifetime = self.life_spin.value()
        data = {
            "project_id": pid, "name": name,
            "status": self.status_c.currentText(),
            "phase":  self.phase_c.currentText(),
            "priority": self.prio_c.currentText(),
            "manager": self.mgr_f.text().strip(),
            "department": self.dept_f.text().strip(),
            "client": self.client_f.text().strip(),
            "start_date": self.start_d.date().toString("yyyy-MM-dd"),
            "end_date":   self.end_d.date().toString("yyyy-MM-dd"),
            "progress":   self.prog_sp.value(),
            "description": self.desc_f.toPlainText().strip(),
            "nbr_ref": self.ref_spin.value(),
            "lifetime_years": lifetime,
            "ref_names": self._get_ref_names_str(),
        }
        is_new = not self._pid
        upsert_project(data)
        if is_new:
            insert_default_phase_actions(pid)
        sync_volumes_for_project(pid, lifetime)
        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# Budget Form (per type)
# ─────────────────────────────────────────────────────────────────────────────
class BudgetForm(BaseDialog):
    def __init__(self, project_id, budget_type, existing=None, parent=None):
        self._pid = project_id; self._btype = budget_type; self._existing = existing or {}
        super().__init__(f"Edit Budget – {budget_type}", parent)
        self._build_form()

    def _build_form(self):
        fl = self.form_layout
        sec = self._section(f"Budget: {self._btype}")
        lay = QFormLayout(sec); lay.setLabelAlignment(Qt.AlignRight); lay.setSpacing(10)
        self.planned = self._double()
        self.actual  = self._double()
        self.planned.setValue(float(self._existing.get("planned_budget",0) or 0))
        self.actual.setValue(float(self._existing.get("actual_cost",0) or 0))
        lay.addRow(_lbl("Planned Budget"), self.planned)
        lay.addRow(_lbl("Actual Cost"),    self.actual)
        fl.addWidget(sec)

    def _on_save(self):
        upsert_budget({
            "project_id": self._pid,
            "budget_type": self._btype,
            "planned_budget": self.planned.value(),
            "actual_cost": self.actual.value(),
        })
        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# Gate Date Form
# ─────────────────────────────────────────────────────────────────────────────
class GateDateForm(BaseDialog):
    def __init__(self, project_id, phase, existing=None, parent=None):
        self._pid = project_id; self._phase = phase; self._existing = existing or {}
        super().__init__(f"Gate Date – {phase}", parent)
        self._build_form()

    def _build_form(self):
        fl = self.form_layout
        sec = self._section(f"{self._phase} – Gate Exit Date")
        lay = QFormLayout(sec); lay.setLabelAlignment(Qt.AlignRight); lay.setSpacing(10)
        self.gate_date = self._date()
        if self._existing.get("gate_date"):
            self.gate_date.setDate(QDate.fromString(self._existing["gate_date"],"yyyy-MM-dd"))
        self.status_c = self._combo(GATE_STATUSES)
        self.status_c.setCurrentText(self._existing.get("status","Pending"))
        lay.addRow(_lbl("Gate Date"), self.gate_date)
        lay.addRow(_lbl("Status"),    self.status_c)
        fl.addWidget(sec)

    def _on_save(self):
        upsert_gate_date(self._pid, self._phase,
                         self.gate_date.date().toString("yyyy-MM-dd"),
                         self.status_c.currentText())
        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# Phase Action Form
# ─────────────────────────────────────────────────────────────────────────────
class PhaseActionForm(BaseDialog):
    def __init__(self, project_id, phase, parent=None, data=None):
        self._pid = project_id; self._phase = phase; self._data = data or {}
        super().__init__(("Edit" if data else "Add") + f" Action – {phase}", parent)
        self._build_form()
        if data: self._populate()

    def _build_form(self):
        fl = self.form_layout
        sec = self._section("Action Details")
        lay = QFormLayout(sec); lay.setLabelAlignment(Qt.AlignRight); lay.setSpacing(10)
        self.name_f = self._field("Action / task name")
        self.lt_sp  = QDoubleSpinBox()
        self.lt_sp.setRange(0, 999); self.lt_sp.setSuffix(" weeks"); self.lt_sp.setStyleSheet(INPUT_QSS)
        self.start_d = self._date(); self.end_d = self._date()
        self.status_c = self._combo(ACTION_STATUSES)
        lay.addRow(_lbl("Action Name *"), self.name_f)
        lay.addRow(_lbl("Lead Time"),     self.lt_sp)
        lay.addRow(_lbl("Start Date"),    self.start_d)
        lay.addRow(_lbl("End Date"),      self.end_d)
        lay.addRow(_lbl("Status"),        self.status_c)
        fl.addWidget(sec)

    def _rebuild_ref_names(self, count=None):
        """Rebuild the Ref name input fields based on current ref count."""
        if count is None:
            count = self.ref_spin.value()
        # Clear existing
        while self._ref_lay.rowCount():
            self._ref_lay.removeRow(0)
        self._ref_edits = []
        for i in range(1, count + 1):
            ed = QLineEdit()
            ed.setPlaceholderText(f"e.g. Ref {i} name")
            ed.setStyleSheet(INPUT_QSS)
            self._ref_lay.addRow(_lbl(f"Ref {i} Name"), ed)
            self._ref_edits.append(ed)

    def _get_ref_names_str(self):
        return "|".join(e.text().strip() or f"Ref {i+1}"
                        for i, e in enumerate(self._ref_edits))

    def _populate(self):
        self.name_f.setText(self._data.get("action_name",""))
        self.lt_sp.setValue(float(self._data.get("lead_time_weeks",0) or 0))
        if self._data.get("start_date"):
            self.start_d.setDate(QDate.fromString(self._data["start_date"],"yyyy-MM-dd"))
        if self._data.get("end_date"):
            self.end_d.setDate(QDate.fromString(self._data["end_date"],"yyyy-MM-dd"))
        self.status_c.setCurrentText(self._data.get("status","Open"))

    def _on_save(self):
        name = self.name_f.text().strip()
        if not name: QMessageBox.warning(self,"Validation","Action name required."); return
        upsert_phase_action({
            "id": self._data.get("id"),
            "project_id": self._pid,
            "phase": self._phase,
            "action_name": name,
            "lead_time_weeks": self.lt_sp.value(),
            "start_date": self.start_d.date().toString("yyyy-MM-dd"),
            "end_date":   self.end_d.date().toString("yyyy-MM-dd"),
            "status": self.status_c.currentText(),
            "sort_order": self._data.get("sort_order", 0),
        })
        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
# Risk Form
# ─────────────────────────────────────────────────────────────────────────────
class RiskForm(BaseDialog):
    def __init__(self, project_id, parent=None, data=None):
        self._pid = project_id; self._data = data or {}
        super().__init__("Add Risk" if not data else "Edit Risk", parent)
        self._build_form()
        if data: self._populate()

    def _build_form(self):
        fl = self.form_layout
        sec = self._section("Risk Details")
        lay = QFormLayout(sec); lay.setLabelAlignment(Qt.AlignRight); lay.setSpacing(10)
        self.desc_f  = self._textarea("Describe the risk...")
        self.impact_c = self._combo(RISK_IMPACTS)
        self.prob_c   = self._combo(RISK_IMPACTS)
        self.mit_f    = self._textarea("Mitigation actions...")
        self.owner_f  = self._field("Risk owner")
        self.status_c = self._combo(["Open","Mitigated","Closed","Accepted"])
        lay.addRow(_lbl("Description *"), self.desc_f)
        lay.addRow(_lbl("Impact"),        self.impact_c)
        lay.addRow(_lbl("Probability"),   self.prob_c)
        lay.addRow(_lbl("Mitigation"),    self.mit_f)
        lay.addRow(_lbl("Owner"),         self.owner_f)
        lay.addRow(_lbl("Status"),        self.status_c)
        fl.addWidget(sec)

    def _rebuild_ref_names(self, count=None):
        """Rebuild the Ref name input fields based on current ref count."""
        if count is None:
            count = self.ref_spin.value()
        # Clear existing
        while self._ref_lay.rowCount():
            self._ref_lay.removeRow(0)
        self._ref_edits = []
        for i in range(1, count + 1):
            ed = QLineEdit()
            ed.setPlaceholderText(f"e.g. Ref {i} name")
            ed.setStyleSheet(INPUT_QSS)
            self._ref_lay.addRow(_lbl(f"Ref {i} Name"), ed)
            self._ref_edits.append(ed)

    def _get_ref_names_str(self):
        return "|".join(e.text().strip() or f"Ref {i+1}"
                        for i, e in enumerate(self._ref_edits))

    def _populate(self):
        self.desc_f.setPlainText(self._data.get("description",""))
        self.impact_c.setCurrentText(self._data.get("impact","Medium"))
        self.prob_c.setCurrentText(self._data.get("probability","Medium"))
        self.mit_f.setPlainText(self._data.get("mitigation",""))
        self.owner_f.setText(self._data.get("owner",""))
        self.status_c.setCurrentText(self._data.get("status","Open"))

    def _on_save(self):
        desc = self.desc_f.toPlainText().strip()
        if not desc: QMessageBox.warning(self,"Validation","Description required."); return
        upsert_risk({
            "id": self._data.get("id"),
            "project_id": self._pid,
            "description": desc,
            "impact": self.impact_c.currentText(),
            "probability": self.prob_c.currentText(),
            "mitigation": self.mit_f.toPlainText().strip(),
            "owner": self.owner_f.text().strip(),
            "status": self.status_c.currentText(),
        })
        self.accept()
