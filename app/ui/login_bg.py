"""
login_bg.py — Animated gradient-orb background for the login screen.

Uses QPainter with QTimer to animate 4 soft radial-gradient orbs that
drift slowly across a deep-navy canvas.  GPU-free, fully smooth at 60 fps
on any modern desktop.
"""
from __future__ import annotations
import math

from PySide6.QtWidgets import QWidget
from PySide6.QtCore    import Qt, QTimer, QPointF
from PySide6.QtGui     import QPainter, QRadialGradient, QColor, QLinearGradient


# Orb descriptors: (cx_frac, cy_frac, r_frac, hex_color, speed_x, speed_y)
_ORBS = [
    (0.15, 0.25, 0.55, "#1A3C6E", +0.00012, +0.00007),
    (0.80, 0.20, 0.50, "#0E2A52", -0.00008, +0.00010),
    (0.60, 0.80, 0.60, "#132B55", +0.00010, -0.00009),
    (0.30, 0.70, 0.45, "#0A1E3D", -0.00011, -0.00006),
]


class AnimatedBackground(QWidget):
    """Full-size widget painted with drifting radial-gradient orbs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self._t = 0.0          # animation tick
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 fps

    def _tick(self) -> None:
        self._t += 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Base canvas — very dark navy
        p.fillRect(0, 0, w, h, QColor("#060E1C"))

        t = self._t
        for cx_f, cy_f, r_f, color, sx, sy in _ORBS:
            # Drift using sine/cosine so the orbs never leave the canvas
            cx = (cx_f + sx * t) % 1.0
            cy = (cy_f + sy * t) % 1.0
            px = cx * w
            py = cy * h
            r  = r_f * max(w, h)

            grad = QRadialGradient(QPointF(px, py), r)
            c = QColor(color)
            c.setAlpha(180)
            grad.setColorAt(0.0, c)
            c2 = QColor(color)
            c2.setAlpha(0)
            grad.setColorAt(1.0, c2)
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(px, py), r, r)

        # Subtle grid overlay for depth
        pen_color = QColor(255, 255, 255, 6)
        p.setPen(pen_color)
        grid = 48
        for x in range(0, w + grid, grid):
            p.drawLine(x, 0, x, h)
        for y in range(0, h + grid, grid):
            p.drawLine(0, y, w, y)

        # Bottom vignette
        vign = QLinearGradient(0, h * 0.6, 0, h)
        vign.setColorAt(0.0, QColor(0, 0, 0, 0))
        vign.setColorAt(1.0, QColor(0, 0, 0, 80))
        p.setBrush(vign)
        p.setPen(Qt.NoPen)
        p.drawRect(0, int(h * 0.6), w, h)

        p.end()

    def stop(self) -> None:
        self._timer.stop()
