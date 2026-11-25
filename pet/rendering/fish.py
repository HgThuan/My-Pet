"""Hàm render chính cho linh vật Cá Vàng 2D và các phụ kiện theo ngữ cảnh."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)

from pet.models import FishRenderState
from pet.rendering.cage import (
    _draw_cage_back,
    _draw_cage_front,
    _draw_cage_muscular_arms,
    _draw_cage_pleading_fins,
)
from pet.rendering.face import _draw_fish_face, _draw_pointing_fin
from pet.rendering.primitives import (
    _draw_angel_halo,
    _draw_anger_mark,
    _draw_eaten_file_icon,
    _draw_heart,
    _draw_mini_ghost,
    _draw_star,
    _draw_surf_wake_ripples,
    _draw_sweat_drop,
)


def render_fish(p: QPainter, st: FishRenderState) -> None:
    """Vẽ toàn bộ chú cá vàng, phụ kiện 3D, hiệu ứng và hạt."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    cx = st.size / 2.0
    cy = st.size / 2.0 + 4.0
    th = st.theme
    outline = QColor(th["outline"])
    body_col = QColor(th["body"])
    hi_col = QColor(th["highlight"])
    shade_col = QColor(th["shade"])
    ventral_col = QColor(th["ventral"])
    blush_col = QColor(th["blush"])
    spike_col = QColor(th["spike"])

    # Chiều sâu 3D: 0.85x (lặn sâu) -> 1.10x (sát mặt kính), kết hợp dive_scale (Boss Key)
    depth_scale = (0.85 + 0.25 * max(0.0, min(1.0, st.depth))) * max(0.15, st.dive_scale)

    cage_visible = (st.cage_mode in ("caged", "breaking_out")) and (st.cage_opacity > 0.01)
    cage_drop_p = max(0.0, min(1.0, st.cage_drop_progress))
    if cage_drop_p < 0.72:
        t_drop = cage_drop_p / 0.72
        cage_drop_y = -22.0 * (1.0 - t_drop * t_drop)
        cage_drop_alpha = min(1.0, cage_drop_p * 2.6)
    else:
        t_bnc = (cage_drop_p - 0.72) / 0.28
        cage_drop_y = math.sin(t_bnc * math.pi) * 3.5
        cage_drop_alpha = 1.0
    cage_eff_alpha = st.cage_opacity * cage_drop_alpha

    # Độ nhún bơi nhẹ không trọng lực (khi bị giam thì nhún cực nhẹ, khi bám thanh sắt thì cố định)
    if cage_visible and (st.cage_pleading or st.cage_mode == "breaking_out"):
        bob_y = 0.0
    elif cage_visible:
        bob_y = math.sin(st.t_sec * 1.9) * 1.8
    elif st.surfing_waterline:
        # Nhấp nhô mặt nước theo nhịp sin(time * 4) * 3px khi lướt trên thanh tiêu đề cửa sổ
        bob_y = math.sin(st.t_sec * 4.0) * 3.0
    elif st.expression == "play_dead":
        bob_y = math.sin(st.t_sec * 1.35) * 3.0
    else:
        bob_y = math.sin(st.t_sec * (2.6 if st.expression not in ("sleep", "belly_up") else 1.5)) * 3.2

    jitter_x = 0.0
    jitter_y = 0.0
    if st.expression == "muscle_strain":
        amp = 1.6 + 2.2 * st.muscular_level
        jitter_x = math.sin(st.t_sec * 58.0) * amp
        jitter_y = math.cos(st.t_sec * 51.0) * amp
    elif st.expression in ("puffed", "panic", "grumpy", "sneeze_windup", "nauseous") or st.boiling:
        amp = 2.0 if st.expression in ("panic", "sneeze_windup") else 1.15
        jitter_x = math.sin(st.t_sec * 42.0) * amp
        jitter_y = math.cos(st.t_sec * 37.0) * amp

    # --- 1. Bóng đổ tiếp xúc (Contact Shadow) ---
    # Ẩn hoàn toàn khi bơi lơ lửng giữa màn hình; chỉ hiện hình elip ngang cố định (không xoay theo cá)
    # khi cá bơi sát đáy màn hình (Taskbar) hoặc đậu/lướt gần mép trên cửa sổ ứng dụng!
    if cage_visible:
        p.save()
        p.setOpacity(0.55 * cage_eff_alpha)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(25, 38, 52, 82))
        p.drawEllipse(QRectF(cx - 50.0, cy + 58.0, 100.0, 14.0))
        p.restore()
    elif st.contact_shadow > 0.01 and not st.peeking_window:
        prox = max(0.0, min(1.0, st.contact_shadow))
        # Càng sát bề mặt: bóng càng đậm, rõ và thu nhỏ sắc nét; bay cao lên: lan rộng mờ dần rồi mất
        shadow_alpha = int(112 * (prox ** 1.25))
        shadow_w = (72.0 - 22.0 * prox) * (1.0 + st.puff_factor * 0.35 + st.chubby_factor * 0.14) * depth_scale
        shadow_h = (12.0 - 3.5 * prox) * depth_scale
        sy = st.contact_shadow_y if st.contact_shadow_y > 0.0 else (cy + 40.0 * depth_scale)
        sy = max(cy + 26.0 * depth_scale, min(st.size - shadow_h * 0.6 - 2.0, sy))
        p.save()
        p.translate(cx, sy)
        p.scale(1.0, max(0.12, shadow_h / max(1.0, shadow_w)))
        grad_sh = QRadialGradient(QPointF(0.0, 0.0), shadow_w * 0.5)
        grad_sh.setColorAt(0.0, QColor(22, 34, 48, shadow_alpha))
        grad_sh.setColorAt(0.65, QColor(28, 46, 66, int(shadow_alpha * 0.55)))
        grad_sh.setColorAt(1.0, QColor(28, 46, 66, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad_sh)
        p.drawEllipse(QPointF(0.0, 0.0), shadow_w * 0.5, shadow_w * 0.5)
        p.restore()

    # --- 2. Hiệu ứng nước sôi (CPU cao) phía sau ---
    if st.boiling:
        p.save()
        glow = QRadialGradient(QPointF(cx, cy), 72.0)
        pulse = 0.75 + 0.25 * math.sin(st.t_sec * 10.0)
        glow.setColorAt(0.0, QColor(255, 110, 70, int(75 * pulse)))
        glow.setColorAt(0.65, QColor(255, 160, 90, int(35 * pulse)))
        glow.setColorAt(1.0, QColor(255, 160, 90, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), 72.0, 72.0)
        p.restore()

    # --- 3. Xoáy nước Cursor Wake ---
    if st.vortex_alpha > 0.02:
        p.save()
        p.translate(cx, cy)
        p.rotate((st.t_sec * 520.0) % 360.0)
        p.setOpacity(st.vortex_alpha * 0.92)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for ring_i in range(3):
            r = 40.0 + ring_i * 11.5
            p.setPen(QPen(QColor(72, 202, 245, 235 - ring_i * 40), 3.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(QRectF(-r, -r, r * 2, r * 2), ring_i * 110 * 16, 145 * 16)
        p.restore()

    # --- 4. Nửa sau Lồng Sắt (vẽ phía sau chú cá tạo chiều sâu 3D) ---
    if cage_visible:
        p.save()
        p.setOpacity(cage_eff_alpha)
        p.translate(cx, cy + cage_drop_y)
        p.translate(0.0, -76.0)
        p.rotate(st.cage_swing_deg)
        p.translate(0.0, 76.0)
        _draw_cage_back(p)
        p.restore()

    # --- 5. Chú Cá Vàng (thân, vây, đuôi, mặt, phụ kiện) ---
    p.save()
    # Khi đang lướt dọc mặt nước thanh tiêu đề, cắt phẳng phần bụng dưới chìm ~8–12px dưới mép cửa sổ
    if st.surfing_waterline and st.surf_waterline_y > 0.0:
        p.setClipRect(QRectF(0.0, 0.0, float(st.size), st.surf_waterline_y + 1.5))
    if cage_visible:
        # Đồng bộ chuyển động lắc con lắc (±3°) của cá cùng chiếc lồng
        p.translate(cx, cy)
        p.translate(0.0, -76.0)
        p.rotate(st.cage_swing_deg)
        p.translate(jitter_x, 76.0 + bob_y + jitter_y)
    else:
        # Hiệu ứng lắc đầu qua lại khi no căng từ chối ăn (SHAKE_HEAD_FULL)
        shake_dx = math.sin(st.full_shake_t * 25.0) * 8.0 if st.full_shake_t >= 0.0 else 0.0
        p.translate(cx + jitter_x + shake_dx, cy + bob_y + jitter_y)

    # Nếu đang ngó trên thanh tiêu đề cửa sổ, cắt phẳng phần bụng dưới để trông như đang thò đầu qua mép!
    if st.peeking_window:
        p.setClipRect(QRectF(-st.size / 2, -st.size / 2, st.size, st.size / 2 + 15.0))

    # Góc nghiêng bơi + banking quán tính + xoay vòng xoáy/backflip + lắc đầu no căng / lắc nhẹ khi chết đói
    peek_tilt = -4.0 * st.direction if st.peeking_window else 0.0
    shake_rot = math.sin(st.full_shake_t * 25.0) * 10.0 if st.full_shake_t >= 0.0 else 0.0
    dead_rock = math.sin(st.t_sec * 1.9) * 6.0 if st.starved_dead else 0.0
    total_rot = st.pitch_deg + st.bank_deg + st.spin_deg + peek_tilt + shake_rot + dead_rock
    p.rotate(total_rot)

    # Lớp 3: Chuyển cảnh quay đầu mượt (~140ms) đi qua góc nhìn chính diện (Front View)
    eff_dir = st.direction
    eff_front = st.facing_front
    turn_scale_x = 1.0
    turn_face_shift = 0.0
    if 0.0 <= st.turn_progress < 1.0 and not cage_visible and st.puff_factor < 0.2:
        tp = st.turn_progress
        if tp < 0.35:
            # Pha 1: Nghiêng người thu hẹp nhẹ về phía mặt chính diện
            u = tp / 0.35
            eff_dir = st.turn_from_dir
            eff_front = False
            turn_scale_x = 1.0 - 0.34 * u
        elif tp < 0.65:
            # Pha 2: Đi ngang qua Front View nhìn thẳng về phía người dùng
            mid = (tp - 0.35) / 0.30
            eff_dir = st.direction
            eff_front = True
            turn_scale_x = 0.72 + math.sin(mid * math.pi) * 0.24
            # Mặt lướt nhẹ theo chiều quay để cảm giác quay đầu 3D rõ nét
            turn_face_shift = (mid - 0.5) * 10.0 * (-1.0 if st.direction > 0 else 1.0)
        else:
            # Pha 3: Mở thân mượt sang hướng mới
            u = (tp - 0.65) / 0.35
            eff_dir = st.direction
            eff_front = False
            turn_scale_x = 0.66 + 0.34 * u

    # Lật ngang: thiết kế gốc quay TRÁI (direction = -1), quay PHẢI thì lật X = -1
    flip_x = -1.0 if eff_dir > 0 else 1.0
    # Lật ngửa bụng (belly_up hoặc starved_dead)
    flip_y = -1.0 if (st.belly_up or st.starved_dead) else 1.0
    # Hiệu ứng béo tròn khi ăn no (chubby_factor) hoặc phình bụng nhẹ khi no căng (scaleX = 1.08)
    full_sx = 1.08 if st.full_shake_t >= 0.0 else 1.0
    full_sy = 1.04 if st.full_shake_t >= 0.0 else 1.0
    chubby_x = (1.0 + 0.14 * st.chubby_factor) * full_sx
    chubby_y = (1.0 + 0.20 * st.chubby_factor) * full_sy
    p.scale(
        flip_x * depth_scale * st.squash_x * chubby_x * turn_scale_x,
        flip_y * depth_scale * st.squash_y * chubby_y,
    )

    # Quy đổi vector liếc con ngươi (pupil_x, pupil_y) từ tọa độ màn hình sang hệ trục cục bộ của cá
    rad_inv = math.radians(-(total_rot + (st.cage_swing_deg if cage_visible else 0.0)))
    cos_i = math.cos(rad_inv)
    sin_i = math.sin(rad_inv)
    local_pupil_x = (st.pupil_x * cos_i - st.pupil_y * sin_i) * flip_x
    local_pupil_y = (st.pupil_x * sin_i + st.pupil_y * cos_i) * flip_y

    # Hệ số phồng cá nóc (1.0 -> 1.62) hoặc hơi gồng to cơ bắp khi phá lồng
    puff = st.puff_factor
    body_scale = 1.0 + 0.62 * puff + (0.07 * st.muscular_level if st.expression == "muscle_strain" else 0.0)

    # Đồng bộ biên độ & pha vẫy đuôi với lực đẩy Tail-Beat Impulse
    if st.expression in ("panic", "puffed", "muscle_strain"):
        wag_amp = 9.5
        phase = st.t_sec * 24.0
    elif st.expression in ("happy", "love", "proud"):
        wag_amp = 8.4
        phase = st.tail_phase * 1.4 + st.t_sec * 6.0
    elif st.expression in ("play_dead", "starved_dead"):
        wag_amp = 0.7
        phase = st.t_sec * 1.0
    elif st.expression in ("sleep", "belly_up", "caged_sad"):
        wag_amp = 1.8
        phase = st.t_sec * 1.8
    elif st.expression in ("pleading", "hungry_beg"):
        wag_amp = 3.0
        phase = st.t_sec * 4.8
    else:
        wag_amp = 4.5 + st.swim_speed * 5.2
        phase = st.tail_phase
    tail_wag = math.sin(phase) * wag_amp
    fin_wag = math.sin(phase - 0.7) * (wag_amp * 0.48)

    pen_outline = QPen(outline, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    # Lớp hào quang viền ngoài cực mỏng (Outer Glow / Rim Light ~2.5px, opacity ~15%)
    # giúp chú cá tách bạch mềm mại trên cả nền đen (Dark Mode) lẫn nền trắng
    glow_tint = QColor(hi_col)

    def _draw_rim_glow(path: QPainterPath) -> None:
        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        c_outer = QColor(glow_tint.red(), glow_tint.green(), glow_tint.blue(), 22)
        c_inner = QColor(glow_tint.red(), glow_tint.green(), glow_tint.blue(), 38)
        p.setPen(QPen(c_outer, 8.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(c_inner, 5.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)
        p.restore()

    # --- 5a. Layer Vây lưng tách riêng (uốn lượn nhẹ theo hàm sin) ---
    p.save()
    p.scale(body_scale, body_scale)
    dorsal_rot = math.sin(phase - 0.85) * 5.2
    p.save()
    p.translate(0.0, -23.0)
    p.rotate(dorsal_rot)
    p.translate(0.0, 23.0)
    dorsal = QPainterPath()
    dorsal.moveTo(-17, -25)
    dorsal.cubicTo(-10, -40, 8, -46 + fin_wag * 0.45, 17, -40 + fin_wag * 0.5)
    dorsal.cubicTo(20, -37 + fin_wag * 0.45, 16, -32 + fin_wag * 0.3, 12, -32 + fin_wag * 0.25)
    # Múi nhỏ thứ 2 ngay dưới múi chính
    dorsal.cubicTo(19, -31 + fin_wag * 0.3, 19, -24 + fin_wag * 0.2, 11, -22)
    dorsal.lineTo(-15, -21)
    dorsal.closeSubpath()

    _draw_rim_glow(dorsal)
    p.setPen(pen_outline)
    p.setBrush(body_col)
    p.drawPath(dorsal)

    # Highlight vây lưng & nét gân đậm nhỏ bên trong
    p.setPen(QPen(hi_col, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(-8, -32), QPointF(10, -38 + fin_wag * 0.35))
    p.setPen(QPen(outline, 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(-1, -29), QPointF(6, -34 + fin_wag * 0.25))
    p.restore()

    # Múi tròn nhỏ riêng lẻ phía sau lưng (đặc trưng trong ảnh mẫu)
    p.save()
    p.translate(22, -20 + fin_wag * 0.25)
    p.rotate(32 + dorsal_rot * 0.6)
    lobe = QPainterPath()
    lobe.addEllipse(QRectF(-5.5, -5.0, 11.0, 10.0))
    _draw_rim_glow(lobe)
    p.setPen(pen_outline)
    p.setBrush(body_col)
    p.drawPath(lobe)
    p.restore()

    # --- 5b. Vây bụng nhỏ phía dưới-sau ---
    ventral = QPainterPath()
    ventral.moveTo(10, 24)
    ventral.cubicTo(15, 34 + fin_wag * 0.3, 25, 36 + fin_wag * 0.4, 28, 30 + fin_wag * 0.3)
    ventral.cubicTo(25, 26, 23, 21, 22, 18)
    ventral.closeSubpath()
    _draw_rim_glow(ventral)
    p.setPen(pen_outline)
    p.setBrush(ventral_col)
    p.drawPath(ventral)
    p.setPen(QPen(outline, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(17, 26), QPointF(23, 29 + fin_wag * 0.2))
    p.restore()

    # --- 5c. Gai cá nóc nhỏ xung quanh khi phồng mang ---
    if puff > 0.15:
        p.save()
        p.setOpacity(min(1.0, (puff - 0.15) * 1.4))
        p.setPen(QPen(outline, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(spike_col)
        r_sp = 32.5 * body_scale
        for i in range(10):
            ang = i * (math.tau / 10.0) + 0.18
            # Chừa vị trí mặt trước & gốc đuôi
            if abs(math.sin(ang)) < 0.35 and math.cos(ang) > 0.6:
                continue
            bx = -2.0 + math.cos(ang) * r_sp
            by = math.sin(ang) * (r_sp * 0.95)
            tip_x = -2.0 + math.cos(ang) * (r_sp + 7.5 * puff)
            tip_y = math.sin(ang) * (r_sp * 0.95 + 7.5 * puff)
            perp_x = -math.sin(ang) * 4.2
            perp_y = math.cos(ang) * 4.2
            tri = QPolygonF([
                QPointF(bx + perp_x, by + perp_y),
                QPointF(tip_x, tip_y),
                QPointF(bx - perp_x, by - perp_y),
            ])
            p.drawPolygon(tri)
        p.restore()

    # --- 5d-1. Layer Vây Đuôi tách riêng (xoay vẫy nhẹ theo hàm sin ±10° quanh khớp đuôi) ---
    if puff > 0.45:
        tail_len = 0.22
    elif cage_visible:
        tail_len = 0.62
    elif eff_front:
        tail_len = 0.45
    else:
        tail_len = 1.0

    r_x = 32.5 * body_scale
    r_y = 30.8 * body_scale
    tx0 = 26.5 * body_scale
    tail_span = 26.5 * tail_len
    tail_mid = 19.5 * tail_len

    # Góc vẫy đuôi mềm mại theo hàm sin (±10° khi bơi bình thường)
    if st.expression == "play_dead":
        tail_swing_amp = 1.6
    elif st.expression in ("sleep", "belly_up", "caged_sad"):
        tail_swing_amp = 3.5
    elif st.expression in ("panic", "puffed", "muscle_strain"):
        tail_swing_amp = 13.5
    else:
        tail_swing_amp = 8.5 + st.swim_speed * 2.5  # ~±8.5° đến ±11°
    tail_rot_deg = math.sin(phase) * tail_swing_amp

    p.save()
    p.translate(tx0, 2.0 * body_scale)
    p.rotate(tail_rot_deg)
    tail_path = QPainterPath()
    tail_path.moveTo(-4.0, -7.5 * body_scale)
    tail_path.cubicTo(
        8.0 * tail_len, -13.0,
        tail_span - 5.0, -24.5,
        tail_span, -15.0,
    )
    tail_path.cubicTo(
        tail_span + 3.0 * tail_len, -7.0,
        tail_mid + 1.0, -2.5,
        tail_mid, 1.0,
    )
    tail_path.cubicTo(
        tail_span + 1.5 * tail_len, 9.5,
        tail_span - 1.5, 20.5,
        tail_span - 9.0 * tail_len, 20.5,
    )
    tail_path.cubicTo(
        9.0 * tail_len, 18.0,
        4.0 * tail_len, 9.5 * body_scale,
        -4.0, 8.0 * body_scale,
    )
    tail_path.closeSubpath()

    _draw_rim_glow(tail_path)
    p.setPen(pen_outline)
    p.setBrush(body_col)
    p.drawPath(tail_path)

    # Các tia gân ngắn đặc trưng xoay đồng bộ theo layer đuôi
    if not eff_front:
        p.setPen(QPen(outline, 2.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for ry_off in (-7.0, -1.5, 4.0, 9.5):
            p.drawLine(QPointF(8.0 * tail_len, ry_off * 0.55), QPointF(17.5 * tail_len, ry_off * 1.18))
    p.restore()

    # --- 5d-2. Layer Thân tròn mềm mại (Outer Glow + bóng cam + highlight trán thở nhịp) ---
    body_path = QPainterPath()
    body_path.moveTo(tx0 + 2.0, -5.5 * body_scale)
    body_path.cubicTo(
        tx0 + 3.5, 1.5 * body_scale,
        tx0 + 2.5, 7.5 * body_scale,
        tx0 + 0.5, 9.5 * body_scale,
    )
    body_path.cubicTo(
        18.0 * body_scale, r_y * 1.02,
        -21.0 * body_scale, r_y * 1.05,
        -r_x - 2.0, 12.0 * body_scale,
    )
    body_path.cubicTo(
        -r_x - 5.5, -9.0 * body_scale,
        -21.0 * body_scale, -r_y * 1.05,
        2.0 * body_scale, -r_y * 1.02,
    )
    body_path.cubicTo(
        20.0 * body_scale, -r_y * 0.96,
        tx0 + 1.0, -15.0 * body_scale,
        tx0 + 2.0, -5.5 * body_scale,
    )
    body_path.closeSubpath()

    # Hào quang mỏng (Rim Light) bao quanh thân
    _draw_rim_glow(body_path)

    # Tô màu nền thân
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(body_col)
    p.drawPath(body_path)

    # Cắt clip trong thân để tô bóng cam ấm phía bụng & ánh sáng trên trán
    p.save()
    p.setClipPath(body_path, Qt.ClipOperation.IntersectClip)
    # Bóng cam ấm phía dưới-sau thân (giống ảnh mẫu)
    shade_path = QPainterPath()
    shade_path.addEllipse(QRectF(-r_x - 6, -r_y - 4, r_x * 2 + 8, r_y * 2 + 4))
    inner_cut = QPainterPath()
    inner_cut.addEllipse(QRectF(-r_x - 10, -r_y - 10, r_x * 2 + 4, r_y * 2 + 1))
    crescent_shade = shade_path.subtracted(inner_cut)
    p.setBrush(shade_col)
    p.drawPath(crescent_shade)

    # Dải sáng kem + ánh sáng lấp lánh trên trán dao động độ mờ nhẹ theo chu kỳ nhịp thở
    breath_op = 0.58 + 0.42 * math.sin(st.t_sec * 2.2)
    p.save()
    p.setOpacity(breath_op)
    p.setPen(QPen(hi_col, 4.3 * body_scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(
        QRectF(-r_x + 2, -r_y + 3, r_x * 1.75, r_y * 1.55),
        52 * 16,
        105 * 16,
    )
    # Chấm highlight trắng bóng mềm trên đỉnh trán tạo khối tròn mọng nước
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 248, 170))
    p.save()
    p.translate(-12.5 * body_scale, -19.5 * body_scale)
    p.rotate(-24.0)
    p.drawEllipse(QRectF(-7.5 * body_scale, -3.2 * body_scale, 15.0 * body_scale, 6.4 * body_scale))
    p.restore()
    p.restore()

    # Ánh sáng khúc xạ (Caustics) chớp nhẹ như nắng xuyên qua mặt nước
    caustic_pulse = 0.55 + 0.45 * math.sin(st.t_sec * 3.1)
    caustic_shift = math.sin(st.t_sec * 1.7) * 9.0
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 232, int(48 * caustic_pulse)))
    c1 = QPainterPath()
    c1.moveTo(-22 * body_scale + caustic_shift, -30 * body_scale)
    c1.cubicTo(-10 * body_scale + caustic_shift, -14 * body_scale, -26 * body_scale + caustic_shift, 4 * body_scale, -8 * body_scale + caustic_shift, 18 * body_scale)
    c1.lineTo(-1 * body_scale + caustic_shift, 18 * body_scale)
    c1.cubicTo(-18 * body_scale + caustic_shift, 4 * body_scale, -2 * body_scale + caustic_shift, -14 * body_scale, -14 * body_scale + caustic_shift, -30 * body_scale)
    c1.closeSubpath()
    p.drawPath(c1)

    p.setBrush(QColor(255, 255, 238, int(36 * (1.2 - caustic_pulse * 0.5))))
    c2 = QPainterPath()
    c2.moveTo(4 * body_scale - caustic_shift * 0.6, -30 * body_scale)
    c2.cubicTo(14 * body_scale - caustic_shift * 0.6, -12 * body_scale, 2 * body_scale - caustic_shift * 0.6, 4 * body_scale, 16 * body_scale - caustic_shift * 0.6, 16 * body_scale)
    c2.lineTo(22 * body_scale - caustic_shift * 0.6, 16 * body_scale)
    c2.cubicTo(8 * body_scale - caustic_shift * 0.6, 4 * body_scale, 20 * body_scale - caustic_shift * 0.6, -12 * body_scale, 10 * body_scale - caustic_shift * 0.6, -30 * body_scale)
    c2.closeSubpath()
    p.drawPath(c2)

    # Mặt hơi tái nhợt nhẹ khi đang giả chết (hết pin / xỉu ngang)
    if st.expression == "play_dead":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(225, 236, 245, 58))
        p.drawEllipse(QRectF(-r_x - 4, -r_y - 4, r_x * 2 + 8, r_y * 2 + 8))

    # Mặt tái xanh lè khi buồn nôn cầu vồng (Post-Dizzy)
    if st.expression in ("nauseous", "belly_up"):
        g_alpha = 135 if st.expression == "nauseous" else 85
        sick_grad = QRadialGradient(QPointF(-10 * body_scale, -8 * body_scale), 38 * body_scale)
        sick_grad.setColorAt(0.0, QColor(125, 224, 118, g_alpha))
        sick_grad.setColorAt(0.7, QColor(145, 232, 130, int(g_alpha * 0.45)))
        sick_grad.setColorAt(1.0, QColor(145, 232, 130, 0))
        p.setBrush(sick_grad)
        p.drawEllipse(QRectF(-r_x - 4, -r_y - 4, r_x * 2 + 8, r_y * 2 + 8))

    # Mặt đỏ bừng quyết tâm khi gồng lực sĩ bẻ thanh sắt!
    if st.expression == "muscle_strain" and st.muscular_level > 0.05:
        r_alpha = int(145 * min(1.0, st.muscular_level))
        rage_grad = QRadialGradient(QPointF(0.0, -6.0 * body_scale), 42.0 * body_scale)
        rage_grad.setColorAt(0.0, QColor(255, 58, 48, r_alpha))
        rage_grad.setColorAt(0.65, QColor(255, 85, 58, int(r_alpha * 0.55)))
        rage_grad.setColorAt(1.0, QColor(255, 85, 58, 0))
        p.setBrush(rage_grad)
        p.drawEllipse(QRectF(-r_x - 4, -r_y - 4, r_x * 2 + 8, r_y * 2 + 8))

    p.restore()

    # Vẽ viền outline đậm mượt bao quanh thân cá (giữ nguyên viền nâu tím đậm đặc trưng)
    p.setPen(pen_outline)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(body_path)

    # --- 5e. Chăn rong biển (sau 23:30 đêm) ---
    if st.seaweed_blanket:
        _draw_seaweed_blanket(p, body_scale, st.t_sec, outline)

    # --- 5f. Khuôn mặt biểu cảm (kèm con ngươi độc lập & dịch mặt khi quay đầu) ---
    _draw_fish_face(
        p,
        st,
        body_scale,
        outline,
        body_col,
        blush_col,
        eff_front=eff_front,
        face_shift_x=turn_face_shift,
        local_pupil_x=local_pupil_x,
        local_pupil_y=local_pupil_y,
    )

    # --- 5g. Luồng hút thức ăn / file vào miệng ---
    if st.suction_alpha > 0.02:
        p.save()
        p.setOpacity(st.suction_alpha)
        mouth_x = -14.8 * body_scale if not eff_front else 0.0
        mouth_y = 9.8 * body_scale
        # Vòng tâm hút sáng quanh miệng báo hiệu vùng thả file
        pulse = 1.0 + math.sin(st.t_sec * 12.0) * 0.14
        ring_col = QColor(255, 196, 61, 220) if st.mouth_locked else QColor(115, 225, 255, 195)
        p.setPen(QPen(ring_col, 2.4, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        rr = (17.0 if st.mouth_locked else 14.0) * pulse
        p.drawEllipse(QPointF(mouth_x, mouth_y + 1.0), rr, rr)

        # Các tia gió hút xoáy chụm vào miệng
        line_base = QColor(255, 220, 120) if st.mouth_locked else QColor(135, 228, 255)
        for i in range(5):
            prog = ((st.t_sec * 3.8 + i * 0.2) % 1.0)
            dist = 48.0 * (1.0 - prog)
            spread = (i - 2.0) * 10.5 * (1.0 - prog)
            alpha_line = int(240 * (1.0 - abs(prog - 0.5) * 1.6))
            c = QColor(line_base.red(), line_base.green(), line_base.blue(), max(25, alpha_line))
            p.setPen(QPen(c, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(
                QPointF(mouth_x - dist - 12, mouth_y + spread),
                QPointF(mouth_x - dist, mouth_y + spread * 0.55),
            )
        p.restore()

    # --- 5h. Mũ bong bóng nước (Pomodoro Break) ---
    if st.water_helmet:
        _draw_water_helmet(p, body_scale, st.t_sec)

    # --- 5i. Vòng sao chóng mặt quanh đầu ---
    if st.expression in ("dizzy", "nauseous", "belly_up"):
        for i in range(3):
            ang = st.t_sec * 5.2 + i * (math.tau / 3.0)
            sx = -6.0 + math.cos(ang) * 26.0 * body_scale
            sy = -36.0 * body_scale + math.sin(ang) * 6.5
            _draw_star(p, sx, sy, 8.5, QColor("#fff3a3"))

    # Hai chiếc vây nhỏ bám mép trên cửa sổ khi đang ngó (Window Peeking)
    if st.peeking_window:
        p.setPen(pen_outline)
        p.setBrush(ventral_col)
        p.drawEllipse(QRectF(-25.0, 5.5, 13.0, 8.5))
        p.drawEllipse(QRectF(12.0, 5.5, 13.0, 8.5))

    # Cử chỉ đưa vây trước chỉ vào miệng đòi ăn khi Đói (POINT_TO_MOUTH)
    if st.point_to_mouth > 0.05 and not cage_visible and not st.starved_dead:
        _draw_pointing_fin(p, body_scale, eff_front, st.point_to_mouth, body_col, ventral_col, outline, st.t_sec)

    # Gân quyết tâm nổi trên trán khi gồng lực sĩ phá lồng
    if st.expression == "muscle_strain" and st.muscular_level > 0.2:
        vein_pulse = 1.0 + math.sin(st.t_sec * 24.0) * 0.16
        _draw_anger_mark(p, 19.0 * body_scale, -17.0 * body_scale, 13.5 * vein_pulse, QColor("#d90429"))

    p.restore()  # Kết thúc biến đổi thân cá

    # --- 5i-b. Nửa trước Lồng Sắt + Vây bám thanh sắt (Van xin) / Cánh tay lực sĩ (Bẻ sắt) ---
    if cage_visible:
        p.save()
        p.setOpacity(cage_eff_alpha)
        p.translate(cx, cy + cage_drop_y)
        p.translate(0.0, -76.0)
        p.rotate(st.cage_swing_deg)
        p.translate(0.0, 76.0)

        _draw_cage_front(p, st.cage_bend_amount, cage_drop_p, st.t_sec)

        # Vây trước bám chặt 2 thanh sắt (Van xin) hoặc Tay cơ bắp lực sĩ bẻ thanh sắt!
        if cage_drop_p >= 0.85:
            if st.cage_mode == "breaking_out" and st.muscular_level > 0.05:
                _draw_cage_muscular_arms(
                    p,
                    st.cage_bend_amount,
                    st.muscular_level,
                    body_col,
                    hi_col,
                    shade_col,
                    outline,
                    st.t_sec,
                )
            elif st.cage_pleading:
                _draw_cage_pleading_fins(p, body_col, shade_col, outline, st.t_sec)
        p.restore()

    # --- 5i-c. Vệt sóng rẽ nước hình chữ V (Wake Ripples) khi bơi dọc thanh tiêu đề cửa sổ ---
    if st.surfing_waterline and st.surf_waterline_y > 0.0:
        _draw_surf_wake_ripples(p, cx, st.surf_waterline_y, st.direction, st.surf_speed, depth_scale, st.t_sec)

    # --- 5j. Biểu tượng tệp/thư mục bị hút xoáy trực tiếp vào miệng cá ---
    if 0.0 <= st.eating_file_progress <= 1.0:
        prog = st.eating_file_progress
        ease = prog * prog  # tăng tốc dần khi lao vào miệng
        mouth_screen_x = cx + (14.8 if st.direction > 0 else -14.8) * depth_scale
        mouth_screen_y = cy + bob_y + 10.0 * depth_scale
        sx0, sy0 = st.eating_file_start
        fx = sx0 + (mouth_screen_x - sx0) * ease
        fy = sy0 + (mouth_screen_y - sy0) * ease - math.sin(prog * math.pi) * 12.0
        fscale = max(0.08, 1.0 - ease * 0.92)
        frot = prog * 300.0 * (-st.direction)
        _draw_eaten_file_icon(p, fx, fy, fscale, frot, st.eating_file_is_dir)

    # --- 6. Vòng hào quang thiên thần khi Giả chết ---
    if st.expression == "play_dead":
        _draw_angel_halo(p, cx, cy + bob_y - 46.0 * depth_scale, depth_scale, st.t_sec)

    # --- 7. Hạt hiệu ứng (không bị lật ngang để chữ Z / ! / hồn ma luôn đúng chiều) ---
    for pt in st.particles:
        alpha = max(0.0, min(1.0, pt.life / pt.max_life))
        p.save()
        p.setOpacity(alpha)
        if pt.kind == "heart":
            _draw_heart(p, pt.x, pt.y, pt.size, pt.color)
        elif pt.kind == "ghost":
            _draw_mini_ghost(p, pt.x, pt.y, pt.size, pt.color)
        elif pt.kind == "zzz":
            p.setFont(QFont("Sans Serif", int(pt.size), QFont.Weight.Bold))
            p.setPen(pt.color)
            p.drawText(QPointF(pt.x, pt.y), "Z")
        elif pt.kind == "excl":
            p.setFont(QFont("Sans Serif", int(pt.size), QFont.Weight.Black))
            p.setPen(pt.color)
            p.drawText(QPointF(pt.x, pt.y), "!")
        elif pt.kind == "anger":
            _draw_anger_mark(p, pt.x, pt.y, pt.size, pt.color)
        elif pt.kind == "sweat":
            _draw_sweat_drop(p, pt.x, pt.y, pt.size, pt.color)
        elif pt.kind == "star":
            _draw_star(p, pt.x, pt.y, pt.size, pt.color)
        elif pt.kind == "crumb":
            p.translate(pt.x, pt.y)
            p.rotate((st.frame * 12 + int(pt.size * 20)) % 360)
            p.setPen(QPen(QColor("#3b182c"), 1.2))
            p.setBrush(pt.color)
            p.drawRoundedRect(QRectF(-pt.size * 0.5, -pt.size * 0.35, pt.size, pt.size * 0.7), 1.5, 1.5)
        elif pt.kind == "water_drop":
            _draw_sweat_drop(p, pt.x, pt.y, pt.size, pt.color)
        elif pt.kind == "trail_bubble":
            # Đuôi bong bóng động: scale-up nhẹ khi tan dần (fade-out)
            grow = 1.0 + (1.0 - alpha) * 0.75
            rad = pt.size * 0.5 * grow
            p.setPen(QPen(QColor(255, 255, 255, int(215 * alpha)), 1.3))
            p.setBrush(pt.color)
            p.drawEllipse(QPointF(pt.x, pt.y), rad, rad)
        elif pt.kind == "rainbow_bubble":
            rad = pt.size * 0.5 * (1.0 + (1.0 - alpha) * 0.35)
            p.setPen(QPen(QColor(255, 255, 255, 235), 1.6))
            p.setBrush(pt.color)
            p.drawEllipse(QPointF(pt.x, pt.y), rad, rad)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QPointF(pt.x - rad * 0.35, pt.y - rad * 0.35), rad * 0.28, rad * 0.28)
        elif pt.kind == "spark":
            # Tia lửa kim loại bắn tóe sáng rực theo hướng vận tốc
            ang = math.atan2(pt.vy, pt.vx)
            length = max(5.0, pt.size * (0.7 + 0.6 * alpha))
            x2 = pt.x - math.cos(ang) * length
            y2 = pt.y - math.sin(ang) * length
            p.setPen(QPen(pt.color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(pt.x, pt.y), QPointF(x2, y2))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(pt.x, pt.y), 2.0, 2.0)
        elif pt.kind == "smoke":
            # Khói bụi mềm phình to rồi tan dần
            rad = pt.size * (0.65 + (1.0 - alpha) * 0.9)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(pt.color)
            p.drawEllipse(QPointF(pt.x, pt.y), rad, rad * 0.85)
        elif pt.kind == "tear":
            _draw_sweat_drop(p, pt.x, pt.y, pt.size, pt.color)
        elif pt.kind in ("bubble", "boil", "puff_air"):
            # Bong bóng động phóng to dần nhẹ khi trôi lên rồi mờ đi (alpha -> 0)
            grow = 1.0 + (1.0 - alpha) * (0.48 if pt.kind == "bubble" else 0.25)
            rad = pt.size * 0.5 * grow
            p.setPen(QPen(QColor(255, 255, 255, int(235 * alpha)), 1.45))
            p.setBrush(pt.color)
            p.drawEllipse(QPointF(pt.x, pt.y), rad, rad)
            # Chấm bóng sáng nhỏ trên bọt
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, int(230 * alpha)))
            p.drawEllipse(QPointF(pt.x - rad * 0.34, pt.y - rad * 0.34), rad * 0.28, rad * 0.28)
        p.restore()




def _draw_seaweed_blanket(p: QPainter, s: float, t_sec: float, outline: QColor) -> None:
    """Chiếc chăn rong biển mềm mại đắp ngang lưng khi quá 23:30 đêm."""
    p.save()
    wave = math.sin(t_sec * 2.2) * 2.5
    blanket = QPainterPath()
    blanket.moveTo(4.0 * s, -28.0 * s)
    blanket.cubicTo(17.0 * s, -29.0 * s, 29.0 * s, -18.0 * s, 31.5 * s, 3.0 * s)
    blanket.cubicTo(29.0 * s, 15.0 * s + wave, 20.0 * s, 22.0 * s - wave, 11.0 * s, 18.0 * s + wave)
    blanket.cubicTo(3.0 * s, 15.0 * s - wave, -1.0 * s, 5.0 * s, 2.0 * s, -12.0 * s)
    blanket.closeSubpath()

    p.setPen(QPen(QColor("#1b4332"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(QColor(64, 186, 118, 228))
    p.drawPath(blanket)

    # Gân lá rong biển
    p.setPen(QPen(QColor("#95d5b2"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(9.0 * s, -16.0 * s), QPointF(21.0 * s, 6.0 * s + wave * 0.5))
    p.drawLine(QPointF(16.0 * s, -17.0 * s), QPointF(26.0 * s, -1.0 * s + wave * 0.3))
    p.restore()


def _draw_water_helmet(p: QPainter, s: float, t_sec: float) -> None:
    """Mũ bong bóng nước trong suốt đội trên đầu khi Pomodoro nghỉ ngơi."""
    p.save()
    hx = -2.0 * s
    hy = -31.0 * s
    wob = math.sin(t_sec * 4.5) * 1.4
    r = 24.0 * s

    grad = QRadialGradient(QPointF(hx - 7, hy - 9), r * 1.45)
    grad.setColorAt(0.0, QColor(245, 254, 255, 225))
    grad.setColorAt(0.55, QColor(115, 225, 255, 165))
    grad.setColorAt(1.0, QColor(42, 175, 245, 215))

    p.setPen(QPen(QColor(55, 185, 240, 240), 2.4))
    p.setBrush(grad)
    p.drawEllipse(QRectF(hx - r, hy - r * 0.82 + wob * 0.5, r * 2.0, r * 1.52))

    # Vệt sáng trên mũ nước
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawEllipse(QRectF(hx - r * 0.55, hy - r * 0.55 + wob * 0.5, 11.5, 6.0))
    # Giọt nước nhỏ lơ lửng quanh mũ
    p.setBrush(QColor(135, 230, 255, 225))
    p.drawEllipse(QPointF(hx + r + 5, hy - 8 + wob), 3.2, 3.2)
    p.drawEllipse(QPointF(hx - r - 4, hy - 4 - wob), 2.5, 2.5)
    p.restore()


