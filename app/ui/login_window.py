"""
login_window.py — Production-grade animated login screen for PMO Suite.

Architecture
────────────
LoginWindow          QMainWindow shell — hosts background + card
  AnimatedBackground   drifting orb canvas (login_bg.py)
  LoginCard            glassmorphism form card
    LogoSection          animated logo + title
    FieldRow             icon + QLineEdit with focus glow
    PasswordRow          icon + masked input + show/hide toggle
    ActionRow            "Remember me" checkbox + login button
    StatusRow            error/loading feedback

Animations (all QPropertyAnimation — zero third-party deps)
──────────────────────────────────────────────────────────
• Entrance    : card slides up 40px + fades in over 600 ms (OutCubic)
• Logo pulse  : logo icon scales 1.0→1.05→1.0 on load (InOutSine)
• Input focus : blue border glow via QSS property animation wrapper
• Button hover: handled via QSS (instant, no stutter)
• Button press: quick scale 0.97 via QPropertyAnimation on geometry
• Spinner     : 12-dot arc redrawn every 80 ms via QTimer + QPainter
• Shake        : card moves ±8px horizontally × 5 cycles (OutElastic)
• Transition   : card fades out → main window fades in (QGraphicsOpacityEffect)
"""
from __future__ import annotations

import os
import math
from typing import Callable

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QSequentialAnimationGroup,
    QParallelAnimationGroup, QEasingCurve, QRect, QPoint, QSize
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QIcon, QPixmap, QPainterPath
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QCheckBox, QFrame, QSizePolicy,
    QGraphicsOpacityEffect
)

from app.ui.login_bg import AnimatedBackground
from app.models.auth_model import validate_login, get_user
from app.utils.theme import FONT_FAMILY

# ── Design tokens (dark-mode login palette) ───────────────────────────────────
_C_SURFACE   = "rgba(12, 22, 42, 0.72)"   # glassmorphism card fill
_C_BORDER    = "rgba(255, 255, 255, 0.10)"
_C_BORDER_F  = "#3B82F6"                   # focused input border
_C_TEXT      = "#E8EEF4"
_C_MUTED     = "#7A92A8"
_C_ACCENT    = "#3B82F6"                   # electric blue
_C_ACCENT_H  = "#2563EB"
_C_ERROR     = "#EF4444"
_C_SUCCESS   = "#22C55E"
_RADIUS      = 20
_CARD_W      = 440
_CARD_H      = 560


