"""Các hàm toán học và hình học phục vụ vật lý 2D & nhảy sóng trên thanh tiêu đề cửa sổ."""
from __future__ import annotations

import math
import sys

from PySide6.QtCore import QRect

from pet.config import PORPOISE_MIN_SAFE_W
from pet.models import TrackedWindow


def angle_diff(a: float, b: float) -> float:
    return (b - a + math.pi) % math.tau - math.pi


def lerp_angle_deg(current_deg: float, target_deg: float, alpha: float) -> float:
    """Nội suy góc ngắn nhất theo độ để tránh nhảy góc cứng nhắc."""
    diff = (target_deg - current_deg + 180.0) % 360.0 - 180.0
    return current_deg + diff * alpha


def window_safe_zone(win: QRect) -> tuple[float, float] | None:
    """Tính vùng bơi an toàn [safe_min_x, safe_max_x] trên thanh tiêu đề cửa sổ.

    - macOS: chừa ~84px bên trái tránh 3 nút đèn giao thông, ~40px bên phải.
    - Windows/Linux: chừa ~30px bên trái và ~150px bên phải tránh cụm Minimize/Maximize/Close.
    - Trả về None nếu chiều rộng vùng khả dụng < PORPOISE_MIN_SAFE_W (310px).
    """
    if sys.platform == "darwin":
        safe_min_x = float(win.left() + 84)
        safe_max_x = float(win.right() - 40)
    else:
        safe_min_x = float(win.left() + 30)
        safe_max_x = float(win.right() - 150)
    if (safe_max_x - safe_min_x) < PORPOISE_MIN_SAFE_W:
        return None
    return safe_min_x, safe_max_x


def check_window_surface_snap(
    fish_x: float,
    fish_y: float,
    fish_w: float,
    fish_h: float,
    tracked_windows: list[TrackedWindow],
) -> tuple[bool, TrackedWindow | None, float, float]:
    """Kiểm tra cá có đang lướt sát mép trên cửa sổ đủ rộng để tự động đáp xuống mặt nước hay không."""
    fish_bottom = fish_y + fish_h * 0.72
    fish_center_x = fish_x + fish_w * 0.5

    for tw in tracked_windows:
        zone = window_safe_zone(tw.rect)
        if zone is None:
            continue
        safe_min_x, safe_max_x = zone
        if safe_min_x <= fish_center_x <= safe_max_x:
            if abs(fish_bottom - tw.rect.top()) <= 12.0:
                return True, tw, safe_min_x, safe_max_x
    return False, None, 0.0, 0.0
