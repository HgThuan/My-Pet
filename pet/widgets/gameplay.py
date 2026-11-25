"""Các widget tương tác: Pomodoro Mực Nước, Thức ăn Ký tự và Lồng Sắt rơi sau phá lồng."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)

from pet.config import WORD_FOOD_COLORS
from pet.rendering.cage import draw_iron_cage_for_overlay
from pet.widgets.base import _AllSpacesWidget


class WaterOverlay(_AllSpacesWidget):
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


class FishFood(_AllSpacesWidget):
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


class FallingCageOverlay(_AllSpacesWidget):
    """Hiệu ứng chiếc lồng sắt đã bị bẻ cong rơi tự do xuống đáy màn hình và mờ dần biến mất."""

    OVERLAY_SIZE = 224

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
        self.resize(self.OVERLAY_SIZE, self.OVERLAY_SIZE)

        self._active = False
        self._cx = 0.0
        self._cy = 0.0
        self._vx = 0.0
        self._vy = 0.0
        self._rot = 0.0
        self._rot_vel = 0.0
        self._bend = 1.0
        self._opacity = 0.0
        self._bottom_y = 1080.0
        self._shards: list[list[float]] = []  # [lx, ly, vx, vy, rot, rot_v, length]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def trigger_at(
        self,
        center_x: float,
        center_y: float,
        swing_deg: float,
        bend_amount: float,
        bottom_y: float,
    ):
        self._active = True
        self._cx = float(center_x)
        self._cy = float(center_y)
        self._vx = random.uniform(-1.1, 1.1)
        self._vy = -1.8
        self._rot = float(swing_deg)
        self._rot_vel = random.choice([-1.0, 1.0]) * random.uniform(2.2, 3.8)
        self._bend = max(0.0, min(1.0, bend_amount))
        self._opacity = 1.0
        self._bottom_y = float(bottom_y)
        half = self.OVERLAY_SIZE / 2.0
        self._shards = [
            [
                half + random.uniform(-28, 28),
                half + random.uniform(-18, 24),
                random.uniform(-3.4, 3.4),
                random.uniform(-5.0, -1.2),
                random.uniform(0, 360),
                random.uniform(-14.0, 14.0),
                random.uniform(7.0, 14.0),
            ]
            for _ in range(8)
        ]
        self.move(int(self._cx - half), int(self._cy - half))
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start(16)
        self.update()

    def stop(self):
        self._active = False
        self._timer.stop()
        self.hide()

    def _tick(self):
        if not self._active:
            self._timer.stop()
            self.hide()
            return

        self._vy += 0.58
        self._cx += self._vx
        self._cy += self._vy
        self._rot += self._rot_vel

        # Mờ dần theo thời gian rơi & tăng tốc fade-out khi chạm gần đáy màn hình
        fade = 0.017
        dist_to_bottom = self._bottom_y - self._cy
        if dist_to_bottom < 160.0:
            fade += 0.032
        self._opacity = max(0.0, self._opacity - fade)

        for s in self._shards:
            s[0] += s[2]
            s[1] += s[3]
            s[3] += 0.25
            s[4] += s[5]

        half = self.OVERLAY_SIZE / 2.0
        if self._opacity <= 0.01 or (self._cy - half) > self._bottom_y:
            self._active = False
            self._timer.stop()
            self.hide()
            return

        self.move(int(self._cx - half), int(self._cy - half))
        self.update()

    def paintEvent(self, _):
        if not self._active or self._opacity <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        half = self.OVERLAY_SIZE / 2.0
        scale = 0.88 + 0.12 * self._opacity
        draw_iron_cage_for_overlay(p, half, half, self._rot, self._bend, self._opacity, scale=scale)

        # Vài mảnh sắt / tia vỡ bay tách khỏi khung lồng
        p.save()
        p.setOpacity(self._opacity)
        for lx, ly, _, _, rot, _, length in self._shards:
            p.save()
            p.translate(lx, ly)
            p.rotate(rot)
            p.setPen(QPen(QColor("#22262c"), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(-length * 0.5, 0.0), QPointF(length * 0.5, 0.0))
            p.setPen(QPen(QColor("#85929e"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(-length * 0.5, 0.0), QPointF(length * 0.5, 0.0))
            p.restore()
        p.restore()


