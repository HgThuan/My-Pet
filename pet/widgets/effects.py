"""Các overlay hiệu ứng độc lập: sóng té nước, hạt toàn vùng (cầu vồng/chóng mặt) và bong bóng suy nghĩ."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)

from pet.widgets.base import _AllSpacesWidget


class SplashRippleOverlay(_AllSpacesWidget):
    """Hiệu ứng gợn sóng nước tung tóe ở mép dưới khi cá lặn ẩn mình (Boss Key) / ngoi lên."""

    _PASSIVE_CLICK_THROUGH = True

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
        self._mode = "boss"  # "boss" | "takeoff"
        self._drops: list[list[float]] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def trigger_at(self, center_x: float, bottom_y: float):
        self._mode = "boss"
        self.move(int(center_x - self.width() / 2), int(bottom_y - self.height() + 10))
        self._progress = 0.0
        self._drops = [
            [self.width() / 2.0 + random.uniform(-22, 22), self.height() - 18.0,
             random.uniform(-3.8, 3.8), random.uniform(-7.2, -3.4), random.uniform(4.0, 8.0)]
            for _ in range(12)
        ]
        self.show()
        self.raise_no_activate()
        if not self._timer.isActive():
            self._timer.start(16)
        self.update()

    def trigger_takeoff_at(self, center_x: float, surface_y: float):
        """Vòng tròn gợn sóng nhỏ tại điểm cất cánh trên thanh tiêu đề, tan biến sau ~0.5s."""
        self._mode = "takeoff"
        self.move(int(center_x - self.width() / 2), int(surface_y - self.height() + 18))
        self._progress = 0.0
        self._drops = [
            [self.width() / 2.0 + random.uniform(-14, 14), self.height() - 18.0,
             random.uniform(-2.6, 2.6), random.uniform(-4.8, -2.0), random.uniform(2.6, 4.8)]
            for _ in range(5)
        ]
        self.show()
        self.raise_no_activate()
        if not self._timer.isActive():
            self._timer.start(16)
        self.update()

    def _tick(self):
        self._progress += 0.032  # ~31 frames * 16ms ≈ 0.50s
        for d in self._drops:
            d[0] += d[2]
            d[1] += d[3]
            d[3] += 0.30 if self._mode == "takeoff" else 0.34
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

        # Vòng gợn sóng đồng tâm lan rộng (nhỏ gọn khi cất cánh từ thanh tiêu đề)
        p.setBrush(Qt.BrushStyle.NoBrush)
        is_takeoff = self._mode == "takeoff"
        ring_count = 2 if is_takeoff else 3
        for i in range(ring_count):
            rp = max(0.0, min(1.0, prog * 1.25 - i * 0.18))
            if rp <= 0.0:
                continue
            a = int((230 if is_takeoff else 220) * (1.0 - rp) * alpha)
            rx = (10.0 + rp * 50.0) if is_takeoff else (18.0 + rp * 98.0)
            ry = (3.5 + rp * 9.5) if is_takeoff else (6.0 + rp * 18.0)
            col = QColor(195, 245, 255, max(0, a)) if is_takeoff else QColor(115, 225, 255, max(0, a))
            p.setPen(QPen(col, (2.4 if is_takeoff else 3.2) - rp * 1.4))
            p.drawEllipse(QPointF(cx, cy), rx, ry)

        # Các giọt nước bắn tung lên
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(175, 240, 255, int(230 * alpha)))
        for x, y, _, _, r in self._drops:
            if y < self.height():
                p.drawEllipse(QPointF(x, y), r * (1.0 - prog * 0.4), r * (1.0 - prog * 0.4))




class ParticleFieldOverlay(_AllSpacesWidget):
    """Lớp hạt xuyên chuột cỡ rộng (520x440) bám theo vùng quanh cá giúp bong bóng cầu vồng & hạt chóng mặt bay tự do không bị cắt khung vuông."""

    _PASSIVE_CLICK_THROUGH = True
    OVERLAY_W = 520
    OVERLAY_H = 440

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
        self.resize(self.OVERLAY_W, self.OVERLAY_H)

        # Mỗi hạt: [kind, gx, gy, vx, vy, life, max_life, size, QColor, phase]
        self._items: list[list] = []
        self._origin_x = 0
        self._origin_y = 0
        self._frame = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def spawn(
        self,
        kind: str,
        gx: float,
        gy: float,
        vx: float,
        vy: float,
        life: int,
        size: float,
        color: QColor,
    ):
        if not self._items:
            self._origin_x = int(gx - self.OVERLAY_W / 2.0)
            self._origin_y = int(gy - self.OVERLAY_H / 2.0)
            self.move(self._origin_x, self._origin_y)
            self.show()
            self.raise_no_activate()
        self._items.append([kind, gx, gy, vx, vy, float(life), float(life), float(size), color, random.uniform(0.0, math.tau)])
        if not self._timer.isActive():
            self._timer.start(16)
        self.update()

    def clear_all(self):
        self._items.clear()
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._frame += 1
        alive: list[list] = []
        for it in self._items:
            kind = it[0]
            it[1] += it[3]
            it[2] += it[4]
            if kind in ("rainbow_bubble", "bubble"):
                it[3] *= 0.982
                it[4] = it[4] * 0.982 - 0.032
                it[1] += math.sin(self._frame * 0.12 + it[9]) * 0.45
            elif kind == "star":
                it[3] *= 0.96
                it[4] *= 0.96
            it[5] -= 1.0
            if it[5] > 0.0:
                alive.append(it)
        self._items = alive
        if not self._items:
            self._timer.stop()
            self.hide()
        else:
            self.update()

    def paintEvent(self, _):
        if not self._items:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox = float(self._origin_x)
        oy = float(self._origin_y)

        for kind, gx, gy, _, _, life, max_life, size, color, _ in self._items:
            alpha = max(0.0, min(1.0, life / max(1.0, max_life)))
            lx = gx - ox
            ly = gy - oy
            p.save()
            p.setOpacity(alpha)
            if kind in ("rainbow_bubble", "bubble"):
                rad = size * 0.5 * (1.0 + (1.0 - alpha) * 0.40)
                p.setPen(QPen(QColor(255, 255, 255, 235), 1.6))
                p.setBrush(color)
                p.drawEllipse(QPointF(lx, ly), rad, rad)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 230))
                p.drawEllipse(QPointF(lx - rad * 0.34, ly - rad * 0.34), rad * 0.28, rad * 0.28)
            elif kind == "star":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                s = size * 0.55
                poly = QPolygonF([
                    QPointF(lx, ly - s),
                    QPointF(lx + s * 0.3, ly - s * 0.3),
                    QPointF(lx + s, ly),
                    QPointF(lx + s * 0.3, ly + s * 0.3),
                    QPointF(lx, ly + s),
                    QPointF(lx - s * 0.3, ly + s * 0.3),
                    QPointF(lx - s, ly),
                    QPointF(lx - s * 0.3, ly - s * 0.3),
                ])
                p.drawPolygon(poly)
            p.restore()


class ThoughtBubbleOverlay(_AllSpacesWidget):
    """Bong bóng suy nghĩ nhỏ xuyên chuột phía trên đầu cá (chữ đòi ăn / icon thùng rác / no căng)."""

    _PASSIVE_CLICK_THROUGH = True

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

        self._mode = "text"  # "text" | "trash"
        self._text = ""
        self._ticks_left = 0
        self._max_ticks = 1
        self._alpha = 0.0
        self._font = QFont("Sans Serif", 9, QFont.Weight.DemiBold)
        self.hide()

    def show_text(self, text: str, duration_ticks: int = 150):
        self._mode = "text"
        self._text = text
        self._ticks_left = max(1, duration_ticks)
        self._max_ticks = self._ticks_left
        self._alpha = 1.0
        fm = QFontMetrics(self._font)
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        w = max(84, tw + 28)
        h = th + 30
        self.resize(w, h)
        self.show()
        self.raise_no_activate()
        self.update()

    def show_trash_icon(self, duration_ticks: int = 150):
        self._mode = "trash"
        self._text = ""
        self._ticks_left = max(1, duration_ticks)
        self._max_ticks = self._ticks_left
        self._alpha = 1.0
        self.resize(64, 58)
        self.show()
        self.raise_no_activate()
        self.update()

    def dismiss(self):
        self._ticks_left = 0
        self._alpha = 0.0
        self.hide()

    def follow(self, head_gx: float, head_gy: float):
        if self._ticks_left <= 0:
            if self.isVisible():
                self.hide()
            return
        self._ticks_left -= 1
        if self._ticks_left < 20:
            self._alpha = max(0.0, self._ticks_left / 20.0)
            self.update()
        else:
            self._alpha = 1.0
        bx = int(head_gx - self.width() / 2.0)
        by = int(head_gy - self.height() - 4.0)
        self.move(bx, by)

    def paintEvent(self, _):
        if self._ticks_left <= 0 or self._alpha <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._alpha)

        w, h = float(self.width()), float(self.height())
        body = QRectF(3.0, 3.0, w - 6.0, h - 18.0)

        outline = QColor("#3b182c")
        p.setPen(QPen(outline, 2.0))
        p.setBrush(QColor(255, 253, 246, 245))
        p.drawRoundedRect(body, 12.0, 12.0)

        # Hai chấm tròn nhỏ nối xuống đầu cá kiểu bong bóng suy nghĩ
        p.drawEllipse(QPointF(w * 0.5 - 3.0, h - 10.5), 4.0, 3.5)
        p.drawEllipse(QPointF(w * 0.5 + 2.5, h - 4.2), 2.3, 2.1)

        if self._mode == "trash":
            self._draw_trash_icon(p, body.center().x(), body.center().y())
        else:
            p.setFont(self._font)
            p.setPen(outline)
            p.drawText(body, Qt.AlignmentFlag.AlignCenter, self._text)

    @staticmethod
    def _draw_trash_icon(p: QPainter, cx: float, cy: float):
        outline = QColor("#3b182c")
        p.save()
        p.translate(cx, cy)
        p.setPen(QPen(outline, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        # Nắp thùng rác
        p.setBrush(QColor("#8d99ae"))
        p.drawRoundedRect(QRectF(-10.0, -9.5, 20.0, 3.2), 1.4, 1.4)
        p.drawLine(QPointF(-3.5, -11.5), QPointF(3.5, -11.5))
        # Thân thùng rác
        bin_poly = QPolygonF([
            QPointF(-8.2, -6.0),
            QPointF(8.2, -6.0),
            QPointF(6.8, 10.5),
            QPointF(-6.8, 10.5),
        ])
        p.setBrush(QColor("#edf2f4"))
        p.drawPolygon(bin_poly)
        # 3 sọc dọc bên trong thùng rác
        p.setPen(QPen(QColor("#5c677d"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for sx in (-3.2, 0.0, 3.2):
            p.drawLine(QPointF(sx, -2.5), QPointF(sx * 0.85, 7.2))
        p.restore()
