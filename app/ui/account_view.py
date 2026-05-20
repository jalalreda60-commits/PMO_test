"""
account_view.py — Account Management page for PMO Suite.

Permission model
────────────────
Admin
  • Sees all user accounts
  • Can Add, Edit (name + role), Delete any account
  • Can reset any user's password (no old-password required)
  • Cannot delete the last admin account

Regular User / Viewer
  • Sees ONLY their own account card
  • Cannot see other users at all
  • Can change their own password (requires current password)
  • Cannot edit display name, role, or create/delete users
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QDialog, QDialogButtonBox, QFormLayout,
    QLineEdit, QComboBox, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui  import QFont

from app.utils.theme   import *
from app.utils.widgets import make_label
from app.models.auth_model import (
    get_user, create_user, change_password, validate_login
)
from app.database.db_manager import get_connection


# ══════════════════════════════════════════════════════════════════════════════
# DB helpers
# ══════════════════════════════════════════════════════════════════════════════
def _all_users() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, role, display_name, last_login "
        "FROM users ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def _delete_user(user_id: int) -> tuple[bool, str]:
    conn = get_connection()
    admin_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role='admin'"
    ).fetchone()[0]
    target = conn.execute(
        "SELECT role FROM users WHERE id=?", (user_id,)
    ).fetchone()
    if target and target[0] == "admin" and admin_count <= 1:
        return False, "Cannot delete the last administrator account."
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    return True, ""


def _update_user(user_id: int, display_name: str, role: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE users SET display_name=?, role=? WHERE id=?",
        (display_name, role, user_id),
    )
    conn.commit()


def _admin_reset_password(user_id: int, new_password: str) -> None:
    """Admin-only: reset any user password without knowing the current one."""
    import hashlib, os
    salt = os.urandom(32)
    key  = hashlib.pbkdf2_hmac("sha256", new_password.encode(), salt, 600_000)
    conn = get_connection()
    conn.execute(
        "UPDATE users SET salt_hex=?, hash_hex=? WHERE id=?",
        (salt.hex(), key.hex(), user_id),
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# Admin-only: Add / Edit User dialog
# ══════════════════════════════════════════════════════════════════════════════
class _AdminUserDialog(QDialog):
    def __init__(self, user: dict | None = None, parent=None):
        super().__init__(parent)
        self._user = user
        self.setWindowTitle("Edit User" if user else "Add User")
        self.setMinimumWidth(420)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14); lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(make_label(
            "Edit User" if self._user else "Add New User",
            FONT_SIZE_MD, bold=True
        ))

        form = QFormLayout(); form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        def _lbl(t):
            l = QLabel(t); l.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM))
            l.setStyleSheet(f"color:{TEXT_SECONDARY};"); return l

        self._username = QLineEdit(self._user["username"] if self._user else "")
        self._username.setStyleSheet(INPUT_QSS)
        self._username.setPlaceholderText("e.g. john.doe")
        if self._user:
            self._username.setEnabled(False)
        form.addRow(_lbl("Username"), self._username)

        self._display = QLineEdit((self._user or {}).get("display_name", ""))
        self._display.setStyleSheet(INPUT_QSS)
        self._display.setPlaceholderText("Full name")
        form.addRow(_lbl("Display Name"), self._display)

        self._role = QComboBox(); self._role.setStyleSheet(INPUT_QSS)
        self._role.addItems(["user", "admin", "viewer"])
        if self._user:
            self._role.setCurrentText(self._user.get("role", "user"))
        form.addRow(_lbl("Role"), self._role)

        if not self._user:
            self._pw = QLineEdit(); self._pw.setEchoMode(QLineEdit.Password)
            self._pw.setStyleSheet(INPUT_QSS)
            self._pw.setPlaceholderText("Minimum 6 characters")
            form.addRow(_lbl("Password"), self._pw)

            self._pw2 = QLineEdit(); self._pw2.setEchoMode(QLineEdit.Password)
            self._pw2.setStyleSheet(INPUT_QSS)
            self._pw2.setPlaceholderText("Confirm password")
            form.addRow(_lbl("Confirm Password"), self._pw2)
        else:
            self._pw = self._pw2 = None

        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setStyleSheet(BUTTON_PRIMARY_QSS)
        lay.addWidget(btns)

    def _save(self):
        username = self._username.text().strip()
        display  = self._display.text().strip() or username
        role     = self._role.currentText()
        if not username:
            QMessageBox.warning(self, "Validation", "Username is required."); return
        if self._user:
            _update_user(self._user["id"], display, role)
            self.accept()
        else:
            pw, pw2 = self._pw.text(), self._pw2.text()
            if len(pw) < 6:
                QMessageBox.warning(self, "Validation",
                    "Password must be at least 6 characters."); return
            if pw != pw2:
                QMessageBox.warning(self, "Validation", "Passwords do not match."); return
            try:
                create_user(username, pw, role, display)
                self.accept()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create user:\n{e}")


# ══════════════════════════════════════════════════════════════════════════════
# Admin-only: Reset any user's password (no old password needed)
# ══════════════════════════════════════════════════════════════════════════════
class _AdminResetPasswordDialog(QDialog):
    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self._user = user
        self.setWindowTitle(f"Reset Password — {user['username']}")
        self.setMinimumWidth(380)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14); lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(make_label(
            f"Reset password for: {self._user.get('display_name') or self._user['username']}",
            FONT_SIZE_MD, bold=True
        ))

        note = QLabel(
            "⚠  Admin override — current password is not required."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "color:#E65100;background:#FFF3E0;padding:6px;"
            "border-radius:4px;font-size:8pt;"
        )
        lay.addWidget(note)

        form = QFormLayout(); form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        def _lbl(t):
            l = QLabel(t); l.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM))
            l.setStyleSheet(f"color:{TEXT_SECONDARY};"); return l

        self._new  = QLineEdit(); self._new.setEchoMode(QLineEdit.Password)
        self._new.setStyleSheet(INPUT_QSS)
        self._new.setPlaceholderText("Minimum 6 characters")
        form.addRow(_lbl("New Password"), self._new)

        self._new2 = QLineEdit(); self._new2.setEchoMode(QLineEdit.Password)
        self._new2.setStyleSheet(INPUT_QSS)
        form.addRow(_lbl("Confirm Password"), self._new2)

        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setStyleSheet(BUTTON_PRIMARY_QSS)
        lay.addWidget(btns)

    def _save(self):
        new, new2 = self._new.text(), self._new2.text()
        if len(new) < 6:
            QMessageBox.warning(self, "Validation",
                "Password must be at least 6 characters."); return
        if new != new2:
            QMessageBox.warning(self, "Validation", "Passwords do not match."); return
        _admin_reset_password(self._user["id"], new)
        QMessageBox.information(self, "Success",
            f"Password for '{self._user['username']}' has been reset.")
        self.accept()


# ══════════════════════════════════════════════════════════════════════════════
# Regular user: change own password (requires current password)
# ══════════════════════════════════════════════════════════════════════════════
class _SelfChangePasswordDialog(QDialog):
    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self._username = username
        self.setWindowTitle("Change My Password")
        self.setMinimumWidth(380)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14); lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(make_label("Change My Password", FONT_SIZE_MD, bold=True))

        form = QFormLayout(); form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        def _lbl(t):
            l = QLabel(t); l.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM))
            l.setStyleSheet(f"color:{TEXT_SECONDARY};"); return l

        self._old  = QLineEdit(); self._old.setEchoMode(QLineEdit.Password)
        self._old.setStyleSheet(INPUT_QSS)
        form.addRow(_lbl("Current Password"), self._old)

        self._new  = QLineEdit(); self._new.setEchoMode(QLineEdit.Password)
        self._new.setStyleSheet(INPUT_QSS)
        self._new.setPlaceholderText("Minimum 6 characters")
        form.addRow(_lbl("New Password"), self._new)

        self._new2 = QLineEdit(); self._new2.setEchoMode(QLineEdit.Password)
        self._new2.setStyleSheet(INPUT_QSS)
        form.addRow(_lbl("Confirm New Password"), self._new2)

        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Save).setStyleSheet(BUTTON_PRIMARY_QSS)
        lay.addWidget(btns)

    def _save(self):
        old, new, new2 = self._old.text(), self._new.text(), self._new2.text()
        if not old:
            QMessageBox.warning(self, "Validation", "Current password is required."); return
        if len(new) < 6:
            QMessageBox.warning(self, "Validation",
                "New password must be at least 6 characters."); return
        if new != new2:
            QMessageBox.warning(self, "Validation", "Passwords do not match."); return
        if change_password(self._username, old, new):
            QMessageBox.information(self, "Success", "Password changed successfully.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Current password is incorrect.")


# ══════════════════════════════════════════════════════════════════════════════
# User card — renders differently based on viewer's role
# ══════════════════════════════════════════════════════════════════════════════
_ROLE_COLORS = {
    "admin":  ("#1565C0", "#E3F2FD"),
    "user":   ("#2E7D32", "#E8F5E9"),
    "viewer": ("#6A1B9A", "#F3E5F5"),
}


class _UserCard(QFrame):
    def __init__(self, user: dict, viewer_role: str, viewer_username: str,
                 on_refresh, parent=None):
        super().__init__(parent)
        self._user            = user
        self._viewer_role     = viewer_role
        self._viewer_username = viewer_username
        self._refresh         = on_refresh
        self._is_self         = (user["username"].lower() == viewer_username.lower())
        self._is_admin_viewer = (viewer_role == "admin")

        # Highlight own card with a subtle left accent
        border_col = "#1565C040" if self._is_self else BORDER
        left_col   = "#1565C0"   if self._is_self else BORDER
        self.setStyleSheet(f"""
            QFrame {{
                background:{BG_CARD};
                border:1px solid {border_col};
                border-left:3px solid {left_col};
                border-radius:{RADIUS}px;
            }}
        """)
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(14)

        # Avatar
        initials = (self._user.get("display_name") or self._user["username"])[0].upper()
        av_color = "#1565C0" if self._is_self else PRIMARY
        av = QLabel(initials)
        av.setFixedSize(42, 42)
        av.setAlignment(Qt.AlignCenter)
        av.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        av.setStyleSheet(f"background:{av_color};color:white;border-radius:21px;")
        lay.addWidget(av)

        # Name + username
        info = QVBoxLayout(); info.setSpacing(2)
        info.addWidget(make_label(
            self._user.get("display_name") or self._user["username"],
            FONT_SIZE_SM, bold=True
        ))
        info.addWidget(make_label(
            f"@{self._user['username']}", FONT_SIZE_SM - 1, color=TEXT_SECONDARY
        ))
        lay.addLayout(info, 1)

        # "You" badge
        if self._is_self:
            you = QLabel("  You  ")
            you.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM - 1, QFont.Bold))
            you.setStyleSheet(
                "background:#1565C020;color:#1565C0;"
                "border:1px solid #1565C040;"
                "border-radius:8px;padding:2px 8px;font-size:8pt;"
            )
            lay.addWidget(you)

        # Role badge
        role = self._user.get("role", "user")
        fc, bc = _ROLE_COLORS.get(role, ("#333", "#eee"))
        role_lbl = QLabel(f"  {role}  ")
        role_lbl.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM - 1, QFont.Bold))
        role_lbl.setStyleSheet(
            f"background:{bc};color:{fc};border-radius:8px;padding:2px 6px;"
        )
        lay.addWidget(role_lbl)

        # Last login
        ll = self._user.get("last_login") or "Never"
        lay.addWidget(make_label(
            f"Last: {ll[:10]}", FONT_SIZE_SM - 1, color=TEXT_SECONDARY
        ))

        # Action buttons — gated by role
        def _btn(label, handler, danger=False):
            b = QPushButton(label)
            b.setFixedHeight(28)
            bg  = "rgba(239,68,68,0.10)" if danger else BG
            hov = "rgba(239,68,68,0.22)" if danger else BORDER
            col = "#EF4444"              if danger else TEXT_PRIMARY
            b.setStyleSheet(f"""
                QPushButton{{background:{bg};border:1px solid {BORDER};
                border-radius:6px;padding:0 10px;font-size:8pt;color:{col};}}
                QPushButton:hover{{background:{hov};}}
            """)
            b.clicked.connect(handler)
            return b

        if self._is_admin_viewer:
            # Admin: Edit | Reset PW | Delete
            lay.addWidget(_btn("✏ Edit", self._admin_edit))
            lay.addWidget(_btn("🔑 Reset PW", self._admin_reset_pw))
            del_btn = _btn("🗑 Delete", self._admin_delete, danger=True)
            # Disable delete if this is the last admin
            if role == "admin":
                conn = get_connection()
                n_admins = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role='admin'"
                ).fetchone()[0]
                if n_admins <= 1:
                    del_btn.setEnabled(False)
                    del_btn.setToolTip("Cannot delete the last administrator")
            lay.addWidget(del_btn)

        elif self._is_self:
            # Regular user: own card only gets Change Password
            lay.addWidget(_btn("🔑 Change Password", self._self_change_pw))
        # Non-self cards for non-admins: no buttons

    # ── Admin handlers ────────────────────────────────────────────────────────
    def _admin_edit(self):
        if _AdminUserDialog(self._user, parent=self).exec():
            self._refresh()

    def _admin_reset_pw(self):
        _AdminResetPasswordDialog(self._user, parent=self).exec()

    def _admin_delete(self):
        reply = QMessageBox.question(
            self, "Delete User",
            f"Delete user '{self._user['username']}'?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            ok, msg = _delete_user(self._user["id"])
            if not ok:
                QMessageBox.warning(self, "Cannot Delete", msg)
            else:
                self._refresh()

    # ── Self handler ──────────────────────────────────────────────────────────
    def _self_change_pw(self):
        _SelfChangePasswordDialog(self._user["username"], parent=self).exec()


# ══════════════════════════════════════════════════════════════════════════════
# Account Management main view
# ══════════════════════════════════════════════════════════════════════════════
class AccountView(QWidget):
    def __init__(self, current_user: dict | None = None, parent=None):
        super().__init__(parent)
        self._current_user = current_user or {}
        self._is_admin     = (self._current_user.get("role") == "admin")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = "Account Management" if self._is_admin else "My Account"
        hdr.addWidget(make_label(title, FONT_SIZE_LG, bold=True))
        hdr.addStretch()
        if self._is_admin:
            add_btn = QPushButton("＋ Add User")
            add_btn.setStyleSheet(BUTTON_PRIMARY_QSS)
            add_btn.setFixedHeight(34)
            add_btn.clicked.connect(self._add_user)
            hdr.addWidget(add_btn)
        lay.addLayout(hdr)

        # Subtitle
        sub = ("Manage all application users, roles, and passwords."
               if self._is_admin
               else "View your account details and change your password.")
        lay.addWidget(make_label(sub, FONT_SIZE_SM, color=TEXT_SECONDARY))

        # Info banner for non-admin users
        if not self._is_admin:
            banner = QLabel(
                "ℹ  You can view your own account and change your password. "
                "Contact an administrator to change your role or other settings."
            )
            banner.setWordWrap(True)
            banner.setFont(QFont(FONT_FAMILY, FONT_SIZE_SM - 1))
            banner.setStyleSheet(
                "color:#1565C0;background:#E3F2FD;"
                "border:1px solid #90CAF9;"
                "border-radius:6px;padding:8px 12px;"
            )
            lay.addWidget(banner)

        # Scrollable user list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        lay.addWidget(self._scroll)
        self.refresh()

    def refresh(self):
        viewer_role     = self._current_user.get("role", "user")
        viewer_username = self._current_user.get("username", "")

        # Admins see everyone; regular users see only themselves
        if self._is_admin:
            users = _all_users()
        else:
            users = [u for u in _all_users()
                     if u["username"].lower() == viewer_username.lower()]

        container = QWidget()
        vl = QVBoxLayout(container)
        vl.setSpacing(10); vl.setContentsMargins(0, 0, 0, 0)

        if not users:
            vl.addWidget(make_label(
                "No account information found.", FONT_SIZE_SM, color=TEXT_SECONDARY
            ))
        else:
            for u in users:
                vl.addWidget(_UserCard(
                    user=u,
                    viewer_role=viewer_role,
                    viewer_username=viewer_username,
                    on_refresh=self.refresh,
                    parent=container,
                ))

        # User count footer (admin only)
        if self._is_admin:
            total = len(_all_users())
            count_lbl = make_label(
                f"{total} user{'s' if total != 1 else ''} total",
                FONT_SIZE_SM - 1, color=TEXT_SECONDARY
            )
            count_lbl.setAlignment(Qt.AlignRight)
            vl.addWidget(count_lbl)

        vl.addStretch()
        self._scroll.setWidget(container)

    def _add_user(self):
        if _AdminUserDialog(parent=self).exec():
            self.refresh()
