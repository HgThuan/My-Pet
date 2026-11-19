"""Các widget vệ tinh cho Desktop Pet Cá Vàng.

- ClipboardBubble: Bong bóng nổi chứa dữ liệu Ctrl+C (văn bản / link / ảnh), click để "bụp" & mở/dán.
- WaterOverlay: Lớp hiệu ứng mực nước dâng (Pomodoro Focus / Break), hoàn toàn xuyên chuột.
- FishFood: Viên cám cá, tép khô, mảnh cám, HOẶC Ký tự / Từ khóa / Emoji rơi từ đỉnh màn hình xuống.
- PongBubble: Quả bóng bong bóng cho trò chơi "Bóng bàn Bong Bóng" (Bubble Pong) tâng qua lại với cá.
- SplashRippleOverlay: Hiệu ứng gợn sóng nước tung tóe khi cá lặn tòm ẩn mình (Boss Key) hoặc ngoi lên.
"""
from __future__ import annotations

import math
import random
import re
import shutil
import subprocess
import sys

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QWidget

URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)

WORD_FOOD_COLORS = [
    ("#ffe066", "#3b182c"),
    ("#74c0fc", "#183153"),
    ("#ffa8a8", "#4a192c"),
    ("#8ce99a", "#1b4332"),
    ("#d0bfff", "#2b1d4c"),
    ("#ffc078", "#4a2511"),
]

DEFAULT_WORD_TOKENS = [
    "def", "λ", "{ }", "git", "BUG", "404", "OK", "01", "✨", "⚡", "♥", "★", "API", "SQL",
]


class ClipboardBubble(QWidget):
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


