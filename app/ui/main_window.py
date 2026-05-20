"""
Main Window — Ultra-fast sidebar, lazy-loaded pages, instant navigation.
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QStackedWidget,
    QSizePolicy, QToolButton, QMessageBox
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QTimer, Signal
)
from PySide6.QtGui import QFont, QCursor

from app.utils.theme import *
from app.utils.widgets import make_label
from app.ui.dashboard_view    import DashboardView
from app.ui.project_list_view import ProjectListView
from app.ui.project_detail_view import ProjectDetailView
from app.ui.import_view       import ImportView
from app.ui.reports_view      import ReportsView
from app.ui.kpi_view          import KPIView
from app.ui.forms             import ProjectForm
from app.ui.account_view      import AccountView

SIDEBAR_FULL = 220
SIDEBAR_MINI = 58
ANIM_MS      = 120

NAV_ITEMS = [
    ("dashboard", "🏠", "Dashboard"),
    ("projects",  "📁", "Projects"),
    ("kpi",       "📊", "KPI"),
    ("import",    "📤", "Import"),
    ("reports",   "📋", "Reports"),
    ("accounts",  "👤", "Accounts"),
]

_BTN_BASE = (
    "QPushButton{{"
    "background:transparent;color:#8DA3B5;border:none;border-radius:10px;"
    "text-align:left;padding:0 0 0 {pad}px;"
    "font-family:{ff};font-size:{fs}pt;font-weight:500;}}"
    "QPushButton:hover{{background:rgba(255,255,255,0.07);color:#E8EEF4;}}"
)
_BTN_ACTIVE = (
    "QPushButton{{"
    "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
    "stop:0 #1E63C3,stop:1 #1A80D9);"
    "color:white;border:none;border-radius:10px;"
    "text-align:left;padding:0 0 0 {pad}px;"
    "font-family:{ff};font-size:{fs}pt;font-weight:bold;}}"
)


class NavButton(QPushButton):
    def __init__(self, icon, label, page_id, parent=None):
        super().__init__(parent)
        self.page_id = page_id
        self._icon   = icon
        self._label  = label
        self._active = False
        self._mini   = False
        self.setCheckable(False)
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._render()

    def set_active(self, active):
        if self._active == active: return
        self._active = active
        self._apply_style()

    def set_mini(self, mini):
        if self._mini == mini: return
        self._mini = mini
        self._render()

    def _render(self):
        if self._mini:
            self.setText(f" {self._icon}")
            self.setToolTip(self._label)
            self.setFont(QFont(FONT_FAMILY, 13))
        else:
            self.setText(f"  {self._icon}   {self._label}")
            self.setToolTip("")
            self.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM))
        self._apply_style()

    def _apply_style(self):
        pad = 8 if self._mini else 14
        tpl = _BTN_ACTIVE if self._active else _BTN_BASE
        self.setStyleSheet(tpl.format(pad=pad, ff=FONT_FAMILY, fs=FONT_SIZE_SM))


class Sidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_FULL)
        self._mini = False
        self.setStyleSheet(
            "#Sidebar{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #0F1C2E,stop:1 #162032);border:none;}"
        )
        # Sidebar shadow removed for performance
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 14)
        lay.setSpacing(2)

        # Logo bar
        logo_bar = QWidget()
        logo_bar.setFixedHeight(62)
        logo_bar.setStyleSheet(
            "background:transparent;"
            "border-bottom:1px solid rgba(255,255,255,0.06);"
        )
        lb = QHBoxLayout(logo_bar); lb.setContentsMargins(12, 0, 8, 0)

        self._logo_icon = QLabel("◈")
        self._logo_icon.setFont(QFont(FONT_FAMILY, 15, QFont.Bold))
        self._logo_icon.setStyleSheet("color:#4FA3E0;background:transparent;")
        lb.addWidget(self._logo_icon)

        self._logo_text = QLabel("PMO Suite")
        self._logo_text.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self._logo_text.setStyleSheet(
            "color:#E8EEF4;background:transparent;margin-left:4px;"
        )
        lb.addWidget(self._logo_text); lb.addStretch()

        self._toggle = QToolButton()
        self._toggle.setText("‹")
        self._toggle.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        self._toggle.setFixedSize(30, 30)
        self._toggle.setCursor(QCursor(Qt.PointingHandCursor))
        self._toggle.setStyleSheet(
            "QToolButton{background:rgba(255,255,255,0.08);color:#8DA3B5;"
            "border:none;border-radius:15px;}"
            "QToolButton:hover{background:rgba(255,255,255,0.18);color:white;}"
        )
        lb.addWidget(self._toggle)
        lay.addWidget(logo_bar)
        lay.addSpacing(12)

        # Section label
        self._section_lbl = QLabel("NAVIGATION")
        self._section_lbl.setFont(QFont(FONT_FAMILY, 7, QFont.Bold))
        self._section_lbl.setStyleSheet(
            "color:#2D4255;background:transparent;padding-left:14px;letter-spacing:1px;"
        )
        self._section_lbl.setFixedHeight(18)
        lay.addWidget(self._section_lbl)
        lay.addSpacing(6)

        # Nav buttons
        self.nav_buttons = {}
        for page_id, icon, label in NAV_ITEMS:
            btn = NavButton(icon, label, page_id)
            lay.addWidget(btn)
            self.nav_buttons[page_id] = btn

        lay.addStretch()

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:rgba(255,255,255,0.05);max-height:1px;")
        lay.addWidget(sep); lay.addSpacing(8)

        # Logout button
        self._logout_btn = QPushButton()
        self._logout_btn.setFixedHeight(38)
        self._logout_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._logout_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._logout_btn.setStyleSheet("""
            QPushButton{
                background:rgba(239,68,68,0.12);
                color:#F87171;
                border:1px solid rgba(239,68,68,0.25);
                border-radius:9px;
                font-family:%s;font-size:9pt;font-weight:600;
                text-align:left;padding:0 0 0 14px;
            }
            QPushButton:hover{
                background:rgba(239,68,68,0.28);
                color:#FCA5A5;
                border-color:rgba(239,68,68,0.5);
            }
        """ % FONT_FAMILY)
        self._render_logout(False)
        lay.addWidget(self._logout_btn)
        lay.addSpacing(6)

        self._ver_lbl = QLabel("v2.1  ·  PMO Suite")
        self._ver_lbl.setFont(QFont(FONT_FAMILY, 7))
        self._ver_lbl.setStyleSheet("color:#243344;background:transparent;")
        self._ver_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._ver_lbl)

    def _render_logout(self, mini):
        if mini:
            self._logout_btn.setText(" 🔓")
            self._logout_btn.setToolTip("Logout")
        else:
            self._logout_btn.setText("  🔓   Logout")
            self._logout_btn.setToolTip("")

    def toggle(self):
        self._mini = not self._mini
        self._toggle.setText("›" if self._mini else "‹")
        self._logo_text.setVisible(not self._mini)
        self._section_lbl.setVisible(not self._mini)
        self._ver_lbl.setVisible(not self._mini)
        for btn in self.nav_buttons.values():
            btn.set_mini(self._mini)
        self._render_logout(self._mini)
        return self._mini

    @property
    def logout_btn(self):
        return self._logout_btn

    @property
    def toggle_btn(self):
        return self._toggle


class TopHeader(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopHeader")
        self.setFixedHeight(48)
        self.setStyleSheet(
            f"#TopHeader{{background:{BG_CARD};"
            f"border-bottom:1px solid {BORDER};}}"
        )
        lay = QHBoxLayout(self); lay.setContentsMargins(20, 0, 16, 0)

        self._title = QLabel("Dashboard")
        self._title.setFont(QFont(FONT_FAMILY, FONT_SIZE_MD, QFont.Bold))
        self._title.setStyleSheet(f"color:{TEXT_PRIMARY};background:transparent;")
        lay.addWidget(self._title); lay.addStretch()

        self._new_btn = QPushButton("＋  New Project")
        self._new_btn.setFixedHeight(34)
        self._new_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._new_btn.setStyleSheet(f"""
            QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #1565C0,stop:1 #1E88E5);
                color:white;border:none;border-radius:8px;padding:0 18px;
                font-family:{FONT_FAMILY};font-size:{FONT_SIZE_SM}pt;font-weight:bold;}}
            QPushButton:hover{{background:#1976D2;}}
            QPushButton:pressed{{background:#0D47A1;}}
        """)
        lay.addWidget(self._new_btn)

    def set_title(self, text):
        self._title.setText(text)

    @property
    def new_project_btn(self):
        return self._new_btn


class MainWindow(QMainWindow):
    def __init__(self, current_user: dict | None = None):
        super().__init__()
        self.current_user = current_user or {}
        self.setWindowTitle("PMO Portfolio Manager")
        self.setMinimumSize(1100, 700)
        self.resize(1440, 880)
        self._anim_group = None
        self._detail_widget = None
        self._build_ui()
        # Defer first paint so window appears instantly
        QTimer.singleShot(0, lambda: self._nav_to("dashboard"))

    def _build_ui(self):
        root = QWidget(); root.setStyleSheet(f"background:{BG};")
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0); root_lay.setSpacing(0)
        self.setCentralWidget(root)

        self.sidebar = Sidebar()
        self.sidebar.toggle_btn.clicked.connect(self._toggle_sidebar)
        for pid, btn in self.sidebar.nav_buttons.items():
            btn.clicked.connect(lambda _, p=pid: self._nav_to(p))
        self.sidebar.logout_btn.clicked.connect(self._logout)
        root_lay.addWidget(self.sidebar)

        right = QWidget(); right.setStyleSheet(f"background:{BG};")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0); right_lay.setSpacing(0)

        self.header = TopHeader()
        self.header.new_project_btn.clicked.connect(self._open_add_project)
        right_lay.addWidget(self.header)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background:{BG};")
        right_lay.addWidget(self.stack)
        root_lay.addWidget(right)

        # Lazy page registry: page_id -> [stack_index|None, factory, widget|None]
        self._pages = {
            "dashboard": [None, self._make_dashboard, None],
            "projects":  [None, self._make_projects,  None],
            "kpi":       [None, self._make_kpi,       None],
            "import":    [None, self._make_import,    None],
            "reports":   [None, self._make_reports,   None],
            "accounts":  [None, self._make_accounts,  None],
        }
        self._titles = {
            "dashboard": "Dashboard",
            "projects":  "Projects",
            "kpi":       "KPI Monthly Review",
            "import":    "Import from Excel",
            "reports":   "Reports",
            "accounts":  "Account Management",
        }

    # ── Lazy factories ─────────────────────────────────────────────────────────
    def _make_dashboard(self):
        return DashboardView()

    def _make_projects(self):
        w = ProjectListView()
        w.project_selected.connect(self._open_project_detail)
        w.add_project_requested.connect(self._open_add_project)
        w.edit_project_requested.connect(self._open_edit_project)
        return w

    def _make_kpi(self):
        return KPIView()

    def _make_import(self):
        w = ImportView()
        w.import_completed.connect(self._on_import_completed)
        return w

    def _make_reports(self):
        return ReportsView()

    def _make_accounts(self):
        return AccountView(current_user=self.current_user)

    def _logout(self):
        """Confirm, close main window, re-open login screen."""
        reply = QMessageBox.question(
            self, "Logout",
            "Are you sure you want to logout?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Import here to avoid circular imports at module level
        from app.ui.login_window import LoginWindow
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve

        self._login_win = LoginWindow()

        def _on_login(user):
            from PySide6.QtWidgets import QGraphicsOpacityEffect
            new_win = MainWindow(current_user=user)
            fx = QGraphicsOpacityEffect(new_win.centralWidget())
            fx.setOpacity(0.0)
            new_win.centralWidget().setGraphicsEffect(fx)
            new_win.show()
            anim = QPropertyAnimation(fx, b"opacity", new_win)
            anim.setDuration(500)
            anim.setStartValue(0.0); anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            new_win._fade_in_anim = anim
            anim.start()

        self._login_win.set_success_callback(_on_login)
        self._login_win.show()
        self.close()

    # ── Navigation ─────────────────────────────────────────────────────────────
    def _nav_to(self, page_id):
        for pid, btn in self.sidebar.nav_buttons.items():
            btn.set_active(pid == page_id)

        entry = self._pages[page_id]
        if entry[0] is None:                    # first visit → build page
            w = entry[1]()
            entry[2] = w
            entry[0] = self.stack.addWidget(w)

        self.stack.setCurrentIndex(entry[0])
        self.header.set_title(self._titles[page_id])

        # Refresh the visible page (lightweight for list views)
        w = entry[2]
        if hasattr(w, "refresh"):
            w.refresh()

    # ── Sidebar animation ──────────────────────────────────────────────────────
    def _toggle_sidebar(self):
        mini   = self.sidebar.toggle()
        target = SIDEBAR_MINI if mini else SIDEBAR_FULL

        if self._anim_group:
            self._anim_group.stop()

        g = QParallelAnimationGroup(self)
        for prop in (b"minimumWidth", b"maximumWidth"):
            a = QPropertyAnimation(self.sidebar, prop, g)
            a.setDuration(ANIM_MS)
            a.setStartValue(self.sidebar.width())
            a.setEndValue(target)
            a.setEasingCurve(QEasingCurve.OutCubic)
            g.addAnimation(a)
        self._anim_group = g
        g.start()

    # ── Project detail ─────────────────────────────────────────────────────────
    def _open_project_detail(self, pid):
        if self._detail_widget:
            self.stack.removeWidget(self._detail_widget)
            self._detail_widget.deleteLater()
            self._detail_widget = None
        detail = ProjectDetailView(pid)
        detail.back_requested.connect(lambda: self._nav_to("projects"))
        detail.edit_requested.connect(self._open_edit_project)
        self.stack.addWidget(detail)
        self.stack.setCurrentWidget(detail)
        self._detail_widget = detail
        for btn in self.sidebar.nav_buttons.values(): btn.set_active(False)
        self.header.set_title("Project Detail")

    def _open_add_project(self):
        if ProjectForm(parent=self).exec():
            self._nav_to("projects")
            if self._pages["dashboard"][2]: self._pages["dashboard"][2].refresh()

    def _open_edit_project(self, pid):
        if ProjectForm(project_id=pid, parent=self).exec():
            self._nav_to("projects")
            if self._pages["dashboard"][2]: self._pages["dashboard"][2].refresh()

    def _on_import_completed(self):
        if self._pages["dashboard"][2]: self._pages["dashboard"][2].refresh()
        if self._pages["projects"][2]:  self._pages["projects"][2].refresh()
