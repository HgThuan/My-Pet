"""Các hàm vẽ vector nguyên thủy dùng chung (sao, tim, giọt mồ hôi, vệt sóng, file bị nuốt...)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)


def _clamp_ellipse(x: float, y: float, rx: float, ry: float) -> tuple[float, float]:
    """Giới hạn tọa độ (x, y) nằm gọn bên trong hình elip bán trục (rx, ry)."""
    if rx <= 0.0 or ry <= 0.0:
        return 0.0, 0.0
    n = math.hypot(x / rx, y / ry)
    if n > 1.0:
        return x / n, y / n
    return x, y




def _draw_surf_wake_ripples(
    p: QPainter,
    cx: float,
    waterline_y: float,
    direction: int,
    surf_speed: float,
    scale: float,
    t_sec: float,
) -> None:
    """Vẽ vệt sóng rẽ nước hình chữ V và mép bọt trắng tại giao điểm bụng cá & thanh tiêu đề cửa sổ."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    spd = max(0.20, min(1.0, surf_speed))
    # Hướng đi của cá: dir_sign = +1 đi phải (sóng tỏa về trái -X), -1 đi trái (sóng tỏa về phải +X)
    back = -1.0 if direction > 0 else 1.0
    bow_x = cx - back * 22.0 * scale

    # 1. Đường mặt nước mỏng lấp lánh ôm ngay bụng cá
    shimmer = 0.72 + 0.28 * math.sin(t_sec * 8.0)
    meniscus_w = (30.0 + 10.0 * spd) * scale
    p.setPen(QPen(QColor(220, 250, 255, int(205 * shimmer)), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(cx - meniscus_w, waterline_y), QPointF(cx + meniscus_w, waterline_y))

    # 2. 3 đường gợn sóng chữ V trắng/xanh nhạt rẽ nước tỏa dần về phía sau đuôi cá
    p.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(3):
        phase = (t_sec * (2.6 + spd * 2.2) + i * 0.33) % 1.0
        start_x = bow_x + back * (phase * 14.0 * scale)
        tail_len = (24.0 + 26.0 * spd + phase * 18.0) * scale
        end_x = start_x + back * tail_len
        spread_y = (3.5 + phase * 6.5 + i * 1.4) * scale
        alpha_v = int((1.0 - phase * 0.72) * (155 + 80 * spd))
        col = QColor(245, 253, 255, max(20, alpha_v)) if i == 0 else QColor(145, 232, 255, max(20, alpha_v))
        p.setPen(QPen(col, max(1.1, 2.3 - phase * 1.1), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

        # Cánh sóng chữ V trên & dưới lan nhẹ ra sau
        upper = QPainterPath()
        upper.moveTo(start_x, waterline_y - 0.5)
        upper.quadTo(
            start_x + back * tail_len * 0.5,
            waterline_y - spread_y * 0.85,
            end_x,
            waterline_y - spread_y,
        )
        p.drawPath(upper)

        lower = QPainterPath()
        lower.moveTo(start_x, waterline_y + 0.8)
        lower.quadTo(
            start_x + back * tail_len * 0.5,
            waterline_y + spread_y * 0.55,
            end_x,
            waterline_y + spread_y * 0.45,
        )
        p.drawPath(lower)

    # 3. Điểm bọt rẽ nước nhỏ ngay mũi ngực cá
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, int(215 * shimmer)))
    p.drawEllipse(QPointF(bow_x, waterline_y - 1.2), 2.8 * scale, 1.8 * scale)
    p.restore()


def _draw_angel_halo(p: QPainter, cx: float, cy: float, scale: float, t_sec: float) -> None:
    """Vòng hào quang thiên thần vàng sáng lơ lửng phía trên khi cá giả chết."""
    p.save()
    hover = math.sin(t_sec * 2.4) * 2.4
    pulse = 0.80 + 0.20 * math.sin(t_sec * 3.8)
    p.translate(cx, cy + hover)
    p.scale(scale, scale)

    # Quầng sáng mềm vàng ấm
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 232, 102, int(95 * pulse)), 8.0))
    p.drawEllipse(QRectF(-22.0, -6.5, 44.0, 13.0))

    # Vòng hào quang chính
    p.setPen(QPen(QColor("#ffbe0b"), 3.6))
    p.drawEllipse(QRectF(-22.0, -6.5, 44.0, 13.0))
    p.setPen(QPen(QColor("#fff7cc"), 1.6))
    p.drawEllipse(QRectF(-22.0, -6.5, 44.0, 13.0))
    p.restore()