class PongBubble(QWidget):
    """Quả bóng bong bóng cho trò chơi Bóng bàn Bong Bóng (Bubble Pong)."""

    BUBBLE_SIZE = 62

    def __init__(self, start_x: float, start_y: float, on_player_hit, on_closed):
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
        self.setToolTip("Nhấp đúp (hoặc vung chuột) để hất bong bóng chơi với cá!\n(Chuột phải để đóng trò chơi)")

        self._on_player_hit = on_player_hit
        self._on_closed = on_closed

        self.bx = float(start_x)
        self.by = float(start_y)
        self.vx = random.uniform(-0.6, 0.6)
        self.vy = -0.6
        self.phase = random.uniform(0, math.tau)
        self.squash_x = 1.0
        self.squash_y = 1.0

        self.in_rally = False
        self.last_hitter = ""  # "player" | "fish" | ""
        self.rally_count = 0
        self.hit_cooldown = 0
        self.popping = False
        self.pop_progress = 0.0
        self.alive = True
        self._font = QFont("Sans Serif", 12, QFont.Weight.Black)

        self.move(int(self.bx), int(self.by))
        self.show()

    def center(self) -> tuple[float, float]:
        return self.bx + self.BUBBLE_SIZE / 2.0, self.by + self.BUBBLE_SIZE / 2.0

    def launch(self, vx: float, vy: float, hitter: str):
        self.vx = vx
        self.vy = vy
        self.in_rally = True
        self.last_hitter = hitter
        self.hit_cooldown = 16
        self.squash_x = 1.30 if abs(vx) >= abs(vy) else 0.78
        self.squash_y = 0.78 if abs(vx) >= abs(vy) else 1.30
        if hitter == "fish":
            self.rally_count += 1

    def step(self, bounds: QRectF):
        if not self.alive:
            return
        if self.hit_cooldown > 0:
            self.hit_cooldown -= 1

        if self.popping:
            self.pop_progress += 0.14
            if self.pop_progress >= 1.0:
                self.alive = False
                self.close()
                self._on_closed(self)
            else:
                self.update()
            return

        self.phase += 0.07
        self.squash_x += (1.0 - self.squash_x) * 0.16
        self.squash_y += (1.0 - self.squash_y) * 0.16

        if self.in_rally:
            # Chuyển động mượt có lực cản không khí cực nhẹ
            self.vx *= 0.992
            self.vy *= 0.992
            if math.hypot(self.vx, self.vy) < 1.0:
                self.in_rally = False
                self.last_hitter = ""
        else:
            # Lơ lửng nhẹ chờ người chơi nhấp đúp hất đi
            self.vx *= 0.96
            self.vy = self.vy * 0.96 + math.sin(self.phase) * 0.04

        self.bx += self.vx
        self.by += self.vy

        # Nảy đàn hồi ở các mép màn hình
        margin = 10.0
        if self.bx < bounds.left() + margin:
            self.bx = bounds.left() + margin
            self.vx = abs(self.vx) * 0.88 + 0.5
            self.squash_x, self.squash_y = 0.75, 1.28
        elif self.bx + self.BUBBLE_SIZE > bounds.right() - margin:
            self.bx = bounds.right() - margin - self.BUBBLE_SIZE
            self.vx = -abs(self.vx) * 0.88 - 0.5
            self.squash_x, self.squash_y = 0.75, 1.28

        if self.by < bounds.top() + margin:
            self.by = bounds.top() + margin
            self.vy = abs(self.vy) * 0.88 + 0.4
            self.squash_x, self.squash_y = 1.28, 0.75
        elif self.by + self.BUBBLE_SIZE > bounds.bottom() - margin:
            self.by = bounds.bottom() - margin - self.BUBBLE_SIZE
            self.vy = -abs(self.vy) * 0.88 - 0.4
            self.squash_x, self.squash_y = 1.28, 0.75

        self.move(int(self.bx), int(self.by))
        self.update()

    def close_with_pop(self):
        if not self.popping:
            self.popping = True
            self.pop_progress = 0.0

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._on_player_hit(self, e.globalPosition().toPoint())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self.close_with_pop()
        elif e.button() == Qt.MouseButton.LeftButton and self.in_rally:
            # Khi đang trong lượt tâng bóng, click đơn cũng đánh trả được ngay!
            self._on_player_hit(self, e.globalPosition().toPoint())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.BUBBLE_SIZE / 2.0
        cy = self.BUBBLE_SIZE / 2.0

        if self.popping:
            prog = self.pop_progress
            p.setOpacity(max(0.0, 1.0 - prog))
            r = 22.0 + prog * 14.0
            p.setPen(QPen(QColor("#72efdd"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(8):
                ang = i * (math.tau / 8.0)
                p.drawLine(
                    QPointF(cx + math.cos(ang) * (r - 6), cy + math.sin(ang) * (r - 6)),
                    QPointF(cx + math.cos(ang) * r, cy + math.sin(ang) * r),
                )
            return

        p.save()
        p.translate(cx, cy)
        p.scale(self.squash_x, self.squash_y)

        r = 24.0
        grad = QRadialGradient(QPointF(-8, -8), r * 1.55)
        grad.setColorAt(0.0, QColor(255, 255, 255, 235))
        grad.setColorAt(0.45, QColor(120, 240, 255, 155))
        grad.setColorAt(0.80, QColor(168, 200, 255, 165))
        grad.setColorAt(1.0, QColor(255, 175, 225, 220))

        rim_col = QColor("#ffbe0b") if self.in_rally else QColor(85, 205, 245, 235)
        p.setPen(QPen(rim_col, 2.5))
        p.setBrush(grad)
        p.drawEllipse(QPointF(0, 0), r, r)

        # Vệt sáng cầu vồng
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawEllipse(QRectF(-13, -15, 10, 6))
        p.drawEllipse(QRectF(-15, -7, 4, 4))

        # Hiển thị điểm tâng bóng khi đang rally
        if self.rally_count > 0:
            p.setFont(self._font)
            p.setPen(QColor("#2b2d42"))
            p.drawText(QRectF(-18, -14, 36, 28), Qt.AlignmentFlag.AlignCenter, str(self.rally_count))
        p.restore()


class SplashRippleOverlay(QWidget):
    """Hiệu ứng gợn sóng nước tung tóe ở mép dưới khi cá lặn ẩn mình (Boss Key) / ngoi lên."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.resize(260, 120)

        self._progress = 1.0
        self._drops: list[list[float]] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def trigger_at(self, center_x: float, bottom_y: float):
        self.move(int(center_x - self.width() / 2), int(bottom_y - self.height() + 10))
        self._progress = 0.0
        self._drops = [
            [self.width() / 2.0 + random.uniform(-22, 22), self.height() - 18.0,
             random.uniform(-3.8, 3.8), random.uniform(-7.2, -3.4), random.uniform(4.0, 8.0)]
            for _ in range(12)
        ]
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start(16)
        self.update()

    def _tick(self):
        self._progress += 0.032
        for d in self._drops:
            d[0] += d[2]
            d[1] += d[3]
            d[3] += 0.34
        if self._progress >= 1.0:
            self._timer.stop()
            self.hide()
        else:
            self.update()

    def paintEvent(self, _):
        if self._progress >= 1.0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        prog = self._progress
        alpha = max(0.0, 1.0 - prog)
        cx = self.width() / 2.0
        cy = self.height() - 18.0

        # 3 vòng gợn sóng đồng tâm lan rộng
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(3):
            rp = max(0.0, min(1.0, prog * 1.25 - i * 0.16))
            if rp <= 0.0:
                continue
            a = int(220 * (1.0 - rp) * alpha)
            rx = 18.0 + rp * 98.0
            ry = 6.0 + rp * 18.0
            p.setPen(QPen(QColor(115, 225, 255, max(0, a)), 3.2 - rp * 1.6))
            p.drawEllipse(QPointF(cx, cy), rx, ry)

        # Các giọt nước bắn tung lên
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(175, 240, 255, int(230 * alpha)))
        for x, y, _, _, r in self._drops:
            if y < self.height():
                p.drawEllipse(QPointF(x, y), r * (1.0 - prog * 0.4), r * (1.0 - prog * 0.4))


class WaterOverlay(QWidget):
    """Lớp nước trong suốt dâng lên/rút xuống cho Pomodoro Tập Trung (xuyên chuột)."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)

        self.active = False
        self.phase = "idle"
        self.focus_secs = 25 * 60
        self.break_secs = 5 * 60
        self.elapsed = 0.0
        self.water_ratio = 0.0
        self.wave_t = 0.0
        self._bubbles: list[list[float]] = []
        self._badge_font = QFont("Sans Serif", 11, QFont.Weight.Bold)
        self.hide()

    def start_pomodoro(self, focus_secs: int = 25 * 60, break_secs: int = 5 * 60):
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())
        self.focus_secs = max(5, focus_secs)
        self.break_secs = max(5, break_secs)
        self.phase = "focus"
        self.elapsed = 0.0
        self.water_ratio = 0.16
        self.active = True
        self._bubbles = [
            [random.random(), random.random(), random.uniform(2.5, 6.5), random.uniform(0.0015, 0.004)]
            for _ in range(24)
        ]
        self.show()
        self.update()

    def stop_pomodoro(self):
        self.active = False
        self.phase = "idle"
        self.water_ratio = 0.0
        self.hide()

    def step(self, dt: float) -> str | None:
        if not self.active:
            return None

        self.wave_t += dt * 2.2
        self.elapsed += dt
        transition = None

        if self.phase == "focus":
            prog = min(1.0, self.elapsed / self.focus_secs)
            self.water_ratio = 0.16 + prog * 0.78
            if self.elapsed >= self.focus_secs:
                self.phase = "break"
                self.elapsed = 0.0
                transition = "enter_break"
        elif self.phase == "break":
            prog = min(1.0, self.elapsed / self.break_secs)
            self.water_ratio = max(0.08, 0.94 - prog * 0.86)
            if self.elapsed >= self.break_secs:
                self.phase = "focus"
                self.elapsed = 0.0
                transition = "enter_focus"

        for b in self._bubbles:
            b[1] -= b[3]
            if b[1] < 0.0:
                b[1] = 1.0
                b[0] = random.random()

        self.update()
        return transition

    def surface_global_y(self) -> float:
        geo = self.geometry()
        return geo.bottom() - self.water_ratio * geo.height()

    def remaining_seconds(self) -> int:
        total = self.focus_secs if self.phase == "focus" else self.break_secs
        return max(0, int(math.ceil(total - self.elapsed)))

    def paintEvent(self, _):
        if not self.active or self.water_ratio <= 0.01:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        surf_y = h * (1.0 - self.water_ratio)

        back_wave = QPainterPath()
        back_wave.moveTo(0, h)
        steps = 36
        for i in range(steps + 1):
            x = w * i / steps
            y = surf_y - 4 + math.sin(i * 0.45 + self.wave_t * 0.85 + 1.2) * 7.5
            back_wave.lineTo(x, y)
        back_wave.lineTo(w, h)
        back_wave.closeSubpath()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(46, 178, 224, 34 if self.phase == "focus" else 24))
        p.drawPath(back_wave)

        front_wave = QPainterPath()
        front_wave.moveTo(0, h)
        crest_pts: list[QPointF] = []
        for i in range(steps + 1):
            x = w * i / steps
            y = surf_y + math.sin(i * 0.55 - self.wave_t * 1.2) * 8.5 + math.cos(i * 0.25 + self.wave_t) * 3.0
            front_wave.lineTo(x, y)
            crest_pts.append(QPointF(x, y))
        front_wave.lineTo(w, h)
        front_wave.closeSubpath()

        grad = QLinearGradient(0, surf_y, 0, h)
        if self.phase == "focus":
            grad.setColorAt(0.0, QColor(90, 210, 250, 56))
            grad.setColorAt(1.0, QColor(20, 125, 200, 72))
        else:
            grad.setColorAt(0.0, QColor(115, 235, 215, 42))
            grad.setColorAt(1.0, QColor(45, 165, 185, 52))
        p.setBrush(grad)
        p.drawPath(front_wave)

        crest = QPainterPath()
        if crest_pts:
            crest.moveTo(crest_pts[0])
            for pt in crest_pts[1:]:
                crest.lineTo(pt)
        p.setPen(QPen(QColor(225, 250, 255, 165), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(crest)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 110))
        water_h = max(1.0, h - surf_y)
        for bx_n, by_n, br, _ in self._bubbles:
            bx = bx_n * w
            by = surf_y + 12 + by_n * max(1.0, water_h - 16)
            if by < h - 4:
                p.drawEllipse(QPointF(bx, by), br, br)

        rem = self.remaining_seconds()
        mm, ss = divmod(rem, 60)
        icon = "🌊" if self.phase == "focus" else "🫧"
        label = f"{icon} {mm:02d}:{ss:02d}"
        badge = QRectF(w - 118, h - 46, 102, 32)
        p.setPen(QPen(QColor(255, 255, 255, 180), 1.6))
        p.setBrush(QColor(15, 65, 110, 135))
        p.drawRoundedRect(badge, 14, 14)
        p.setFont(self._badge_font)
        p.setPen(QColor("#ffffff"))
        p.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)


