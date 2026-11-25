"""Vẽ khuôn mặt, biểu cảm mắt/miệng/má hồng và cử chỉ chỉ vây vào miệng đòi ăn."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
)

from pet.models import FishRenderState
from pet.rendering.primitives import _clamp_ellipse, _draw_heart, _draw_star


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
        if expr in ("puffed", "shy", "love", "happy", "proud", "nauseous", "full_shake", "hungry_beg"):
            cheeks.append((-26.0 * s, 10.5 * s))

    # --- Má hồng ---
    if expr in ("nauseous", "belly_up"):
        c_blush = QColor(115, 208, 110, 200)
        cheek_r = 7.2 * s
    elif expr == "starved_dead":
        c_blush = QColor(175, 165, 180, 110)
        cheek_r = 5.4 * s
    elif expr == "muscle_strain":
        c_blush = QColor("#ff2a3c")
        c_blush.setAlpha(235)
        cheek_r = 8.4 * s
    elif expr in ("puffed", "grumpy", "full_shake"):
        c_blush = QColor("#ff4d6d")
        c_blush.setAlpha(228)
        cheek_r = (8.0 if expr == "full_shake" else 7.4) * s
    elif expr == "proud":
        c_blush = QColor("#ff5277")
        c_blush.setAlpha(235)
        cheek_r = 8.0 * s
    elif expr in ("happy", "love", "shy", "pleading", "hungry_beg"):
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
        elif expr in ("eat", "sneeze_windup", "full_shake"):
            # Mắt > < hưởng thụ, lấy hơi hắt xì, hoặc nhắm tít lắc đầu từ chối khi no căng
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
        elif expr in ("belly_up", "starved_dead"):
            # Mắt X X trôi lờ đờ khi ngửa bụng hoặc chết đói
            p.setBrush(Qt.BrushStyle.NoBrush)
            d = er * 0.72 if expr == "starved_dead" else er * 0.65
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
        elif expr in ("pleading", "caged_sad", "hungry_beg"):
            # Mắt to rưng rưng long lanh (giống ảnh mẫu), con ngươi liếc độc lập mượt theo chuột!
            is_plead = expr in ("pleading", "hungry_beg")
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
    elif expr in ("belly_up", "starved_dead"):
        # Miệng hé lè lưỡi nhỏ lờ đờ
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(mouth_x - 4.8, mouth_y + 1.0), QPointF(mouth_x + 4.8, mouth_y + 1.0))
        p.setBrush(QColor("#ff758f"))
        p.drawEllipse(QRectF(mouth_x - 2.6, mouth_y + 0.5, 5.2, 5.5))
    elif expr == "full_shake":
        # Miệng mím phồng má từ chối khi no căng ("ừm ừm, no rồi!")
        p.setBrush(Qt.BrushStyle.NoBrush)
        mp = QPainterPath()
        mp.moveTo(mouth_x - 5.5, mouth_y + 1.8)
        mp.quadTo(mouth_x - 2.2, mouth_y - 1.4, mouth_x, mouth_y + 1.6)
        mp.quadTo(mouth_x + 2.2, mouth_y + 4.2, mouth_x + 5.5, mouth_y + 1.4)
        p.drawPath(mp)
    elif expr == "hungry_beg":
        # Miệng mở đóng nhẹ theo nhịp "măm măm" đòi ăn!
        nom = 0.5 + 0.5 * math.sin(st.t_sec * 12.0)
        if nom > 0.35:
            p.setBrush(QColor("#ff6b81"))
            p.drawEllipse(QPointF(mouth_x, mouth_y + 1.4), 4.0 + nom * 1.4, 2.2 + nom * 3.8)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(mouth_x - 4.2, mouth_y - 1.5, 8.4, 6.0), 200 * 16, 140 * 16)
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


def _draw_pointing_fin(
    p: QPainter,
    s: float,
    facing_front: bool,
    intensity: float,
    body_col: QColor,
    ventral_col: QColor,
    outline: QColor,
    t_sec: float,
) -> None:
    """Vẽ chiếc vây trước nhấc lên chỉ nhịp nhàng vào miệng đòi ăn (POINT_TO_MOUTH)."""
    p.save()
    p.setOpacity(max(0.0, min(1.0, intensity)))
    # Nhịp chỉ vây 3–4 lần liên tiếp về phía miệng
    tap = 0.5 + 0.5 * math.sin(t_sec * 13.0)

    if facing_front:
        base_x, base_y = 18.0 * s, 21.0 * s
        tip_x = (7.5 - tap * 3.2) * s
        tip_y = (13.0 - tap * 2.2) * s
    else:
        base_x, base_y = 1.5 * s, 21.5 * s
        tip_x = (-8.5 - tap * 3.2) * s
        tip_y = (12.8 - tap * 2.2) * s

    fin = QPainterPath()
    fin.moveTo(base_x, base_y)
    fin.cubicTo(
        base_x - 3.0 * s, base_y - 10.0 * s,
        tip_x + 4.5 * s, tip_y - 4.5 * s,
        tip_x, tip_y,
    )
    fin.cubicTo(
        tip_x - 1.5 * s, tip_y + 4.2 * s,
        base_x - 8.0 * s, base_y + 3.5 * s,
        base_x, base_y,
    )
    fin.closeSubpath()

    p.setPen(QPen(outline, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(ventral_col)
    p.drawPath(fin)

    # Điểm sáng nhỏ trên vây
    p.setPen(QPen(body_col, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(base_x - 3.0 * s, base_y - 3.5 * s), QPointF(tip_x + 3.2 * s, tip_y + 0.8 * s))

    # Gạch nhịp nhỏ cạnh đầu vây khi chạm nhịp chỉ
    if tap > 0.65:
        p.setPen(QPen(QColor("#ffbe0b"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(tip_x - 4.0 * s, tip_y - 3.0 * s), QPointF(tip_x - 6.5 * s, tip_y - 4.8 * s))
        p.drawLine(QPointF(tip_x - 4.2 * s, tip_y + 1.5 * s), QPointF(tip_x - 7.0 * s, tip_y + 2.2 * s))
    p.restore()