# ══════════════════════════════════════════════════════════════════════════════
# Spinner widget — arc drawn with QPainter, rotated via QTimer
# ══════════════════════════════════════════════════════════════════════════════
class _Spinner(QWidget):
    _DOT_COUNT = 10
    _RADIUS    = 12
    _DOT_R     = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        size = (self._RADIUS + self._DOT_R + 2) * 2
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.hide()

    def start(self) -> None:
        self._angle = 0
        self.show()
        self._timer.start(80)

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def _rotate(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx = self.width()  / 2
        cy = self.height() / 2
        for i in range(self._DOT_COUNT):
            angle_deg = (i * 360 / self._DOT_COUNT + self._angle) % 360
            alpha     = int(255 * ((i + 1) / self._DOT_COUNT) ** 1.6)
            angle_rad = math.radians(angle_deg)
            dx = self._RADIUS * math.cos(angle_rad)
            dy = self._RADIUS * math.sin(angle_rad)
            color = QColor("#3B82F6"); color.setAlpha(alpha)
            p.setBrush(QBrush(color)); p.setPen(Qt.NoPen)
            p.drawEllipse(
                QPoint(int(cx + dx), int(cy + dy)),
                self._DOT_R, self._DOT_R
            )
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# Glassmorphism card — painted background (backdrop blur simulated with opacity)
# ══════════════════════════════════════════════════════════════════════════════
class _GlassCard(QFrame):
    """QFrame subclass that paints a dark glass panel.

    Shadow is painted manually inside paintEvent — no QGraphicsEffect is used
    because Qt cannot run a custom paintEvent and a graphics effect on the same
    widget simultaneously (causes the 'Painter not active' loop).
    """

    _SHADOW_BLUR   = 24   # px of soft shadow spread
    _SHADOW_OFFSET = 12   # px downward offset

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Reserve room for the shadow so the card content stays centred
        total_w = _CARD_W + self._SHADOW_BLUR * 2
        total_h = _CARD_H + self._SHADOW_BLUR + self._SHADOW_OFFSET
        self.setFixedSize(total_w, total_h)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")

    # Content rect (excludes shadow margin)
    def _card_rect(self):
        b = self._SHADOW_BLUR
        return QRect(b, b, _CARD_W, _CARD_H)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cr = self._card_rect()

        # ── Layered soft shadow (paint multiple translucent rects) ──────
        for i in range(self._SHADOW_BLUR, 0, -1):
            alpha  = max(1, int(90 * (1 - i / self._SHADOW_BLUR) ** 1.8))
            expand = self._SHADOW_BLUR - i
            sr = QRect(
                cr.x()      - expand,
                cr.y()      - expand + self._SHADOW_OFFSET,
                cr.width()  + expand * 2,
                cr.height() + expand * 2,
            )
            sc = QColor(0, 0, 0, alpha)
            p.setBrush(sc); p.setPen(Qt.NoPen)
            p.drawRoundedRect(sr, _RADIUS + expand * 0.4, _RADIUS + expand * 0.4)

        # ── Card fill ────────────────────────────────────────────────────
        card_path = QPainterPath()
        card_path.addRoundedRect(
            cr.x(), cr.y(), cr.width(), cr.height(), _RADIUS, _RADIUS
        )
        p.setClipPath(card_path)
        p.fillPath(card_path, QColor(10, 18, 36, 218))

        # ── Top highlight stripe ─────────────────────────────────────────
        hi = QLinearGradient(0, cr.y(), 0, cr.y() + 3)
        hi.setColorAt(0.0, QColor(255, 255, 255, 50))
        hi.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(cr.x(), cr.y(), cr.width(), 3, hi)

        # ── Border ───────────────────────────────────────────────────────
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(
            cr.x() + 1, cr.y() + 1,
            cr.width() - 2, cr.height() - 2,
            _RADIUS, _RADIUS
        )
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# Animated text input row (icon + field)
# ══════════════════════════════════════════════════════════════════════════════
_INPUT_BASE = """
QLineEdit {{
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    color: #E8EEF4;
    font-family: {ff};
    font-size: 10pt;
    padding: 0 42px 0 40px;
    selection-background-color: #3B82F6;
}}
QLineEdit:focus {{
    border: 1.5px solid #3B82F6;
    background: rgba(59,130,246,0.08);
}}
QLineEdit::placeholder {{
    color: #4A6478;
}}
"""

_TOGGLE_QSS = """
QPushButton {
    background: transparent;
    border: none;
    color: #4A6478;
    font-size: 14px;
    padding: 0;
}
QPushButton:hover { color: #7A92A8; }
"""


class _IconInput(QWidget):
    """Input field with left icon, optional right toggle, focus animation."""

    def __init__(self, placeholder: str, icon: str,
                 password: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)

        # Outer wrapper for glow effect
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        # Container holds icon + field + toggle
        container = QWidget(self)
        container.setFixedHeight(52)
        c_lay = QHBoxLayout(container)
        c_lay.setContentsMargins(0, 0, 0, 0); c_lay.setSpacing(0)
        lay.addWidget(container)

        # Left icon
        icon_lbl = QLabel(icon, container)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedWidth(40)
        icon_lbl.setFont(QFont(FONT_FAMILY, 13))
        icon_lbl.setStyleSheet("color:#4A6478; background:transparent;")
        icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)

        # Field
        self.field = QLineEdit(container)
        self.field.setPlaceholderText(placeholder)
        self.field.setFixedHeight(52)
        self.field.setStyleSheet(_INPUT_BASE.format(ff=FONT_FAMILY))
        if password:
            self.field.setEchoMode(QLineEdit.Password)

        c_lay.addWidget(self.field)

        # Position icon absolutely over field
        icon_lbl.raise_()
        icon_lbl.setGeometry(0, 0, 40, 52)

        # Show/hide toggle for password
        self._toggle: QPushButton | None = None
        if password:
            self._toggle = QPushButton("👁", container)
            self._toggle.setFixedSize(36, 52)
            self._toggle.setStyleSheet(_TOGGLE_QSS)
            self._toggle.setCursor(Qt.PointingHandCursor)
            self._toggle.clicked.connect(self._toggle_visibility)
            # Position right
            self._toggle.setGeometry(_CARD_W - 36 - 2, 0, 36, 52)
            self._toggle.raise_()
            self._is_visible = False

        # Focus glow via opacity animation stub
        self.field.installEventFilter(self)

    def eventFilter(self, obj, event):  # noqa: N802
        return False  # let QSS :focus handle the glow

    def _toggle_visibility(self) -> None:
        self._is_visible = not self._is_visible
        self.field.setEchoMode(
            QLineEdit.Normal if self._is_visible else QLineEdit.Password
        )
        self._toggle.setText("🙈" if self._is_visible else "👁")

    def text(self) -> str:
        return self.field.text()

    def clear(self) -> None:
        self.field.clear()

    def setFocus(self) -> None:  # noqa: N802
        self.field.setFocus()