class FishFood(QWidget):
    """Hạt cám cá, tép khô, mảnh cám hoặc Ký tự / Từ khóa / Emoji rơi chậm xuống đáy."""

    PELLET_KINDS = ("pellet", "shrimp", "flake")

    def __init__(self, x: int, y: int, bottom_y: int, kind: str | None = None, word: str | None = None):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)

        self.word = word or ""
        if word:
            self.kind = "word"
            self._font = QFont("Sans Serif", 11, QFont.Weight.Bold)
            fm = QFontMetrics(self._font)
            tw = fm.horizontalAdvance(self.word)
            self.resize(max(40, tw + 22), 34)
            bg_hex, fg_hex = random.choice(WORD_FOOD_COLORS)
            self._bg_col = QColor(bg_hex)
            self._fg_col = QColor(fg_hex)
        else:
            self.kind = kind if kind in self.PELLET_KINDS else random.choice(self.PELLET_KINDS)
            self.resize(36, 36)
            self._font = QFont("Sans Serif", 10)
            self._bg_col = QColor("#ffd93b")
            self._fg_col = QColor("#3b182c")

        self.fx = float(x)
        self.fy = float(y)
        self.bottom_y = float(bottom_y - self.height() - 4)
        self.fall_speed = random.uniform(0.55, 0.95)
        self.phase = random.uniform(0, math.tau)
        self.bite_progress = 0.0
        self.settled_ticks = 0
        self.move(int(self.fx), int(self.fy))
        self.show()

    def step(self) -> bool:
        """Trả về False nếu hạt thức ăn đã chìm đáy quá lâu và tự tan."""
        self.phase += 0.08
        if self.fy < self.bottom_y:
            self.fy = min(self.bottom_y, self.fy + self.fall_speed)
            self.fx += math.sin(self.phase) * 0.55
            self.move(int(self.fx), int(self.fy))
        else:
            self.settled_ticks += 1
            if self.settled_ticks > 480:  # 8 giây nằm đáy mà chưa ăn -> tự tan
                return False
        return True

    def center(self) -> tuple[float, float]:
        return self.fx + self.width() / 2.0, self.fy + self.height() / 2.0

    def paintEvent(self, _):
        scale = max(0.05, 1.0 - self.bite_progress)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2.0, self.height() / 2.0)
        p.scale(scale, scale)

        if self.kind == "word":
            w, h = self.width() - 6, self.height() - 6
            rect = QRectF(-w / 2.0, -h / 2.0, w, h)
            p.setPen(QPen(QColor("#3b182c"), 2.0))
            p.setBrush(self._bg_col)
            p.drawRoundedRect(rect, 11.0, 11.0)
            p.setFont(self._font)
            p.setPen(self._fg_col)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.word)
            return

        p.setPen(QPen(QColor("#3b182c"), 2.0))
        if self.kind == "shrimp":
            p.setBrush(QColor("#ff8566"))
            path = QPainterPath()
            path.moveTo(-8, -4)
            path.cubicTo(4, -12, 12, -2, 6, 8)
            path.cubicTo(2, 10, -4, 4, -8, -4)
            p.drawPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#3b182c"))
            p.drawEllipse(QPointF(-4, -3), 1.6, 1.6)
        elif self.kind == "flake":
            p.setBrush(QColor("#ffb74d"))
            poly = QPolygonF([
                QPointF(-10, -2),
                QPointF(-2, -9),
                QPointF(10, -4),
                QPointF(6, 7),
                QPointF(-6, 6),
            ])
            p.drawPolygon(poly)
        else:
            p.setBrush(QColor("#e07a3c"))
            p.drawEllipse(QRectF(-8, -8, 16, 16))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 240, 210, 170))
            p.drawEllipse(QRectF(-4, -5, 4, 4))
