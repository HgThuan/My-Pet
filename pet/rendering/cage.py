"""Vẽ Lồng Sắt 2D (Cage Mode), vây van xin và cánh tay lực sĩ bẻ cong thanh sắt."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

from pet.rendering.primitives import _draw_star


# ---------- Vẽ Lồng Sắt 2D (Cage Mode) & Lực sĩ bẻ thanh sắt ----------

_CAGE_RIM_Y = 48.0
_CAGE_RIM_RX = 52.0
_CAGE_RIM_RY = 11.5
_CAGE_CAP_Y = -60.0


def _cage_ellipse_y(x: float, front: bool) -> float:
    ratio = max(-1.0, min(1.0, x / _CAGE_RIM_RX))
    dy = _CAGE_RIM_RY * math.sqrt(max(0.0, 1.0 - ratio * ratio))
    return _CAGE_RIM_Y + dy if front else _CAGE_RIM_Y - dy


def _cage_middle_bar_grip_x(bend_amount: float) -> float:
    """Trả về khoảng cách X từ tâm tới 2 thanh sắt giữa tại độ cao tay cá nắm (y ≈ +8)."""
    return 17.5 + max(0.0, min(1.0, bend_amount)) * 28.5


def _cage_dome_bar_path(x_top: float, x_bot: float, y_bot: float) -> QPainterPath:
    """Đường cong mái vòm cổ điển từ chóp lồng xuống vành đáy."""
    path = QPainterPath()
    path.moveTo(x_top, _CAGE_CAP_Y)
    # Độ nở mái vòm theo tỷ lệ khoảng cách x_bot
    shoulder_x = x_bot * 1.06
    path.cubicTo(
        x_top + (shoulder_x - x_top) * 0.62,
        _CAGE_CAP_Y + 6.0,
        shoulder_x,
        -24.0,
        x_bot,
        y_bot,
    )
    return path


def _cage_bendable_bar_path(side: int, bend_amount: float) -> QPainterPath:
    """Thanh sắt dọc ở giữa lồng có thể uốn cong sang hai bên (side = -1 trái, +1 phải)."""
    x_top = side * 3.0
    x_bot = side * 16.5
    y_bot = _cage_ellipse_y(x_bot, front=True)
    bend = max(0.0, min(1.0, bend_amount))

    if bend <= 0.005:
        return _cage_dome_bar_path(x_top, x_bot, y_bot)

    # Điểm khuỷu nơi cánh tay lực sĩ bẻ bật thanh sắt sang hai bên
    elbow_x = side * _cage_middle_bar_grip_x(bend)
    elbow_y = 7.0
    path = QPainterPath()
    path.moveTo(x_top, _CAGE_CAP_Y)
    path.cubicTo(
        side * (12.0 + bend * 14.0),
        -46.0,
        elbow_x + side * (2.5 * bend),
        -16.0,
        elbow_x,
        elbow_y,
    )
    path.cubicTo(
        elbow_x + side * (2.5 * bend),
        28.0,
        x_bot + side * (7.0 * bend),
        44.0,
        x_bot,
        y_bot,
    )
    return path


def _stroke_metal_bar(
    p: QPainter,
    path: QPainterPath,
    width_outer: float,
    core_col: QColor,
    hi_col: QColor | None = None,
    outline_col: QColor | None = None,
) -> None:
    out_c = outline_col or QColor("#23272e")
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(out_c, width_outer, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPath(path)
    p.setPen(QPen(core_col, max(1.6, width_outer - 2.8), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPath(path)
    if hi_col is not None and width_outer >= 4.8:
        p.save()
        p.translate(-0.7, 0.0)
        p.setPen(QPen(hi_col, 1.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(path)
        p.restore()


def _draw_cage_back(p: QPainter) -> None:
    """Vẽ nửa sau của lồng sắt (nền bóng bên trong, các thanh sắt sau, nửa sau vành đáy)."""
    outline = QColor("#22262c")
    back_core = QColor("#49525c")

    # Bóng mờ cực nhẹ bên trong vòm lồng tạo cảm giác không gian 3D
    dome_bg = QPainterPath()
    dome_bg.moveTo(-10.0, _CAGE_CAP_Y)
    dome_bg.cubicTo(-42.0, -52.0, -52.5, -20.0, -51.5, _CAGE_RIM_Y)
    dome_bg.arcTo(
        QRectF(-_CAGE_RIM_RX, _CAGE_RIM_Y - _CAGE_RIM_RY, _CAGE_RIM_RX * 2, _CAGE_RIM_RY * 2),
        180.0,
        180.0,
    )
    dome_bg.cubicTo(52.5, -20.0, 42.0, -52.0, 10.0, _CAGE_CAP_Y)
    dome_bg.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(24, 38, 52, 26))
    p.drawPath(dome_bg)

    # Đáy sàn lồng (elip trong + các thanh ngang sàn lồng)
    floor_rect = QRectF(-_CAGE_RIM_RX + 2.0, _CAGE_RIM_Y - _CAGE_RIM_RY + 1.0, (_CAGE_RIM_RX - 2.0) * 2, (_CAGE_RIM_RY - 1.0) * 2)
    p.setPen(QPen(outline, 3.0))
    p.setBrush(QColor(52, 60, 68, 130))
    p.drawEllipse(floor_rect)

    # Các thanh sắt nhỏ đan dưới sàn lồng
    p.setPen(QPen(QColor("#363e47"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for fx in (-34.0, -18.0, 0.0, 18.0, 34.0):
        fy1 = _cage_ellipse_y(fx, front=False) + 1.5
        fy2 = _cage_ellipse_y(fx, front=True) - 1.5
        p.drawLine(QPointF(fx, fy1), QPointF(fx, fy2))

    # 4 thanh sắt vòm phía sau (mảnh và tối hơn nửa trước để tạo chiều sâu)
    for x_top, x_bot in ((-7.0, -37.0), (-2.5, -14.0), (2.5, 14.0), (7.0, 37.0)):
        yb = _cage_ellipse_y(x_bot, front=False)
        bar = _cage_dome_bar_path(x_top, x_bot, yb)
        _stroke_metal_bar(p, bar, 4.2, back_core, hi_col=None, outline_col=outline)


def _draw_cage_front(p: QPainter, bend_amount: float, drop_progress: float, t_sec: float) -> None:
    """Vẽ nửa trước của lồng sắt (khung ngoài, 4 thanh trước có 2 thanh giữa uốn cong được, vành đáy, chóp & móc treo)."""
    outline = QColor("#22262c")
    iron_core = QColor("#73808c")
    iron_dark = QColor("#545f69")
    iron_hi = QColor("#b8c4cf")
    rust_col = QColor(158, 86, 44, 185)

    # 1. Hai thanh khung biên trái / phải tạo dáng mái vòm
    for side in (-1, 1):
        outer_bar = _cage_dome_bar_path(side * 10.0, side * (_CAGE_RIM_RX - 0.5), _CAGE_RIM_Y)
        _stroke_metal_bar(p, outer_bar, 6.4, iron_core, hi_col=iron_hi, outline_col=outline)

    # 2. Hai thanh sắt trước ngoài (trái & phải)
    for side in (-1, 1):
        xb = side * 36.5
        yb = _cage_ellipse_y(xb, front=True)
        bar = _cage_dome_bar_path(side * 7.0, xb, yb)
        _stroke_metal_bar(p, bar, 5.6, iron_core, hi_col=iron_hi, outline_col=outline)

    # 3. Hai thanh sắt trước ở giữa (CÓ THỂ BỊ BẺ CONG SANG HAI BÊN!)
    for side in (-1, 1):
        mid_bar = _cage_bendable_bar_path(side, bend_amount)
        _stroke_metal_bar(p, mid_bar, 5.8, iron_core, hi_col=iron_hi, outline_col=outline)
        # Ánh nóng ứng suất kim loại tại điểm bị bẻ cong
        if bend_amount > 0.12:
            ex = side * _cage_middle_bar_grip_x(bend_amount)
            ey = 7.0
            glow_r = 7.0 + 4.0 * math.sin(t_sec * 35.0)
            stress = QRadialGradient(QPointF(ex, ey), glow_r)
            stress.setColorAt(0.0, QColor(255, 224, 115, int(190 * bend_amount)))
            stress.setColorAt(1.0, QColor(255, 130, 40, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(stress)
            p.drawEllipse(QPointF(ex, ey), glow_r, glow_r)

    # Điểm nhấn vết gỉ sét nghệ thuật giống ảnh tham khảo trên khung ngoài
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(rust_col)
    p.drawEllipse(QRectF(-52.5, 4.0, 3.8, 9.5))
    p.drawEllipse(QRectF(48.8, -14.0, 3.8, 8.5))
    p.drawEllipse(QRectF(19.0, -49.0, 6.0, 3.2))

    # 4. Vành đáy sắt 3D phía trước (dải vòng kim loại dày bo mặt trước)
    rim_band = QPainterPath()
    rim_band.moveTo(-_CAGE_RIM_RX, _CAGE_RIM_Y)
    rim_band.arcTo(
        QRectF(-_CAGE_RIM_RX, _CAGE_RIM_Y - _CAGE_RIM_RY, _CAGE_RIM_RX * 2, _CAGE_RIM_RY * 2),
        180.0,
        180.0,
    )
    rim_band.lineTo(_CAGE_RIM_RX, _CAGE_RIM_Y + 6.5)
    rim_band.arcTo(
        QRectF(-_CAGE_RIM_RX, _CAGE_RIM_Y + 6.5 - _CAGE_RIM_RY, _CAGE_RIM_RX * 2, _CAGE_RIM_RY * 2),
        0.0,
        -180.0,
    )
    rim_band.closeSubpath()

    rim_grad = QLinearGradient(-_CAGE_RIM_RX, _CAGE_RIM_Y, _CAGE_RIM_RX, _CAGE_RIM_Y)
    rim_grad.setColorAt(0.0, iron_dark)
    rim_grad.setColorAt(0.28, iron_core)
    rim_grad.setColorAt(0.55, QColor("#8e9ba6"))
    rim_grad.setColorAt(0.85, iron_dark)
    rim_grad.setColorAt(1.0, QColor("#3e464e"))
    p.setPen(QPen(outline, 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(rim_grad)
    p.drawPath(rim_band)

    # Vệt gỉ nhỏ trên vành đáy giống ảnh minh họa
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(rust_col)
    p.drawEllipse(QRectF(8.0, _CAGE_RIM_Y + 9.0, 14.0, 4.2))
    p.drawEllipse(QRectF(-34.0, _CAGE_RIM_Y + 6.8, 9.0, 3.4))

    # Đường viền sáng mảnh dọc mép trên vành đáy
    rim_hi = QPainterPath()
    rim_hi.arcMoveTo(QRectF(-_CAGE_RIM_RX + 2.0, _CAGE_RIM_Y - _CAGE_RIM_RY, (_CAGE_RIM_RX - 2.0) * 2, _CAGE_RIM_RY * 2), 200.0)
    rim_hi.arcTo(QRectF(-_CAGE_RIM_RX + 2.0, _CAGE_RIM_Y - _CAGE_RIM_RY, (_CAGE_RIM_RX - 2.0) * 2, _CAGE_RIM_RY * 2), 200.0, 140.0)
    p.setPen(QPen(QColor(215, 226, 236, 175), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(rim_hi)

    # 5. Móc treo đỉnh lồng + Chóp sắt tròn (Cap)
    # Thanh xích ngắn trên đỉnh
    p.setPen(QPen(outline, 5.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(0.0, -84.0), QPointF(0.0, -78.0))
    p.setPen(QPen(iron_core, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(0.0, -84.0), QPointF(0.0, -78.0))

    # Vòng tròn móc treo
    p.setPen(QPen(outline, 5.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(0.0, -72.0), 6.8, 6.8)
    p.setPen(QPen(iron_core, 2.8))
    p.drawEllipse(QPointF(0.0, -72.0), 6.8, 6.8)
    p.setPen(QPen(iron_hi, 1.0))
    p.drawArc(QRectF(-6.8, -78.8, 13.6, 13.6), 95 * 16, 75 * 16)

    # Chóp tròn nối các thanh sắt trên đỉnh
    cap = QPainterPath()
    cap.moveTo(-14.5, -58.5)
    cap.cubicTo(-13.5, -67.5, 13.5, -67.5, 14.5, -58.5)
    cap.quadTo(0.0, -54.5, -14.5, -58.5)
    cap.closeSubpath()
    p.setPen(QPen(outline, 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(iron_core)
    p.drawPath(cap)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(iron_hi)
    p.drawEllipse(QRectF(-7.5, -64.5, 7.0, 2.8))
    p.setBrush(rust_col)
    p.drawEllipse(QRectF(2.5, -62.5, 5.5, 2.6))

    # Tia sáng lóe "cạch!" khi chốt khóa lồng vừa đóng lại
    if 0.68 <= drop_progress <= 0.98:
        glint_p = 1.0 - abs(drop_progress - 0.82) / 0.16
        if glint_p > 0.0:
            p.save()
            p.setOpacity(max(0.0, min(1.0, glint_p)))
            _draw_star(p, 0.0, -61.0, 14.0 + 6.0 * glint_p, QColor("#fff7cc"))
            _draw_star(p, -22.0, _CAGE_RIM_Y + 9.0, 10.0 * glint_p, QColor("#ffffff"))
            p.restore()


def _draw_cage_pleading_fins(
    p: QPainter,
    body_col: QColor,
    shade_col: QColor,
    outline: QColor,
    t_sec: float,
) -> None:
    """Vẽ hai chiếc vây trước dễ thương bám chặt lấy 2 thanh sắt dọc (chế độ Van xin giống ảnh mẫu)."""
    grip_x = _cage_middle_bar_grip_x(0.0)
    wiggle = math.sin(t_sec * 11.0) * 0.9
    pen_out = QPen(outline, 2.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    for side in (-1, 1):
        p.save()
        p.translate(side * grip_x, 12.0 + wiggle * side * 0.4)
        p.rotate(side * -8.0)

        # Thân bàn vây tròn ôm lấy thanh sắt
        p.setPen(pen_out)
        p.setBrush(body_col)
        p.drawEllipse(QRectF(-8.5, -6.5, 17.0, 13.0))

        # Bóng cam ấm phía dưới vây
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shade_col)
        p.drawEllipse(QRectF(-6.0, 1.0, 12.0, 4.2))

        # 2 đường ngón vây nhỏ bám vòng quanh thanh sắt (giống hệt ảnh mẫu!)
        p.setPen(QPen(outline, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        tip_x = -side * 3.5
        p.drawLine(QPointF(tip_x, -2.2), QPointF(tip_x - side * 3.8, -2.2))
        p.drawLine(QPointF(tip_x, 2.2), QPointF(tip_x - side * 3.8, 2.2))
        p.restore()


def _draw_cage_muscular_arms(
    p: QPainter,
    bend_amount: float,
    muscular_level: float,
    body_col: QColor,
    hi_col: QColor,
    shade_col: QColor,
    outline: QColor,
    t_sec: float,
) -> None:
    """Vẽ đôi cánh tay cơ bắp lực sĩ cuồn cuộn nắm chặt và bẻ cong 2 thanh sắt ở giữa lồng!"""
    m = max(0.0, min(1.0, muscular_level))
    grip_x = _cage_middle_bar_grip_x(bend_amount)
    shake = math.sin(t_sec * 52.0) * (1.2 + 1.4 * m)
    pen_out = QPen(outline, 2.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    for side in (-1, 1):
        p.save()
        # Lật đối xứng trái/phải
        p.scale(float(side), 1.0)
        gx = grip_x + shake * 0.4 * side
        gy = 7.0 + shake * 0.35

        # Vai nối từ hông cá -> bắp tay cuồn cuộn -> cẳng tay -> nắm đấm ôm thanh sắt
        shoulder_x = 15.0
        bicep_x = (shoulder_x + gx) * 0.52
        bicep_h = 11.0 + 7.5 * m

        arm = QPainterPath()
        arm.moveTo(shoulder_x, 0.0)
        # Bầu cơ bắp chuột (biceps) phồng căng lên trên!
        arm.cubicTo(
            shoulder_x + 4.0,
            -bicep_h,
            bicep_x + 6.0,
            -bicep_h - 2.0,
            gx - 4.0,
            gy - 6.5,
        )
        # Vòng xuống qua nắm đấm và cẳng tay dưới
        arm.lineTo(gx - 2.0, gy + 7.5)
        arm.cubicTo(
            bicep_x + 2.0,
            gy + 10.5,
            shoulder_x + 2.0,
            13.5,
            shoulder_x - 1.0,
            10.5,
        )
        arm.closeSubpath()

        p.setPen(pen_out)
        p.setBrush(body_col)
        p.drawPath(arm)

        # Bóng cơ bắp phía dưới & ánh bóng căng cơ trên đỉnh bắp chuột
        p.setPen(QPen(hi_col, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(bicep_x - 8.0, -bicep_h * 0.72, 14.0, 9.0), 30 * 16, 125 * 16)
        p.setPen(QPen(shade_col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(bicep_x - 3.0, 5.5), QPointF(bicep_x + 6.0, 6.5))

        # Nắm đấm siết chặt quanh thanh sắt đang bẻ cong
        p.setPen(pen_out)
        p.setBrush(body_col)
        p.drawRoundedRect(QRectF(gx - 7.5, gy - 7.5, 14.0, 15.0), 5.5, 5.5)
        p.setPen(QPen(outline, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for ky in (-3.0, 0.5, 4.0):
            p.drawLine(QPointF(gx - 2.5, gy + ky), QPointF(gx + 4.5, gy + ky))
        p.restore()


def draw_iron_cage_for_overlay(
    p: QPainter,
    cx: float,
    cy: float,
    swing_deg: float,
    bend_amount: float,
    opacity: float,
    scale: float = 1.0,
) -> None:
    """Vẽ toàn bộ chiếc lồng sắt (đã bị bẻ cong) cho widget hiệu ứng rơi vỡ biến mất."""
    if opacity <= 0.01:
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setOpacity(max(0.0, min(1.0, opacity)))
    p.translate(cx, cy)
    p.scale(scale, scale)
    p.rotate(swing_deg)
    _draw_cage_back(p)
    _draw_cage_front(p, bend_amount, 1.0, 0.0)
    p.restore()