# ══════════════════════════════════════════════════════════════════════════════
# Login button with press-scale animation
# ══════════════════════════════════════════════════════════════════════════════
_BTN_QSS = f"""
QPushButton {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #2563EB, stop:1 #3B82F6);
    color: white;
    border: none;
    border-radius: 12px;
    font-family: {FONT_FAMILY};
    font-size: 11pt;
    font-weight: bold;
    letter-spacing: 0.5px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #1D4ED8, stop:1 #2563EB);
}}
QPushButton:disabled {{
    background: rgba(59,130,246,0.3);
    color: rgba(255,255,255,0.4);
}}
"""


class _LoginButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFixedHeight(52)
        self.setStyleSheet(_BTN_QSS)
        self.setCursor(Qt.PointingHandCursor)
        self._press_anim: QPropertyAnimation | None = None

    def mousePressEvent(self, event):  # noqa: N802
        # Quick shrink on press
        r = self.geometry()
        self._press_anim = QPropertyAnimation(self, b"geometry", self)
        shrunk = r.adjusted(4, 2, -4, -2)
        self._press_anim.setDuration(80)
        self._press_anim.setStartValue(r)
        self._press_anim.setEndValue(shrunk)
        self._press_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._press_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        r = self.geometry()
        restored = r.adjusted(-4, -2, 4, 2)
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(120)
        anim.setStartValue(r)
        anim.setEndValue(restored)
        anim.setEasingCurve(QEasingCurve.OutBack)
        anim.start()
        super().mouseReleaseEvent(event)


