"""Bong bóng Clipboard nổi khi người dùng Ctrl+C và tiện ích mở/dán nội dung."""
from __future__ import annotations

import math
import random
import shutil
import subprocess
import sys

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication

from pet.widgets.base import _AllSpacesWidget


class ClipboardBubble(_AllSpacesWidget):
    """Bong bóng xà phòng nổi mang biểu tượng nội dung vừa Ctrl+C."""

    BUBBLE_SIZE = 58

    def __init__(
        self,
        kind: str,  # "url" | "text" | "image"
        payload: str | QImage,
        start_x: float,
        start_y: float,
        on_activate,
        on_closed,
    ):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resize(self.BUBBLE_SIZE, self.BUBBLE_SIZE)

        self.kind = kind
        self.payload = payload
        self._on_activate = on_activate
        self._on_closed = on_closed

        if isinstance(payload, str):
            preview = payload.strip().replace("\n", " ")
            if len(preview) > 64:
                preview = preview[:61] + "..."
            tip = f"Mở liên kết: {preview}" if kind == "url" else f"Click để dán/chép lại: {preview}"
        else:
            tip = "Click để khôi phục ảnh vào Clipboard"
        self.setToolTip(tip + "\n(Chuột phải để xóa bong bóng)")

        self.bx = float(start_x)
        self.by = float(start_y)
        self.vx = random.uniform(-0.8, 0.8)
        self.vy = random.uniform(-1.3, -0.7)
        self.phase = random.uniform(0, math.tau)
        self.age = 0
        self.popping = False
        self.pop_progress = 0.0
        self.alive = True
        self.move(int(self.bx), int(self.by))
        self.show()

    def step(self, bounds: QRectF):
        if not self.alive:
            return
        self.age += 1

        if self.popping:
            self.pop_progress += 0.14
            if self.pop_progress >= 1.0:
                self.alive = False
                self.close()
                self._on_closed(self)
            else:
                self.update()
            return

        self.phase += 0.045
        self.vx *= 0.985
        self.vy = self.vy * 0.97 + (-0.06 if self.age < 55 else math.sin(self.phase * 0.7) * 0.025)
        self.bx += self.vx + math.sin(self.phase) * 0.35
        self.by += self.vy

        margin = 14
        if self.bx < bounds.left() + margin:
            self.bx = bounds.left() + margin
            self.vx = abs(self.vx) * 0.6 + 0.2
        elif self.bx + self.BUBBLE_SIZE > bounds.right() - margin:
            self.bx = bounds.right() - margin - self.BUBBLE_SIZE
            self.vx = -abs(self.vx) * 0.6 - 0.2

        if self.by < bounds.top() + margin:
            self.by = bounds.top() + margin
            self.vy = abs(self.vy) * 0.4 + 0.1
        elif self.by + self.BUBBLE_SIZE > bounds.bottom() - margin:
            self.by = bounds.bottom() - margin - self.BUBBLE_SIZE
            self.vy = -abs(self.vy) * 0.5 - 0.2

        self.move(int(self.bx), int(self.by))
        self.update()

    def trigger_pop(self, activate: bool = True):
        if self.popping:
            return
        self.popping = True
        self.pop_progress = 0.0
        if activate:
            self._on_activate(self)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.trigger_pop(activate=True)
        elif e.button() == Qt.MouseButton.RightButton:
            self.trigger_pop(activate=False)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.BUBBLE_SIZE / 2
        cy = self.BUBBLE_SIZE / 2

        if self.popping:
            prog = self.pop_progress
            alpha = max(0.0, 1.0 - prog)
            p.setOpacity(alpha)
            r_outer = 18 + prog * 12
            p.setPen(QPen(QColor("#a8e6ff"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(8):
                ang = i * (math.tau / 8.0)
                p.drawLine(
                    QPointF(cx + math.cos(ang) * (r_outer - 5), cy + math.sin(ang) * (r_outer - 5)),
                    QPointF(cx + math.cos(ang) * r_outer, cy + math.sin(ang) * r_outer),
                )
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#ffffff"))
            for i in range(6):
                ang = i * (math.tau / 6.0) + 0.3
                d = 12 + prog * 15
                p.drawEllipse(QPointF(cx + math.cos(ang) * d, cy + math.sin(ang) * d), 2.5, 2.5)
            return

        wobble_x = 1.0 + math.sin(self.phase * 1.4) * 0.04
        wobble_y = 1.0 - math.sin(self.phase * 1.4) * 0.04
        p.save()
        p.translate(cx, cy)
        p.scale(wobble_x, wobble_y)

        r = 23.0
        grad = QRadialGradient(QPointF(-7, -7), r * 1.5)
        grad.setColorAt(0.0, QColor(255, 255, 255, 215))
        grad.setColorAt(0.45, QColor(175, 232, 255, 130))
        grad.setColorAt(0.82, QColor(195, 210, 255, 145))
        grad.setColorAt(1.0, QColor(255, 200, 230, 195))

        p.setPen(QPen(QColor(110, 195, 240, 220), 2.0))
        p.setBrush(grad)
        p.drawEllipse(QPointF(0, 0), r, r)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 220))
        p.drawEllipse(QRectF(-13, -15, 10, 6))
        p.drawEllipse(QRectF(-15, -7, 4, 4))

        self._draw_content_icon(p)
        p.restore()

    def _draw_content_icon(self, p: QPainter):
        ink = QColor("#2c3e50")
        if self.kind == "url":
            p.setPen(QPen(QColor("#1d6fe2"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.save()
            p.rotate(-35)
            p.drawRoundedRect(QRectF(-10, -4, 11, 8), 4, 4)
            p.drawRoundedRect(QRectF(-1, -4, 11, 8), 4, 4)
            p.restore()
        elif self.kind == "image":
            p.setPen(QPen(ink, 1.8))
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawRoundedRect(QRectF(-9, -7, 18, 14), 2.5, 2.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#52b788"))
            p.drawPolygon(QPolygonF([QPointF(-7, 5), QPointF(-2, -1), QPointF(3, 5)]))
            p.setBrush(QColor("#ffd166"))
            p.drawEllipse(QPointF(4, -3), 2.2, 2.2)
        else:
            p.setPen(QPen(ink, 1.8))
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawRoundedRect(QRectF(-8, -9, 16, 18), 2.5, 2.5)
            p.setPen(QPen(QColor("#3b5bdb"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(-5, -4), QPointF(5, -4))
            p.drawLine(QPointF(-5, 0), QPointF(5, 0))
            p.drawLine(QPointF(-5, 4), QPointF(2, 4))


def paste_or_open_clipboard_payload(kind: str, payload: str | QImage) -> None:
    """Mở URL ngay hoặc khôi phục clipboard và thử gửi Ctrl+V (không cướp focus)."""
    if kind == "url" and isinstance(payload, str):
        QDesktopServices.openUrl(QUrl(payload.strip()))
        return

    cb = QApplication.clipboard()
    if isinstance(payload, QImage):
        cb.setImage(payload)
    else:
        cb.setText(payload)

    if sys.platform.startswith("linux") and shutil.which("xdotool"):
        QTimer.singleShot(
            90,
            lambda: subprocess.Popen(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ),
        )


