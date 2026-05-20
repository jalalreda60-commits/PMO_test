"""
main.py - Entry point for PMO Portfolio Manager
Run: python main.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect
from PySide6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui     import QFont

from app.database.db_manager  import initialize_database, initialize_kpi_tables, get_connection
from app.models.auth_model    import initialize_auth_tables
from app.ui.login_window      import LoginWindow
from app.ui.main_window       import MainWindow
from app.utils.theme          import FONT_FAMILY, APP_QSS


def _set_app_icon(app):
    from PySide6.QtGui import QIcon
    base = os.path.dirname(__file__)
    for sz in [256, 128, 64, 48, 32, 16]:
        path = os.path.join(base, "icons", f"icon_{sz}x{sz}.png")
        if os.path.exists(path):
            app.setWindowIcon(QIcon(path))
            return
    ico = os.path.join(base, "icons", "pmo_app.ico")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))


def _seed_kpi_data_if_needed():
    conn  = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM kpi_monthly_scores").fetchone()[0]
    if count == 0:
        try:
            from populate_kpi_data import populate
            populate()
            print("✅ KPI data seeded from Excel file.")
        except Exception as e:
            print(f"⚠ KPI seed skipped: {e}")


def _launch_main_window(user: dict | None = None):
    """Create MainWindow with the logged-in user, fade it in from transparent."""
    window = MainWindow(current_user=user or {})

    fx = QGraphicsOpacityEffect(window.centralWidget())
    fx.setOpacity(0.0)
    window.centralWidget().setGraphicsEffect(fx)
    window.show()

    anim = QPropertyAnimation(fx, b"opacity", window)
    anim.setDuration(500)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    window._fade_in_anim = anim   # keep reference
    anim.start()


def main():
    initialize_database()
    initialize_kpi_tables()
    initialize_auth_tables()
    _seed_kpi_data_if_needed()

    app = QApplication(sys.argv)
    app.setApplicationName("PMO Portfolio Manager")
    app.setOrganizationName("Orhan Automotive")
    _set_app_icon(app)
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setStyleSheet(APP_QSS)
    try:
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except AttributeError:
        pass

    login = LoginWindow()

    def on_login_success(user: dict):
        print(f"[Auth] Login: {user.get('username')} ({user.get('role')})")
        _launch_main_window(user)

    login.set_success_callback(on_login_success)
    login.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