# ══════════════════════════════════════════════════════════════════════════════
# The full login card
# ══════════════════════════════════════════════════════════════════════════════
class LoginCard(_GlassCard):
    """Glassmorphism login form with all animations."""

    # Signal-less callback approach to stay decoupled
    login_success_callback: Callable[[dict], None] | None = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._debounce_active = False
        self._remember = False
        self._build()

    # ── UI construction ────────────────────────────────────────────────────
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        b = self._SHADOW_BLUR   # offset content into the card rect
        lay.setContentsMargins(b + 44, b + 44, b + 44, b + 44)
        lay.setSpacing(0)

        # ── Logo + title ───────────────────────────────────────────────────
        logo_row = QHBoxLayout()
        logo_row.setAlignment(Qt.AlignCenter)

        self._logo_lbl = QLabel("◈")
        self._logo_lbl.setFont(QFont(FONT_FAMILY, 36, QFont.Bold))
        self._logo_lbl.setStyleSheet("color:#3B82F6; background:transparent;")
        self._logo_lbl.setAlignment(Qt.AlignCenter)
        logo_row.addWidget(self._logo_lbl)
        lay.addLayout(logo_row)
        lay.addSpacing(16)

        title = QLabel("PMO Suite")
        title.setFont(QFont(FONT_FAMILY, 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:#E8EEF4; background:transparent; letter-spacing:1px;")
        lay.addWidget(title)

        subtitle = QLabel("Portfolio Management Platform")
        subtitle.setFont(QFont(FONT_FAMILY, 9))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color:#4A6478; background:transparent; letter-spacing:2px;")
        lay.addWidget(subtitle)

        lay.addSpacing(36)

        # ── Divider ────────────────────────────────────────────────────────
        div = QFrame(); div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background:rgba(255,255,255,0.07); max-height:1px;")
        lay.addWidget(div)
        lay.addSpacing(28)

        # ── Username ───────────────────────────────────────────────────────
        self._user_field = _IconInput("Username", "👤")
        lay.addWidget(self._user_field)
        lay.addSpacing(14)

        # ── Password ───────────────────────────────────────────────────────
        self._pass_field = _IconInput("Password", "🔑", password=True)
        lay.addWidget(self._pass_field)
        lay.addSpacing(16)

        # ── Remember me ────────────────────────────────────────────────────
        rem_row = QHBoxLayout()
        self._rem_chk = QCheckBox("Remember me")
        self._rem_chk.setFont(QFont(FONT_FAMILY, 9))
        self._rem_chk.setStyleSheet(f"""
            QCheckBox {{
                color: #7A92A8;
                background: transparent;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 4px;
                background: rgba(255,255,255,0.04);
            }}
            QCheckBox::indicator:checked {{
                background: #3B82F6;
                border-color: #3B82F6;
            }}
        """)
        rem_row.addWidget(self._rem_chk)
        rem_row.addStretch()
        lay.addLayout(rem_row)
        lay.addSpacing(24)

        # ── Login button + spinner row ─────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(12)
        self._login_btn = _LoginButton("Sign In")
        self._login_btn.clicked.connect(self._on_login_clicked)
        btn_row.addWidget(self._login_btn, 1)

        self._spinner = _Spinner()
        btn_row.addWidget(self._spinner)
        lay.addLayout(btn_row)
        lay.addSpacing(20)

        # ── Status message ─────────────────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setFont(QFont(FONT_FAMILY, 9))
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setFixedHeight(36)
        self._status_lbl.setStyleSheet(
            "background: transparent; border-radius: 8px; padding: 4px 8px;"
        )
        lay.addWidget(self._status_lbl)

        lay.addStretch()

        # ── Footer ─────────────────────────────────────────────────────────
        footer = QLabel("Orhan Automotive  ·  v2.1")
        footer.setFont(QFont(FONT_FAMILY, 7))
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color:#243344; background:transparent;")
        lay.addWidget(footer)

        # Enter key binding
        self._user_field.field.returnPressed.connect(self._on_login_clicked)
        self._pass_field.field.returnPressed.connect(self._on_login_clicked)

    # ── Login logic ────────────────────────────────────────────────────────
    def _on_login_clicked(self) -> None:
        if self._debounce_active:
            return
        self._clear_status()

        username = self._user_field.text().strip()
        password = self._pass_field.text()

        # ── Validation ────────────────────────────────────────────────────
        if not username:
            self._show_error("Username cannot be empty.")
            self._user_field.setFocus()
            return
        if not password:
            self._show_error("Password cannot be empty.")
            self._pass_field.setFocus()
            return

        # ── Begin processing ──────────────────────────────────────────────
        self._debounce_active = True
        self._login_btn.setEnabled(False)
        self._login_btn.setText("Signing in…")
        self._spinner.start()

        # Defer actual auth 600 ms — lets spinner render at least one frame
        QTimer.singleShot(600, lambda: self._do_auth(username, password))

    def _do_auth(self, username: str, password: str) -> None:
        ok = validate_login(username, password)
        self._spinner.stop()
        self._login_btn.setEnabled(True)
        self._login_btn.setText("Sign In")
        self._debounce_active = False

        if ok:
            user = get_user(username)
            self._show_success(f"Welcome back, {user.get('display_name', username)}!")
            # Short pause then hand off
            QTimer.singleShot(500, lambda: self._emit_success(user))
        else:
            self._show_error("Incorrect username or password.")
            self._shake()
            self._pass_field.clear()
            self._pass_field.setFocus()

    def _emit_success(self, user: dict) -> None:
        if self.login_success_callback:
            self.login_success_callback(user)

    # ── Status helpers ─────────────────────────────────────────────────────
    def _clear_status(self) -> None:
        self._status_lbl.setText("")
        self._status_lbl.setStyleSheet(
            "background: transparent; border-radius: 8px;"
        )

    def _show_error(self, msg: str) -> None:
        self._status_lbl.setText(f"⚠  {msg}")
        self._status_lbl.setStyleSheet(
            "color:#EF4444; background:rgba(239,68,68,0.10); "
            "border:1px solid rgba(239,68,68,0.25); "
            "border-radius:8px; padding:4px 8px;"
        )

    def _show_success(self, msg: str) -> None:
        self._status_lbl.setText(f"✓  {msg}")
        self._status_lbl.setStyleSheet(
            "color:#22C55E; background:rgba(34,197,94,0.10); "
            "border:1px solid rgba(34,197,94,0.25); "
            "border-radius:8px; padding:4px 8px;"
        )

    # ── Shake animation (error feedback) ──────────────────────────────────
    def _shake(self) -> None:
        """Horizontal shake: card moves ±8px × 5 cycles in 400 ms."""
        orig = self.pos()
        seq  = QSequentialAnimationGroup(self)
        offsets = [8, -8, 6, -6, 4, -4, 2, -2, 0]
        for dx in offsets:
            a = QPropertyAnimation(self, b"pos", seq)
            a.setDuration(40)
            a.setStartValue(orig)
            a.setEndValue(QPoint(orig.x() + dx, orig.y()))
            a.setEasingCurve(QEasingCurve.OutCubic)
            seq.addAnimation(a)
        seq.start(QSequentialAnimationGroup.DeleteWhenStopped)


# ══════════════════════════════════════════════════════════════════════════════
# Login window — QMainWindow that hosts background + card + entrance animation
# ══════════════════════════════════════════════════════════════════════════════
class LoginWindow(QMainWindow):
    """Full-screen login shell.

    Call ``set_success_callback(fn)`` to be notified on successful login.
    ``fn`` receives a user dict: {id, username, role, display_name}.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PMO Suite — Sign In")
        self.setMinimumSize(900, 600)
        self.resize(1200, 750)
        self._success_callback: Callable[[dict], None] | None = None
        self._build()

    def set_success_callback(self, fn: Callable[[dict], None]) -> None:
        self._success_callback = fn
        self._card.login_success_callback = self._on_login_success

    # ── UI ─────────────────────────────────────────────────────────────────
    def _build(self) -> None:
        root = QWidget()
        root.setAttribute(Qt.WA_TranslucentBackground)
        self.setCentralWidget(root)

        # Stack: background then card on top
        self._bg = AnimatedBackground(root)
        self._bg.setGeometry(0, 0, self.width(), self.height())

        # Card container — centred
        self._card_container = QWidget(root)
        self._card_container.setAttribute(Qt.WA_TranslucentBackground)
        # Size is set dynamically in _centre_card after card is built

        self._card = LoginCard(self._card_container)
        self._card.move(0, 0)

        # Opacity effect for entrance / exit fade
        self._opacity_fx = QGraphicsOpacityEffect(self._card_container)
        self._opacity_fx.setOpacity(0.0)
        self._card_container.setGraphicsEffect(self._opacity_fx)

        # Position card once window is visible
        QTimer.singleShot(0, self._centre_card)
        # Entrance animation after a short delay
        QTimer.singleShot(80, self._play_entrance)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._bg.setGeometry(0, 0, self.width(), self.height())
        self._centre_card()

    def _centre_card(self) -> None:
        cw = self._card.width()
        ch = self._card.height()
        cx = (self.width()  - cw) // 2
        cy = (self.height() - ch) // 2
        self._card_container.move(cx, cy)
        self._card_container.setFixedSize(cw, ch)

    # ── Entrance animation: fade-in + slide-up ─────────────────────────────
    def _play_entrance(self) -> None:
        """Card slides up 40px and fades in over 650 ms."""
        container  = self._card_container
        start_pos  = QPoint(container.x(), container.y() + 40)
        end_pos    = QPoint(container.x(), container.y())

        group = QParallelAnimationGroup(self)

        # Fade in
        fade = QPropertyAnimation(self._opacity_fx, b"opacity", group)
        fade.setDuration(650)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        group.addAnimation(fade)

        # Slide up
        slide = QPropertyAnimation(container, b"pos", group)
        slide.setDuration(650)
        slide.setStartValue(start_pos)
        slide.setEndValue(end_pos)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        group.addAnimation(slide)

        group.start(QParallelAnimationGroup.DeleteWhenStopped)

        # Logo pulse after entrance completes
        QTimer.singleShot(700, self._pulse_logo)

    # ── Logo pulse (scale 1.0 → 1.08 → 1.0) ──────────────────────────────
    def _pulse_logo(self) -> None:
        """Subtle font-size bounce to draw attention to the logo."""
        lbl  = self._card._logo_lbl
        orig = lbl.font().pointSize()   # 36

        def _set(size: float) -> None:
            f = lbl.font()
            f.setPointSizeF(size)
            lbl.setFont(f)

        steps  = [36, 38, 40, 39, 38, 36]
        delays = [0,  60, 120, 180, 240, 300]
        for delay, size in zip(delays, steps):
            QTimer.singleShot(delay, lambda s=size: _set(s))

    # ── Success → fade out then launch main window ─────────────────────────
    def _on_login_success(self, user: dict) -> None:
        """Fade the login card out, then call success callback."""
        fade_out = QPropertyAnimation(self._opacity_fx, b"opacity", self)
        fade_out.setDuration(400)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InCubic)
        fade_out.finished.connect(lambda: self._launch(user))
        fade_out.start()

    def _launch(self, user: dict) -> None:
        self._bg.stop()
        if self._success_callback:
            self._success_callback(user)
        self.close()
