"""Bộ vẽ vector 2D cho linh vật Cá Vàng (Golden Fish) khớp phong cách minh họa.

Hỗ trợ:
- Tạo hình cá vàng tròn trĩnh, vây lưng 2 múi + chấm phụ, đuôi quạt mượt liền thân, má hồng, bọt trắng
- Chiều sâu 3D (scale 0.85x..1.10x + bóng đổ đậm/mờ ngược chiều sâu)
- Toàn bộ trạng thái biểu cảm: swim/idle, happy, love, puffed (cá nóc), dizzy,
  eat/swallow (há miệng hút), panic (hốt hoảng/sôi nước), sleep (ngủ trong bong bóng lớn),
  sleepy (ngáp khuya), shy, curious, grumpy, cautious (dè chừng vùng đỏ/cam)
- Phụ kiện: Mũ bong bóng nước (Pomodoro Break), Chăn rong biển (sau 23:30),
  xoáy nước (Cursor Wake), bong bóng nảy theo nhạc (Audio Equalizer)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)

FISH_THEMES = {
    "Cá Vàng 🐠": {
        "body": "#ffd93b",
        "highlight": "#fff4a3",
        "shade": "#f59b25",
        "ventral": "#ffa82e",
        "outline": "#3b182c",
        "blush": "#f66e5e",
        "spike": "#ffb732",
    },
    "Cá Koi Đỏ 🎏": {
        "body": "#fff8f0",
        "highlight": "#ffffff",
        "shade": "#f26a3d",
        "ventral": "#ff7a45",
        "outline": "#3a1d26",
        "blush": "#ff6b81",
        "spike": "#ff7a45",
    },
    "Cá Xanh Ngọc 🐟": {
        "body": "#63d2ff",
        "highlight": "#ccf2ff",
        "shade": "#2b9cd8",
        "ventral": "#42b5eb",
        "outline": "#1d2d44",
        "blush": "#ff7aa2",
        "spike": "#48bfe3",
    },
    "Cá Hồng Sakura 🌸": {
        "body": "#ffb3c6",
        "highlight": "#ffe5ec",
        "shade": "#fb6f92",
        "ventral": "#ff8fab",
        "outline": "#421d2d",
        "blush": "#ff4d6d",
        "spike": "#ff8fab",
    },
    "Cá Đêm Huyền Bí 🌙": {
        "body": "#5e60ce",
        "highlight": "#a5a8f5",
        "shade": "#3a3ca8",
        "ventral": "#7476e0",
        "outline": "#1a1830",
        "blush": "#ff70a6",
        "spike": "#7b7ee6",
    },
}

# 8 vị trí bọt trắng đặc trưng bay quanh chú cá (giống ảnh mẫu), kiêm 8 cột Equalizer
AMBIENT_BUBBLES = [
    (-46.0, -14.0, 3.6),
    (-50.0, 12.0, 2.3),
    (-35.0, -34.0, 2.6),
    (-14.0, -47.0, 2.8),
    (-6.0, -50.0, 2.0),
    (34.0, -30.0, 3.6),
    (46.0, -18.0, 2.9),
    (60.0, 14.0, 2.6),
]


@dataclass
class Particle:
    kind: str  # bubble | trail_bubble | rainbow_bubble | water_drop | boil | heart | zzz | star | excl | quest | anger | sweat | puff_air | crumb
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    color: QColor


@dataclass
class FishRenderState:
    size: int
    theme: dict[str, str]
    t_sec: float
    frame: int
    direction: int           # -1 = quay trái (mặc định ảnh mẫu), 1 = quay phải
    pitch_deg: float         # góc chúi lên/xuống khi bơi
    spin_deg: float          # góc xoay khi bị xoáy nước hoặc backflip
    depth: float             # 0.0 (lặn sâu 0.85x) .. 1.0 (sát mặt kính 1.10x)
    squash_x: float
    squash_y: float
    puff_factor: float       # 0.0 (bình thường) .. 1.0 (cá nóc phồng to ~1.75x)
    expression: str          # normal | happy | love | proud | puffed | dizzy | nauseous | belly_up | sneeze_windup | sneeze_burst | eat | swallow | panic | sleep | sleepy | shy | curious | grumpy | cautious | peeking
    facing_front: bool
    blink: bool
    look_dx: float           # -1..1 hướng liếc theo chuột (đã chiếu theo hướng cá)
    look_dy: float           # -1..1
    swim_speed: float        # 0..1 tốc độ vẫy đuôi/vây
    in_sleep_bubble: bool
    water_helmet: bool       # mũ bong bóng nước khi Pomodoro Break
    seaweed_blanket: bool    # chăn rong biển sau 23:30
    boiling: bool            # hiệu ứng nước sôi CPU > 85%
    vortex_alpha: float      # 0..1 xoáy nước khi vung chuột nhanh
    suction_alpha: float     # 0..1 luồng hút khi kéo thả file/text vào miệng
    audio_bands: list[float]
    audio_level: float
    particles: list[Particle]
    mouth_locked: bool = False
    eating_file_progress: float = -1.0       # 0..1 file đang bị hút vào miệng, <0 là không có
    eating_file_start: tuple[float, float] = (0.0, 0.0)
    eating_file_is_dir: bool = False
    tail_phase: float = 0.0                  # pha nhịp vẫy đuôi đồng bộ với lực đẩy Tail-Beat
    bank_deg: float = 0.0                    # góc nghiêng quán tính khi cua góc rộng
    chubby_factor: float = 0.0               # 0..1 độ béo tròn khi ăn no
    belly_up: bool = False                   # lật ngửa bụng trôi lờ đờ sau khi nôn cầu vồng
    peeking_window: bool = False             # thò nửa đầu lên trên thanh tiêu đề cửa sổ
    dive_scale: float = 1.0                  # co nhỏ khi lặn sâu ẩn mình (Boss Key)


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

    # Độ nhún bơi nhẹ không trọng lực
    bob_y = math.sin(st.t_sec * (2.6 if st.expression not in ("sleep", "belly_up") else 1.5)) * 3.2
    jitter_x = 0.0
    jitter_y = 0.0
    if st.expression in ("puffed", "panic", "grumpy", "sneeze_windup", "nauseous") or st.boiling:
        amp = 2.0 if st.expression in ("panic", "sneeze_windup") else 1.15
        jitter_x = math.sin(st.t_sec * 42.0) * amp
        jitter_y = math.cos(st.t_sec * 37.0) * amp

    # --- 1. Bóng đổ chiều sâu bên dưới bụng ---
    # Lặn sâu (depth -> 0): bóng đậm, nhỏ gọn sắc nét hơn; nổi sát kính (depth -> 1): bóng mờ dần & rộng hơn
    if not st.in_sleep_bubble and not st.peeking_window and abs(st.spin_deg) < 25.0:
        shadow_alpha = int(105 - 82 * st.depth)  # 105 (sâu) -> 23 (nổi)
        shadow_w = (54.0 + 18.0 * st.depth) * (1.0 + st.puff_factor * 0.45 + st.chubby_factor * 0.16) * depth_scale
        shadow_h = (10.5 + 3.0 * st.depth) * depth_scale
        shadow_y = cy + (34.0 + 14.0 * st.puff_factor + 4.0 * st.chubby_factor) * depth_scale
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(40, 75, 100, max(12, shadow_alpha)))
        p.drawEllipse(QRectF(cx - shadow_w / 2, shadow_y - shadow_h / 2, shadow_w, shadow_h))

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

    # --- 4. Bọt trắng xung quanh chú cá (kiêm Equalizer nảy theo nhạc) ---
    p.save()
    p.translate(cx, cy + bob_y * 0.5)
    p.scale(depth_scale, depth_scale)
    for idx, (bx, by, br) in enumerate(AMBIENT_BUBBLES):
        band = st.audio_bands[idx % len(st.audio_bands)] if st.audio_bands else 0.0
        eq_lift = -band * 18.0 if st.audio_level > 0.02 else math.sin(st.t_sec * 2.1 + idx * 1.1) * 2.6
        eq_scale = 1.0 + band * 0.75 if st.audio_level > 0.02 else 1.0
        draw_x = bx * (-st.direction)
        draw_y = by + eq_lift
        rad = br * eq_scale
        p.setPen(Qt.PenStyle.NoPen)
        if st.audio_level > 0.05:
            # Có nhạc -> bọt sáng ánh xanh ngọc/trắng sống động
            p.setBrush(QColor(225, 252, 255, 235))
        else:
            p.setBrush(QColor(255, 255, 255, 225))
        p.drawEllipse(QPointF(draw_x, draw_y), rad, rad)
    p.restore()

    # --- 5. Chú Cá Vàng (thân, vây, đuôi, mặt, phụ kiện) ---
    p.save()
    p.translate(cx + jitter_x, cy + bob_y + jitter_y)

    # Nếu đang ngó trên thanh tiêu đề cửa sổ, cắt phẳng phần bụng dưới để trông như đang thò đầu qua mép!
    if st.peeking_window:
        p.setClipRect(QRectF(-st.size / 2, -st.size / 2, st.size, st.size / 2 + 15.0))

    # Góc nghiêng bơi + banking quán tính + xoay vòng xoáy/backflip
    curious_tilt = -12.0 * st.direction if st.expression == "curious" else (-4.0 * st.direction if st.peeking_window else 0.0)
    total_rot = st.pitch_deg + st.bank_deg + st.spin_deg + curious_tilt
    p.rotate(total_rot)

    # Lật ngang: thiết kế gốc quay TRÁI (direction = -1), quay PHẢI thì lật X = -1
    flip_x = -1.0 if st.direction > 0 else 1.0
    # Lật ngửa bụng (belly_up) sau khi nôn cầu vồng
    flip_y = -1.0 if st.belly_up else 1.0
    # Hiệu ứng béo tròn khi ăn no (chubby_factor 0..1 -> mập tròn hơn tới 18%)
    chubby_x = 1.0 + 0.14 * st.chubby_factor
    chubby_y = 1.0 + 0.20 * st.chubby_factor
    p.scale(flip_x * depth_scale * st.squash_x * chubby_x, flip_y * depth_scale * st.squash_y * chubby_y)

    # Hệ số phồng cá nóc (1.0 -> 1.62)
    puff = st.puff_factor
    body_scale = 1.0 + 0.62 * puff

    # Đồng bộ biên độ & pha vẫy đuôi với lực đẩy Tail-Beat Impulse
    if st.expression in ("panic", "puffed"):
        wag_amp = 9.5
        phase = st.t_sec * 24.0
    elif st.expression in ("happy", "love", "proud"):
        wag_amp = 8.4
        phase = st.tail_phase * 1.4 + st.t_sec * 6.0
    elif st.expression in ("sleep", "belly_up"):
        wag_amp = 1.8
        phase = st.t_sec * 1.8
    else:
        wag_amp = 4.5 + st.swim_speed * 5.2
        phase = st.tail_phase
    tail_wag = math.sin(phase) * wag_amp
    fin_wag = math.sin(phase - 0.7) * (wag_amp * 0.48)

    pen_outline = QPen(outline, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    # --- 5a. Vây lưng trên (2 múi mềm + chấm tròn nhỏ phía sau, giống hệt ảnh mẫu) ---
    p.save()
    p.scale(body_scale, body_scale)
    dorsal = QPainterPath()
    dorsal.moveTo(-17, -25)
    dorsal.cubicTo(-10, -40, 8, -46 + fin_wag * 0.4, 17, -40 + fin_wag * 0.45)
    dorsal.cubicTo(20, -37 + fin_wag * 0.4, 16, -32 + fin_wag * 0.3, 12, -32 + fin_wag * 0.25)
    # Múi nhỏ thứ 2 ngay dưới múi chính
    dorsal.cubicTo(19, -31 + fin_wag * 0.3, 19, -24 + fin_wag * 0.2, 11, -22)
    dorsal.lineTo(-15, -21)
    dorsal.closeSubpath()

    p.setPen(pen_outline)
    p.setBrush(body_col)
    p.drawPath(dorsal)

    # Highlight vây lưng & nét gân đậm nhỏ bên trong
    p.setPen(QPen(hi_col, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(-8, -32), QPointF(10, -38 + fin_wag * 0.35))
    p.setPen(QPen(outline, 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(-1, -29), QPointF(6, -34 + fin_wag * 0.25))

    # Múi tròn nhỏ riêng lẻ phía sau lưng (đặc trưng trong ảnh mẫu)
    p.setPen(pen_outline)
    p.setBrush(body_col)
    p.save()
    p.translate(22, -20 + fin_wag * 0.2)
    p.rotate(32)
    p.drawEllipse(QRectF(-5.5, -5.0, 11.0, 10.0))
    p.restore()

    # --- 5b. Vây bụng nhỏ phía dưới-sau ---
    ventral = QPainterPath()
    ventral.moveTo(10, 24)
    ventral.cubicTo(15, 34 + fin_wag * 0.3, 25, 36 + fin_wag * 0.4, 28, 30 + fin_wag * 0.3)
    ventral.cubicTo(25, 26, 23, 21, 22, 18)
    ventral.closeSubpath()
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

    # --- 5d. Thân tròn + Đuôi quạt liền mạch (1 silhouette thống nhất không đường nối) ---
    # Khi quay chính diện (facing_front) hoặc phồng cá nóc, đuôi thu nhẹ ra phía sau
    tail_len = 0.22 if puff > 0.45 else (0.45 if st.facing_front else 1.0)
    tx0 = 28.5 * body_scale
    tx_tip = tx0 + 24.5 * tail_len
    tx_mid = tx0 + 18.0 * tail_len

    body_tail = QPainterPath()
    # Bắt đầu ở eo đuôi trên
    body_tail.moveTo(tx0, -5.5 * body_scale)
    # Cánh đuôi trên cong mượt
    body_tail.cubicTo(
        tx0 + 8.0 * tail_len, -10.0 + tail_wag * 0.3,
        tx_tip - 5.0, -23.0 + tail_wag * 0.85,
        tx_tip, -13.5 + tail_wag,
    )
    # Mép ngoài đuôi dạng chữ W mềm mại
    body_tail.cubicTo(
        tx_tip + 3.0 * tail_len, -6.0 + tail_wag * 0.9,
        tx_mid + 1.0, -1.0 + tail_wag * 0.7,
        tx_mid, 3.0 + tail_wag * 0.75,
    )
    body_tail.cubicTo(
        tx_tip + 1.5 * tail_len, 11.0 + tail_wag * 0.9,
        tx_tip - 1.5, 22.0 + tail_wag,
        tx_tip - 9.0 * tail_len, 22.0 + tail_wag * 0.85,
    )
    # Cong về eo đuôi dưới
    body_tail.cubicTo(
        tx0 + 9.0 * tail_len, 20.0 + tail_wag * 0.4,
        tx0 + 4.0 * tail_len, 11.5 * body_scale,
        tx0 - 1.5, 9.5 * body_scale,
    )
    # Thân tròn dưới -> trước -> trên quay về eo đuôi trên
    r_x = 32.5 * body_scale
    r_y = 30.8 * body_scale
    body_tail.cubicTo(
        18.0 * body_scale, r_y * 1.02,
        -21.0 * body_scale, r_y * 1.05,
        -r_x - 2.0, 12.0 * body_scale,
    )
    body_tail.cubicTo(
        -r_x - 5.5, -9.0 * body_scale,
        -21.0 * body_scale, -r_y * 1.05,
        2.0 * body_scale, -r_y * 1.02,
    )
    body_tail.cubicTo(
        20.0 * body_scale, -r_y * 0.96,
        tx0 - 1.0, -15.0 * body_scale,
        tx0, -5.5 * body_scale,
    )
    body_tail.closeSubpath()

    # Tô màu nền thân + đuôi
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(body_col)
    p.drawPath(body_tail)

    # Cắt clip trong thân để tô bóng cam ấm phía bụng & ánh sáng vàng kem phía trên
    p.save()
    p.setClipPath(body_tail, Qt.ClipOperation.IntersectClip)
    # Bóng cam ấm phía dưới-sau thân (giống ảnh mẫu)
    shade_path = QPainterPath()
    shade_path.addEllipse(QRectF(-r_x - 6, -r_y - 4, r_x * 2 + 8, r_y * 2 + 4))
    inner_cut = QPainterPath()
    inner_cut.addEllipse(QRectF(-r_x - 10, -r_y - 10, r_x * 2 + 4, r_y * 2 + 1))
    crescent_shade = shade_path.subtracted(inner_cut)
    p.setBrush(shade_col)
    p.drawPath(crescent_shade)

    # Dải sáng kem phía trên đầu
    p.setPen(QPen(hi_col, 4.2 * body_scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(
        QRectF(-r_x + 2, -r_y + 3, r_x * 1.75, r_y * 1.55),
        52 * 16,
        105 * 16,
    )

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

    # Mặt tái xanh lè khi buồn nôn cầu vồng (Post-Dizzy)
    if st.expression in ("nauseous", "belly_up"):
        g_alpha = 135 if st.expression == "nauseous" else 85
        sick_grad = QRadialGradient(QPointF(-10 * body_scale, -8 * body_scale), 38 * body_scale)
        sick_grad.setColorAt(0.0, QColor(125, 224, 118, g_alpha))
        sick_grad.setColorAt(0.7, QColor(145, 232, 130, int(g_alpha * 0.45)))
        sick_grad.setColorAt(1.0, QColor(145, 232, 130, 0))
        p.setBrush(sick_grad)
        p.drawEllipse(QRectF(-r_x - 4, -r_y - 4, r_x * 2 + 8, r_y * 2 + 8))

    p.restore()

    # Các tia gân ngắn đặc trưng bên trong đuôi quạt
    if not st.facing_front:
        p.setPen(QPen(outline, 2.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for ry_off in (-7.0, -1.5, 4.0, 9.5):
            y1 = ry_off * 0.55 + tail_wag * 0.45
            y2 = ry_off * 1.25 + tail_wag * 0.85
            p.drawLine(QPointF(tx0 + 8.5, y1), QPointF(tx0 + 17.5, y2))

    # Vẽ viền outline đậm mượt bên ngoài cùng
    p.setPen(pen_outline)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(body_tail)

    # --- 5e. Chăn rong biển (sau 23:30 đêm) ---
    if st.seaweed_blanket:
        _draw_seaweed_blanket(p, body_scale, st.t_sec, outline)

    # --- 5f. Khuôn mặt biểu cảm ---
    _draw_fish_face(p, st, body_scale, outline, body_col, blush_col)

    # --- 5g. Luồng hút thức ăn / file vào miệng ---
    if st.suction_alpha > 0.02:
        p.save()
        p.setOpacity(st.suction_alpha)
        mouth_x = -14.8 * body_scale if not st.facing_front else 0.0
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

    p.restore()  # Kết thúc biến đổi thân cá

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

    # --- 6. Bong bóng khổng lồ bao bọc khi ngủ (Idle State) ---
    if st.in_sleep_bubble:
        _draw_giant_sleep_bubble(p, cx, cy + bob_y, 68.0 * depth_scale, st.t_sec)

    # --- 7. Hạt hiệu ứng (không bị lật ngang để chữ Z / ! / ? luôn đúng chiều) ---
    for pt in st.particles:
        alpha = max(0.0, min(1.0, pt.life / pt.max_life))
        p.save()
        p.setOpacity(alpha)
        if pt.kind == "heart":
            _draw_heart(p, pt.x, pt.y, pt.size, pt.color)
        elif pt.kind == "zzz":
            p.setFont(QFont("Sans Serif", int(pt.size), QFont.Weight.Bold))
            p.setPen(pt.color)
            p.drawText(QPointF(pt.x, pt.y), "Z")
        elif pt.kind == "excl":
            p.setFont(QFont("Sans Serif", int(pt.size), QFont.Weight.Black))
            p.setPen(pt.color)
            p.drawText(QPointF(pt.x, pt.y), "!")
        elif pt.kind == "quest":
            p.setFont(QFont("Sans Serif", int(pt.size), QFont.Weight.Black))
            p.setPen(pt.color)
            p.drawText(QPointF(pt.x, pt.y), "?")
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
        elif pt.kind in ("bubble", "boil", "puff_air"):
            p.setPen(QPen(QColor(255, 255, 255, 230), 1.5))
            p.setBrush(pt.color)
            p.drawEllipse(QPointF(pt.x, pt.y), pt.size * 0.5, pt.size * 0.5)
            # Chấm bóng sáng nhỏ trên bọt
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 220))
            p.drawEllipse(QPointF(pt.x - pt.size * 0.16, pt.y - pt.size * 0.16), pt.size * 0.14, pt.size * 0.14)
        p.restore()


def _draw_fish_face(
    p: QPainter,
    st: FishRenderState,
    s: float,
    outline: QColor,
    body_col: QColor,
    blush_col: QColor,
) -> None:
    expr = st.expression
    if st.facing_front:
        eyes = [(-13.5 * s, 0.5 * s, 6.8), (13.5 * s, 0.5 * s, 6.8)]
        mouth_x, mouth_y = 0.0, 9.5 * s
        cheeks = [(-22.0 * s, 10.5 * s), (22.0 * s, 10.5 * s)]
    else:
        # Khớp chuẩn góc nghiêng 3/4 siêu dễ thương như ảnh mẫu!
        eyes = [(-23.0 * s, 0.5 * s, 6.4), (-3.5 * s, 1.0 * s, 7.2)]
        mouth_x, mouth_y = -14.8 * s, 9.8 * s
        cheeks = [(3.8 * s, 11.5 * s)]
        if expr in ("puffed", "shy", "love", "happy", "proud", "nauseous"):
            cheeks.append((-26.0 * s, 10.5 * s))

    # --- Má hồng ---
    if expr in ("nauseous", "belly_up"):
        c_blush = QColor(115, 208, 110, 200)
        cheek_r = 7.2 * s
    elif expr in ("puffed", "grumpy"):
        c_blush = QColor("#ff4260")
        c_blush.setAlpha(220)
        cheek_r = 7.4 * s
    elif expr == "proud":
        c_blush = QColor("#ff5277")
        c_blush.setAlpha(235)
        cheek_r = 8.0 * s
    elif expr in ("happy", "love", "shy"):
        c_blush = QColor(blush_col)
        c_blush.setAlpha(215)
        cheek_r = 6.9 * s
    else:
        c_blush = QColor(blush_col)
        c_blush.setAlpha(185)
        cheek_r = 6.2 * s

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c_blush)
    for bx, by in cheeks:
        p.drawEllipse(QPointF(bx, by), cheek_r, cheek_r * 0.88)

    if expr in ("shy", "love", "proud"):
        p.setPen(QPen(QColor("#ff3b5c"), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for bx, by in cheeks:
            for d in (-3.0, 0.0, 3.0):
                p.drawLine(QPointF(bx + d - 1.0, by + 2.5), QPointF(bx + d + 1.5, by - 2.0))

    # --- Đôi mắt ---
    eye_pen = QPen(outline, 2.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(eye_pen)

    for idx, (ex, ey, er) in enumerate(eyes):
        side = -1 if idx == 0 else 1
        if expr == "sleep":
            arc = QPainterPath()
            arc.moveTo(ex - er * 0.85, ey)
            arc.quadTo(ex, ey + er * 0.72, ex + er * 0.85, ey)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(arc)
        elif expr in ("happy", "proud"):
            arc = QPainterPath()
            arc.moveTo(ex - er * 0.9, ey + 2.2)
            arc.quadTo(ex, ey - er * (1.15 if expr == "proud" else 0.95), ex + er * 0.9, ey + 2.2)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(arc)
        elif expr == "love":
            pulse = 1.0 + math.sin(st.t_sec * 10.0) * 0.13
            _draw_heart(p, ex, ey + 1.0, er * 2.1 * pulse, QColor("#ff4268"))
            p.setPen(eye_pen)
        elif expr in ("eat", "sneeze_windup"):
            # Mắt > < hưởng thụ hoặc nhăn mặt lấy hơi hắt xì
            p.setBrush(Qt.BrushStyle.NoBrush)
            if side == -1:
                p.drawLine(QPointF(ex - 4.5, ey - 3.5), QPointF(ex + 3.5, ey))
                p.drawLine(QPointF(ex + 3.5, ey), QPointF(ex - 4.5, ey + 3.5))
            else:
                p.drawLine(QPointF(ex + 4.5, ey - 3.5), QPointF(ex - 3.5, ey))
                p.drawLine(QPointF(ex - 3.5, ey), QPointF(ex + 4.5, ey + 3.5))
        elif expr == "belly_up":
            # Mắt X X trôi lờ đờ khi ngửa bụng
            p.setBrush(Qt.BrushStyle.NoBrush)
            d = er * 0.65
            p.drawLine(QPointF(ex - d, ey - d), QPointF(ex + d, ey + d))
            p.drawLine(QPointF(ex + d, ey - d), QPointF(ex - d, ey + d))
        elif expr in ("dizzy", "nauseous"):
            # Mắt xoáy tròn @ @
            p.save()
            p.translate(ex, ey)
            p.rotate((st.frame * 11 * side) % 360)
            spiral = QPainterPath()
            for step in range(28):
                a = step * 0.45
                r = step * (er / 27.0)
                sx = math.cos(a) * r
                sy = math.sin(a) * r
                if step == 0:
                    spiral.moveTo(sx, sy)
                else:
                    spiral.lineTo(sx, sy)
            p.setPen(QPen(outline, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(spiral)
            p.restore()
            p.setPen(eye_pen)
        elif expr in ("panic", "sneeze_burst"):
            # Mắt mở to hốt hoảng + đồng tử nhỏ run rẩy
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(ex, ey), er * 1.15, er * 1.18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outline)
            sh = math.sin(st.t_sec * 35.0 + idx) * 1.1
            p.drawEllipse(QPointF(ex + sh, ey), er * 0.36, er * 0.36)
            p.setPen(eye_pen)
        elif expr in ("puffed", "grumpy"):
            # Mắt cau dỗi + lông mày giận
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outline)
            p.drawEllipse(QPointF(ex, ey + 0.5), er * 0.9, er * 0.85)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(ex - er * 0.25, ey - er * 0.22), er * 0.34, er * 0.34)
            p.setPen(QPen(outline, 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            # Lông mày cau dỗi \ / hướng chéo xuống vào giữa hai mắt
            p.drawLine(
                QPointF(ex + side * er * 0.9, ey - er * 1.15),
                QPointF(ex - side * er * 0.8, ey - er * 0.42),
            )
            p.setPen(eye_pen)
        elif expr == "sleepy":
            # Mắt lim dim buồn ngủ
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outline)
            p.drawEllipse(QPointF(ex, ey), er * 0.95, er * 0.95)
            p.setBrush(body_col)
            p.drawRect(QRectF(ex - er - 1, ey - er - 1, (er + 1) * 2, er * 1.05))
            p.setPen(eye_pen)
            p.drawLine(QPointF(ex - er, ey + 0.3), QPointF(ex + er, ey + 0.3))
        elif expr == "excited":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outline)
            p.drawEllipse(QPointF(ex, ey), er * 1.05, er * 1.05)
            _draw_star(p, ex, ey, er * 1.45, QColor("#fff3a3"))
            p.setPen(eye_pen)
        elif st.blink and expr not in ("swallow",):
            p.drawLine(QPointF(ex - er * 0.8, ey), QPointF(ex + er * 0.8, ey))
        else:
            # Mắt tròn long lanh chuẩn ảnh mẫu (viền nâu tím đậm + đốm sáng trắng lớn góc trên-trái)
            lx = st.look_dx * 1.6
            ly = st.look_dy * 1.4
            if expr == "cautious":
                lx = 2.0  # liếc dè chừng
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outline)
            p.drawEllipse(QPointF(ex + lx * 0.4, ey + ly * 0.4), er, er * 0.96)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(ex - er * 0.25 + lx * 0.6, ey - er * 0.3 + ly * 0.5), er * 0.38, er * 0.36)
            p.drawEllipse(QPointF(ex + er * 0.25 + lx * 0.5, ey + er * 0.25 + ly * 0.4), er * 0.16, er * 0.16)
            p.setPen(eye_pen)

    # --- Miệng ---
    p.setPen(QPen(outline, 2.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    if expr == "swallow":
        # Há miệng cực to hút rác/file vào bụng!
        open_r = 9.5 + math.sin(st.t_sec * 18.0) * 1.4
        p.setBrush(QColor("#ff5c77"))
        p.drawEllipse(QPointF(mouth_x, mouth_y + 1.0), open_r * 0.9, open_r)
        # Lưỡi nhỏ bên trong
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ff99ac"))
        p.drawEllipse(QPointF(mouth_x, mouth_y + open_r * 0.45), open_r * 0.52, open_r * 0.32)
    elif expr == "eat":
        if (st.frame // 6) % 2 == 0:
            p.setBrush(QColor("#ff6b81"))
            p.drawEllipse(QPointF(mouth_x, mouth_y + 1.0), 5.2, 4.6)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(mouth_x - 4.5, mouth_y - 3.0, 9.0, 7.5), 200 * 16, 140 * 16)
    elif expr == "nauseous":
        # Há miệng ợ bong bóng cầu vồng
        open_r = 7.2 + math.sin(st.t_sec * 20.0) * 1.4
        p.setBrush(QColor("#80ed99"))
        p.drawEllipse(QPointF(mouth_x, mouth_y + 1.5), open_r * 0.9, open_r)
    elif expr == "belly_up":
        # Miệng hé lè lưỡi nhỏ lờ đờ
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(mouth_x - 4.5, mouth_y + 1.0), QPointF(mouth_x + 4.5, mouth_y + 1.0))
        p.setBrush(QColor("#ff758f"))
        p.drawEllipse(QRectF(mouth_x - 2.6, mouth_y + 0.5, 5.2, 5.5))
    elif expr == "sneeze_windup":
        # Miệng mím nhăn lấy hơi
        p.setBrush(Qt.BrushStyle.NoBrush)
        mp = QPainterPath()
        mp.moveTo(mouth_x - 4.0, mouth_y + 2.0)
        mp.quadTo(mouth_x, mouth_y - 1.5, mouth_x + 4.0, mouth_y + 2.0)
        p.drawPath(mp)
    elif expr == "sneeze_burst":
        # Hắt xì há miệng to!
        p.setBrush(QColor("#ff5c77"))
        p.drawEllipse(QPointF(mouth_x, mouth_y + 1.5), 6.2, 7.6)
    elif expr == "proud":
        # Cười tự hào rạng rỡ ^‿^
        p.setBrush(QColor("#ff6b81"))
        mp = QPainterPath()
        mp.moveTo(mouth_x - 6.0, mouth_y - 0.5)
        mp.lineTo(mouth_x + 6.0, mouth_y - 0.5)
        mp.quadTo(mouth_x, mouth_y + 9.2, mouth_x - 6.0, mouth_y - 0.5)
        p.drawPath(mp)
    elif expr == "puffed":
        # Miệng chu phồng dỗi hờn
        p.setBrush(QColor("#ff6b81"))
        p.drawEllipse(QPointF(mouth_x, mouth_y + 1.5), 3.6, 3.6)
    elif expr == "panic":
        # Miệng há ngoằn ngoèo hốt hoảng
        p.setBrush(QColor("#ff5c77"))
        p.drawEllipse(QPointF(mouth_x, mouth_y + 2.0), 5.5, 6.8)
    elif expr == "sleepy":
        # Ngáp tròn to
        yawn = 4.0 + abs(math.sin(st.t_sec * 2.5)) * 4.2
        p.setBrush(QColor("#ff758f"))
        p.drawEllipse(QPointF(mouth_x, mouth_y + 1.5), 4.2, yawn)
    elif expr == "dizzy":
        p.setBrush(Qt.BrushStyle.NoBrush)
        mp = QPainterPath()
        mp.moveTo(mouth_x - 5.5, mouth_y + 1.5)
        mp.quadTo(mouth_x - 2.5, mouth_y - 2.0, mouth_x, mouth_y + 1.5)
        mp.quadTo(mouth_x + 2.5, mouth_y + 5.0, mouth_x + 5.5, mouth_y + 1.5)
        p.drawPath(mp)
    elif expr in ("grumpy", "cautious"):
        p.setBrush(Qt.BrushStyle.NoBrush)
        mp = QPainterPath()
        mp.moveTo(mouth_x - 4.5, mouth_y + 3.5)
        mp.quadTo(mouth_x, mouth_y - 0.5, mouth_x + 4.5, mouth_y + 3.5)
        p.drawPath(mp)
    elif expr == "sleep":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(mouth_x - 3.5, mouth_y - 2.0, 7.0, 5.5), 200 * 16, 140 * 16)
    else:
        # Nụ cười chữ U tròn nhỏ siêu cưng giống ảnh mẫu!
        p.setBrush(Qt.BrushStyle.NoBrush)
        mp = QPainterPath()
        mp.moveTo(mouth_x - 4.4, mouth_y - 1.2)
        mp.cubicTo(mouth_x - 4.0, mouth_y + 5.2, mouth_x + 4.0, mouth_y + 5.2, mouth_x + 4.4, mouth_y - 1.2)
        p.drawPath(mp)


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


def _draw_giant_sleep_bubble(p: QPainter, cx: float, cy: float, r: float, t_sec: float) -> None:
    """Quả bong bóng khổng lồ bao bọc toàn thân chú cá khi ngủ gật."""
    p.save()
    wx = 1.0 + math.sin(t_sec * 1.7) * 0.025
    wy = 1.0 - math.sin(t_sec * 1.7) * 0.025
    p.translate(cx, cy)
    p.scale(wx, wy)

    grad = QRadialGradient(QPointF(-r * 0.32, -r * 0.35), r * 1.35)
    grad.setColorAt(0.0, QColor(255, 255, 255, 120))
    grad.setColorAt(0.55, QColor(170, 230, 255, 42))
    grad.setColorAt(0.86, QColor(195, 215, 255, 78))
    grad.setColorAt(1.0, QColor(255, 200, 235, 145))

    p.setPen(QPen(QColor(165, 225, 255, 215), 2.4))
    p.setBrush(grad)
    p.drawEllipse(QPointF(0, 0), r, r)

    # Vệt phản chiếu sáng cong lớn trên bong bóng
    p.setPen(QPen(QColor(255, 255, 255, 215), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(-r * 0.78, -r * 0.78, r * 1.56, r * 1.56), 112 * 16, 46 * 16)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 220))
    p.drawEllipse(QPointF(-r * 0.56, -r * 0.2), 4.5, 4.5)
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