def _draw_mini_ghost(p: QPainter, x: float, y: float, size: float, color: QColor) -> None:
    """Linh hồn nhỏ siêu dễ thương bay mờ dần lên trời khi cá giả chết."""
    p.save()
    p.translate(x, y)
    r = size * 0.55
    body = QPainterPath()
    body.moveTo(-r, r * 0.7)
    body.lineTo(-r, -r * 0.15)
    body.cubicTo(-r, -r * 1.15, r, -r * 1.15, r, -r * 0.15)
    body.lineTo(r, r * 0.7)
    body.quadTo(r * 0.5, r * 0.35, 0.0, r * 0.75)
    body.quadTo(-r * 0.5, r * 0.35, -r, r * 0.7)
    body.closeSubpath()

    p.setPen(QPen(QColor(110, 145, 185, 180), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(color)
    p.drawPath(body)

    # Đôi mắt tròn nhỏ xinh trên linh hồn
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3b4c63"))
    p.drawEllipse(QPointF(-r * 0.32, -r * 0.15), r * 0.16, r * 0.18)
    p.drawEllipse(QPointF(r * 0.32, -r * 0.15), r * 0.16, r * 0.18)
    p.restore()


def _draw_heart(p: QPainter, x: float, y: float, size: float, color: QColor) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    s = size * 0.5
    path = QPainterPath()
    path.moveTo(x, y + s * 0.7)
    path.cubicTo(x - s * 1.4, y - s * 0.3, x - s * 0.7, y - s * 1.3, x, y - s * 0.4)
    path.cubicTo(x + s * 0.7, y - s * 1.3, x + s * 1.4, y - s * 0.3, x, y + s * 0.7)
    p.drawPath(path)


def _draw_star(p: QPainter, x: float, y: float, size: float, color: QColor) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    s = size * 0.55
    poly = QPolygonF([
        QPointF(x, y - s),
        QPointF(x + s * 0.3, y - s * 0.3),
        QPointF(x + s, y),
        QPointF(x + s * 0.3, y + s * 0.3),
        QPointF(x, y + s),
        QPointF(x - s * 0.3, y + s * 0.3),
        QPointF(x - s, y),
        QPointF(x - s * 0.3, y - s * 0.3),
    ])
    p.drawPolygon(poly)


def _draw_anger_mark(p: QPainter, x: float, y: float, size: float, color: QColor) -> None:
    p.setPen(QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    r = size * 0.38
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        arc = QPainterPath()
        arc.moveTo(x + sx * r, y + sy * r * 0.25)
        arc.quadTo(x + sx * r * 0.25, y + sy * r * 0.25, x + sx * r * 0.25, y + sy * r)
        p.drawPath(arc)


def _draw_sweat_drop(p: QPainter, x: float, y: float, size: float, color: QColor) -> None:
    p.setPen(QPen(QColor("#2b6cb0"), 1.2))
    p.setBrush(color)
    s = size * 0.6
    path = QPainterPath()
    path.moveTo(x, y - s)
    path.cubicTo(x + s * 0.9, y + s * 0.2, x + s * 0.7, y + s, x, y + s)
    path.cubicTo(x - s * 0.7, y + s, x - s * 0.9, y + s * 0.2, x, y - s)
    p.drawPath(path)


def _draw_eaten_file_icon(
    p: QPainter,
    x: float,
    y: float,
    scale: float,
    rot_deg: float,
    is_dir: bool,
) -> None:
    """Vẽ biểu tượng file / thư mục đang bị hút vào miệng cá."""
    p.save()
    p.translate(x, y)
    p.rotate(rot_deg)
    p.scale(scale, scale)
    outline = QColor("#3b182c")
    p.setPen(QPen(outline, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

    if is_dir:
        # Biểu tượng thư mục màu vàng nhạt
        folder = QPainterPath()
        folder.moveTo(-13, -8)
        folder.lineTo(-4, -8)
        folder.lineTo(-1, -12)
        folder.lineTo(13, -12)
        folder.lineTo(13, 10)
        folder.lineTo(-13, 10)
        folder.closeSubpath()
        p.setBrush(QColor("#ffca3a"))
        p.drawPath(folder)
    else:
        # Biểu tượng tờ file có góc gấp
        doc = QPolygonF([
            QPointF(-11, -14),
            QPointF(4, -14),
            QPointF(11, -7),
            QPointF(11, 14),
            QPointF(-11, 14),
        ])
        p.setBrush(QColor("#ffffff"))
        p.drawPolygon(doc)
        # Góc gấp
        fold = QPolygonF([QPointF(4, -14), QPointF(4, -7), QPointF(11, -7)])
        p.setBrush(QColor("#dce6f2"))
        p.drawPolygon(fold)
        # Dòng chữ nhỏ trên tờ file
        p.setPen(QPen(QColor("#5c7cfa"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(-6, -2), QPointF(6, -2))
        p.drawLine(QPointF(-6, 3), QPointF(6, 3))
        p.drawLine(QPointF(-6, 8), QPointF(2, 8))
    p.restore()


