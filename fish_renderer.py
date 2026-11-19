"""Bộ vẽ vector 2D cho linh vật Cá Vàng (Golden Fish) khớp phong cách minh họa.

Hỗ trợ:
- Tạo hình cá vàng tròn trĩnh, vây lưng 2 múi + chấm phụ, đuôi quạt mượt liền thân, má hồng, bọt trắng
- Chiều sâu 3D (scale 0.85x..1.10x + bóng đổ đậm/mờ ngược chiều sâu)
- Toàn bộ trạng thái biểu cảm: swim/idle, happy, love, puffed (cá nóc), dizzy,
  eat/swallow (há miệng hút), panic (hốt hoảng/sôi nước), sleep (ngủ trong bong bóng lớn),
  sleepy (ngáp khuya), shy, grumpy, cautious (dè chừng vùng đỏ/cam)
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
    QLinearGradient,
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


@dataclass
class Particle:
    kind: str  # bubble | trail_bubble | rainbow_bubble | water_drop | boil | heart | zzz | ghost | star | excl | anger | sweat | puff_air | crumb | spark | smoke | tear
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
    expression: str          # normal | happy | love | proud | puffed | dizzy | nauseous | belly_up | play_dead | sneeze_windup | sneeze_burst | eat | swallow | panic | sleep | sleepy | shy | grumpy | cautious | peeking | caged_sad | pleading | muscle_strain
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
    cage_mode: str = "none"                  # "none" | "caged" | "breaking_out"
    cage_drop_progress: float = 1.0          # 0..1 hiệu ứng lồng rơi xuống khóa "cạch"
    cage_swing_deg: float = 0.0              # góc lắc lồng quanh đỉnh móc treo (±3° khi van xin)
    cage_pleading: bool = False              # True khi đang bám thanh sắt van xin
    cage_bend_amount: float = 0.0            # 0..1 độ bẻ cong 2 thanh sắt giữa lồng
    cage_opacity: float = 1.0                # 0..1 độ mờ của lồng
    muscular_level: float = 0.0              # 0..1 độ gồng cơ bắp lực sĩ khi phá lồng
    pupil_x: float = 0.0                     # dịch chuyển con ngươi theo chuột (tọa độ màn hình, px)
    pupil_y: float = 0.0                     # dịch chuyển con ngươi theo chuột (tọa độ màn hình, px)
    turn_progress: float = -1.0              # 0..1 chuyển cảnh quay đầu qua Front View (~140ms), <0 là không quay
    turn_from_dir: int = -1                  # hướng cũ trước khi bắt đầu quay đầu
    contact_shadow: float = 0.0              # 0..1 bóng đổ tiếp xúc (chỉ hiện khi sát đáy màn hình hoặc mép cửa sổ)
    contact_shadow_y: float = 0.0            # tọa độ Y cục bộ của mặt sàn / mép cửa sổ dưới bụng cá
    play_dead_peek: bool = False             # hé trộm một mắt liếc chuột khi đang giả chết
    surfing_waterline: bool = False          # đang bơi lướt trên mặt nước mép trên cửa sổ (chìm nhẹ bụng 8–12px)
    surf_waterline_y: float = 0.0            # tọa độ Y cục bộ của đường mép cửa sổ
    surf_speed: float = 0.0                  # tốc độ lướt ngang 0..1 điều khiển vệt sóng chữ V


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
    elif st.contact_shadow > 0.01 and not st.in_sleep_bubble and not st.peeking_window:
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
        p.translate(cx + jitter_x, cy + bob_y + jitter_y)

    # Nếu đang ngó trên thanh tiêu đề cửa sổ, cắt phẳng phần bụng dưới để trông như đang thò đầu qua mép!
    if st.peeking_window:
        p.setClipRect(QRectF(-st.size / 2, -st.size / 2, st.size, st.size / 2 + 15.0))

    # Góc nghiêng bơi + banking quán tính + xoay vòng xoáy/backflip
    peek_tilt = -4.0 * st.direction if st.peeking_window else 0.0
    total_rot = st.pitch_deg + st.bank_deg + st.spin_deg + peek_tilt
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
    # Lật ngửa bụng (belly_up) sau khi nôn cầu vồng
    flip_y = -1.0 if st.belly_up else 1.0
    # Hiệu ứng béo tròn khi ăn no (chubby_factor 0..1 -> mập tròn hơn tới 18%)
    chubby_x = 1.0 + 0.14 * st.chubby_factor
    chubby_y = 1.0 + 0.20 * st.chubby_factor
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
    elif st.expression == "play_dead":
        wag_amp = 0.8
        phase = st.t_sec * 1.1
    elif st.expression in ("sleep", "belly_up", "caged_sad"):
        wag_amp = 1.8
        phase = st.t_sec * 1.8
    elif st.expression == "pleading":
        wag_amp = 3.2
        phase = st.t_sec * 5.2
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

    # --- 6. Vòng hào quang thiên thần khi Giả chết (hoặc bong bóng ngủ nếu bật) ---
    if st.expression == "play_dead":
        _draw_angel_halo(p, cx, cy + bob_y - 46.0 * depth_scale, depth_scale, st.t_sec)
    elif st.in_sleep_bubble:
        _draw_giant_sleep_bubble(p, cx, cy + bob_y, 68.0 * depth_scale, st.t_sec)

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


def _clamp_ellipse(x: float, y: float, rx: float, ry: float) -> tuple[float, float]:
    """Giới hạn tọa độ (x, y) nằm gọn bên trong hình elip bán trục (rx, ry)."""
    if rx <= 0.0 or ry <= 0.0:
        return 0.0, 0.0
    n = math.hypot(x / rx, y / ry)
    if n > 1.0:
        return x / n, y / n
    return x, y


def _draw_fish_face(
    p: QPainter,
    st: FishRenderState,
    s: float,
    outline: QColor,
    body_col: QColor,
    blush_col: QColor,
    eff_front: bool = False,
    face_shift_x: float = 0.0,
    local_pupil_x: float = 0.0,
    local_pupil_y: float = 0.0,
) -> None:
    expr = st.expression
    fx = face_shift_x
    if eff_front:
        eyes = [(-13.5 * s + fx, 0.5 * s, 6.8), (13.5 * s + fx, 0.5 * s, 6.8)]
        mouth_x, mouth_y = fx, 9.5 * s
        cheeks = [(-22.0 * s + fx * 0.7, 10.5 * s), (22.0 * s + fx * 0.7, 10.5 * s)]
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
    elif expr == "muscle_strain":
        c_blush = QColor("#ff2a3c")
        c_blush.setAlpha(235)
        cheek_r = 8.4 * s
    elif expr in ("puffed", "grumpy"):
        c_blush = QColor("#ff4260")
        c_blush.setAlpha(220)
        cheek_r = 7.4 * s
    elif expr == "proud":
        c_blush = QColor("#ff5277")
        c_blush.setAlpha(235)
        cheek_r = 8.0 * s
    elif expr in ("happy", "love", "shy", "pleading"):
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
        elif expr == "play_dead":
            # Mắt X X giả chết — thỉnh thoảng hé trộm 1 mắt liếc xem bạn có đang nhìn không!
            if st.play_dead_peek and idx == 1:
                sock_rx = er * 1.04
                sock_ry = er * 0.72
                px, py = _clamp_ellipse(local_pupil_x, local_pupil_y, min(2.8, er * 0.42), min(2.0, er * 0.30))
                sock_path = QPainterPath()
                sock_path.addEllipse(QPointF(ex, ey), sock_rx, sock_ry)
                p.setPen(QPen(outline, 1.8))
                p.setBrush(QColor("#fffef9"))
                p.drawPath(sock_path)
                p.save()
                p.setClipPath(sock_path, Qt.ClipOperation.IntersectClip)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(outline)
                p.drawEllipse(QPointF(ex + px, ey + py), er * 0.62, er * 0.62)
                p.setBrush(QColor("#ffffff"))
                p.drawEllipse(QPointF(ex + px * 0.9 - er * 0.18, ey + py * 0.9 - er * 0.16), er * 0.22, er * 0.20)
                p.restore()
                p.setPen(QPen(outline, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(ex - sock_rx, ey + sock_ry * 0.55), QPointF(ex + sock_rx, ey + sock_ry * 0.55))
                p.setPen(eye_pen)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                d = er * 0.72
                p.drawLine(QPointF(ex - d, ey - d), QPointF(ex + d, ey + d))
                p.drawLine(QPointF(ex + d, ey - d), QPointF(ex - d, ey + d))
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
        elif expr == "surprised":
            # Mắt mở to tròn xoe ngạc nhiên (khi bạn kéo di chuyển cửa sổ dưới chân cá!)
            p.setPen(QPen(outline, 2.2))
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(ex, ey), er * 1.18, er * 1.22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outline)
            p.drawEllipse(QPointF(ex, ey), er * 0.42, er * 0.44)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(ex - er * 0.18, ey - er * 0.22), er * 0.18, er * 0.18)
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
        elif expr == "muscle_strain":
            # Đôi mắt quyết tâm rực lửa + lông mày chữ V cực ngầu khi bẻ thanh sắt!
            p.setPen(QPen(outline, 2.5))
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(ex, ey + 0.5), er * 1.02, er * 0.92)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outline)
            p.drawEllipse(QPointF(ex, ey + 0.8), er * 0.46, er * 0.48)
            p.setBrush(QColor("#ffd166"))
            p.drawEllipse(QPointF(ex - er * 0.14, ey - er * 0.12), er * 0.22, er * 0.22)
            # Lông mày cau mạnh hướng chéo xuống giữa hai mắt
            p.setPen(QPen(outline, 3.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(
                QPointF(ex + side * er * 1.05, ey - er * 1.25),
                QPointF(ex - side * er * 0.95, ey - er * 0.28),
            )
            p.setPen(eye_pen)
        elif expr in ("pleading", "caged_sad"):
            # Mắt to rưng rưng long lanh (giống ảnh mẫu), con ngươi liếc độc lập mượt theo chuột!
            is_plead = expr == "pleading"
            r_eye = er * (1.22 if is_plead else 1.08)
            px, py = _clamp_ellipse(
                local_pupil_x * (0.65 if is_plead else 0.90),
                local_pupil_y * (0.60 if is_plead else 0.82),
                min(3.0, r_eye * 0.36),
                min(2.6, r_eye * 0.32),
            )
            shimmer = 0.5 + 0.5 * math.sin(st.t_sec * 9.0 + idx * 1.4)

            # Lớp tròng mắt trắng mịn + clip elip để con ngươi chuyển động gọn bên trong
            sock_path = QPainterPath()
            sock_path.addEllipse(QPointF(ex, ey), r_eye, r_eye * 1.04)
            p.setPen(QPen(outline, 1.8))
            p.setBrush(QColor("#fffef9"))
            p.drawPath(sock_path)

            p.save()
            p.setClipPath(sock_path, Qt.ClipOperation.IntersectClip)
            # Con ngươi tối to tròn long lanh di chuyển độc lập
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outline)
            p.drawEllipse(QPointF(ex + px, ey + py), r_eye * 0.88, r_eye * 0.90)

            # Làn nước mắt xanh nhạt đọng ở mi dưới mắt (long lanh rưng rưng)
            tear_alpha = int(235 if is_plead else 160)
            tear_h = r_eye * (0.58 + 0.08 * shimmer if is_plead else 0.34)
            tear_path = QPainterPath()
            tx_c = ex + px * 0.35
            ty_b = ey + r_eye * 0.96
            tear_path.moveTo(tx_c - r_eye * 0.90, ty_b - tear_h * 0.45)
            tear_path.quadTo(tx_c, ty_b - tear_h * 0.95, tx_c + r_eye * 0.90, ty_b - tear_h * 0.45)
            tear_path.quadTo(tx_c, ty_b + tear_h * 0.48, tx_c - r_eye * 0.90, ty_b - tear_h * 0.45)
            p.setBrush(QColor(156, 232, 255, tear_alpha))
            p.drawPath(tear_path)

            # Đốm sáng trắng lớn lấp lánh như mắt cún con van xin
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(
                QPointF(ex - r_eye * 0.26 + px * 0.85, ey - r_eye * 0.28 + py * 0.85),
                r_eye * (0.40 if is_plead else 0.35),
                r_eye * (0.38 if is_plead else 0.33),
            )
            p.drawEllipse(
                QPointF(ex + r_eye * 0.28 + px * 0.75, ey + r_eye * 0.16 + py * 0.75),
                r_eye * (0.19 if is_plead else 0.15),
                r_eye * (0.17 if is_plead else 0.14),
            )
            if is_plead:
                # Hạt sáng lung linh trên làn nước mắt
                p.drawEllipse(
                    QPointF(tx_c - r_eye * 0.22, ty_b - tear_h * 0.30),
                    r_eye * (0.14 + 0.04 * shimmer),
                    r_eye * 0.11,
                )
            p.restore()

            # Viền ngoài tròng mắt sắc nét
            p.setPen(QPen(outline, 1.7))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(sock_path)

            # Lông mày cụp buồn (/ \) hướng nghiêng xuống ra hai bên ngoài
            brow_y_in = ey - r_eye * (1.38 if is_plead else 1.25)
            brow_y_out = ey - r_eye * (0.86 if is_plead else 0.92)
            p.setPen(QPen(outline, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(
                QPointF(ex - side * r_eye * 0.55, brow_y_in),
                QPointF(ex + side * r_eye * 0.72, brow_y_out),
            )
            p.setPen(eye_pen)
        elif st.blink and expr not in ("swallow",):
            p.drawLine(QPointF(ex - er * 0.8, ey), QPointF(ex + er * 0.8, ey))
        else:
            # Lớp 1 (Eye Tracking độc lập): Tách tròng mắt trắng và con ngươi (pupil) giới hạn theo elip 2–3.4px
            sock_rx = er * 1.08
            sock_ry = er * 1.04
            max_px = min(3.4, er * 0.48)
            max_py = min(2.8, er * 0.42)
            raw_px = local_pupil_x
            raw_py = local_pupil_y
            if expr == "cautious" and math.hypot(raw_px, raw_py) < 0.5:
                raw_px = 2.4  # liếc dè chừng khi ở vùng màu đỏ/cam
            px, py = _clamp_ellipse(raw_px, raw_py, max_px, max_py)

            # 1a. Tròng mắt trắng (Sclera) cố định trên mặt cá
            sock_path = QPainterPath()
            sock_path.addEllipse(QPointF(ex, ey), sock_rx, sock_ry)
            p.setPen(QPen(outline, 1.7))
            p.setBrush(QColor("#fffef9"))
            p.drawPath(sock_path)

            # 1b. Con ngươi độc lập (Pupil) + ánh sáng bóng nằm gọn trong elip tròng mắt
            p.save()
            p.setClipPath(sock_path, Qt.ClipOperation.IntersectClip)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(outline)
            p_rx = er * 0.80
            p_ry = er * 0.78
            p.drawEllipse(QPointF(ex + px, ey + py), p_rx, p_ry)

            # Ánh sáng long lanh di chuyển đồng bộ theo con ngươi
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(
                QPointF(ex + px * 0.92 - p_rx * 0.28, ey + py * 0.92 - p_ry * 0.30),
                p_rx * 0.38,
                p_ry * 0.36,
            )
            p.drawEllipse(
                QPointF(ex + px * 0.85 + p_rx * 0.28, ey + py * 0.85 + p_ry * 0.26),
                p_rx * 0.16,
                p_ry * 0.16,
            )
            p.restore()

            # Viền tròng mắt sắc nét trên cùng
            p.setPen(QPen(outline, 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(sock_path)
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
    elif expr == "play_dead":
        # Miệng hé lè chiếc lưỡi hồng sang một bên cực hài khi giả chết!
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(mouth_x - 5.2, mouth_y + 1.0), QPointF(mouth_x + 5.2, mouth_y + 1.0))
        p.setBrush(QColor("#ff758f"))
        tongue = QPainterPath()
        tongue.moveTo(mouth_x - 1.5, mouth_y + 1.0)
        tongue.cubicTo(mouth_x - 2.2, mouth_y + 8.5, mouth_x + 5.2, mouth_y + 9.0, mouth_x + 4.4, mouth_y + 1.0)
        tongue.closeSubpath()
        p.drawPath(tongue)
        p.setPen(QPen(QColor("#c9184a"), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(mouth_x + 1.2, mouth_y + 2.2), QPointF(mouth_x + 1.4, mouth_y + 6.0))
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
    elif expr == "surprised":
        # Miệng chữ 'o' tròn nhỏ ngạc nhiên
        p.setBrush(QColor("#ff6b81"))
        p.drawEllipse(QPointF(mouth_x, mouth_y + 1.5), 4.2, 4.8)
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
    elif expr in ("pleading", "caged_sad"):
        # Miệng mếu úp ngược siêu đáng thương (như ảnh mẫu)
        p.setBrush(Qt.BrushStyle.NoBrush)
        wob = math.sin(st.t_sec * 16.0) * 0.6 if expr == "pleading" else 0.0
        mp = QPainterPath()
        mw = 5.4 if expr == "pleading" else 4.4
        arch = 5.2 if expr == "pleading" else 3.4
        mp.moveTo(mouth_x - mw, mouth_y + 4.2 + wob)
        mp.quadTo(mouth_x, mouth_y - arch + 2.5, mouth_x + mw, mouth_y + 4.2 - wob)
        p.drawPath(mp)
    elif expr == "muscle_strain":
        # Miệng nghiến răng quyết tâm gồng lực sĩ!
        p.setBrush(QColor("#ffffff"))
        rect_m = QRectF(mouth_x - 8.0, mouth_y - 2.2, 16.0, 7.6)
        p.drawRoundedRect(rect_m, 3.0, 3.0)
        p.setPen(QPen(outline, 1.8))
        p.drawLine(QPointF(mouth_x - 7.5, mouth_y + 1.6), QPointF(mouth_x + 7.5, mouth_y + 1.6))
        for gx in (-3.2, 0.0, 3.2):
            p.drawLine(QPointF(mouth_x + gx, mouth_y - 2.0), QPointF(mouth_x + gx, mouth_y + 5.2))
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
