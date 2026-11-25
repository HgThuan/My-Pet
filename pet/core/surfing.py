"""Bộ điều khiển Nhảy sóng trên thanh tiêu đề cửa sổ (Porpoising) & Ngó đầu (Window Peeking)."""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QGuiApplication

from pet.config import FPS, SIZE, HungerState
from pet.core.math_utils import window_safe_zone
from pet.models import Particle, TrackedWindow

if TYPE_CHECKING:
    from pet.core.pet import GoldenFishPet


class WindowSurfController:
    """Quản lý vùng an toàn trên cửa sổ, đo khoảng trần, cung nhảy parabol và xuyên chuột rìa."""

    def __init__(self, pet: GoldenFishPet):
        self.pet = pet

    def target_py(self, win_top: float) -> float:
        """Tính tọa độ Y cửa sổ Pet sao cho bụng cá chìm ~10px dưới đường viền cửa sổ."""
        pet = self.pet
        depth_scale = (0.85 + 0.25 * max(0.0, min(1.0, pet.depth))) * max(0.15, pet.dive_scale)
        bounds = pet.virtual_rect()
        raw_y = win_top - (SIZE / 2.0 + 4.0 + 20.0 * depth_scale)
        return max(bounds.top() - 42.0, min(bounds.bottom() - SIZE - 4.0, raw_y))

    def ceiling_info(self, win: QRect, base_py: float | None = None) -> tuple[float, float]:
        """Tính chính xác (min_safe_py, available_rise) từ đỉnh vây lưng cá tới trần màn hình."""
        pet = self.pet
        screen = QGuiApplication.screenAt(win.center()) or QGuiApplication.primaryScreen()
        screen_top = float(screen.availableGeometry().top()) if screen is not None else float(pet.virtual_rect().top())
        depth_scale = (0.85 + 0.25 * max(0.0, min(1.0, pet.depth))) * max(0.15, pet.dive_scale)
        fin_top_offset = (SIZE / 2.0 + 4.0) - 52.0 * depth_scale
        min_safe_py = (screen_top + 8.0) - fin_top_offset
        ref_py = self.target_py(float(win.top())) if base_py is None else base_py
        available_rise = max(0.0, ref_py - min_safe_py)
        return min_safe_py, available_rise

    def spawn_surface_splash(self, win_top: float, play_sound: bool = True) -> None:
        pet = self.pet
        fcx = pet.px + SIZE / 2.0
        pet.splash_overlay.trigger_takeoff_at(fcx, win_top)
        if play_sound:
            pet.sound.play_splash()
        local_wy = max(46.0, min(SIZE - 16.0, win_top - pet.py))
        for side in (-1, 1):
            for _ in range(3):
                pet.particles.append(Particle(
                    kind="water_drop",
                    x=SIZE / 2.0 + side * random.uniform(8.0, 22.0),
                    y=local_wy - random.uniform(0.0, 5.0),
                    vx=side * random.uniform(1.8, 4.4),
                    vy=random.uniform(-4.8, -2.1),
                    life=28,
                    max_life=28,
                    size=random.uniform(5.2, 8.6),
                    color=QColor("#9bf6ff"),
                ))

    def launch_porpoise_arc(self, win: QRect) -> None:
        """Phóng cá lên theo cung parabol đảm bảo không chạm trần màn hình (H = vy^2 / 2g)."""
        pet = self.pet
        fcx = pet.px + SIZE / 2.0
        safe_min_x = pet._perch_safe_min
        safe_max_x = pet._perch_safe_max
        rem = (safe_max_x - fcx) if pet._perch_dir > 0 else (fcx - safe_min_x)
        if rem < 115.0:
            pet._perch_dir *= -1

        porpoise_g = 0.30
        _, available_rise = self.ceiling_info(win, pet.py)
        if available_rise < 16.0:
            pet._surf_phase = "dive_out"
            pet._porpoise_dive_ticks = 26
            pet.vy = 3.2
            pet.vx = pet._perch_dir * 3.0
            pet._set_direction(1 if pet.vx > 0 else -1)
            return

        desired_h = random.uniform(44.0, 74.0)
        target_h = min(desired_h, available_rise * 0.88)
        vy_mag = math.sqrt(2.0 * porpoise_g * max(12.0, target_h))

        safe_span = max(250.0, safe_max_x - safe_min_x)
        vx_scale = max(0.68, min(1.0, target_h / 52.0))
        vx_mag = min(4.5, max(2.8, safe_span / 85.0)) * vx_scale

        pet.vx = pet._perch_dir * vx_mag
        pet.vy = -vy_mag
        pet._set_direction(1 if pet.vx > 0 else -1)
        pet._surf_phase = "arc"
        pet._surf_landed = True
        pet.facing_front = False
        pet.impulse_squash(1.20, 0.82)
        self.spawn_surface_splash(float(win.top()), play_sound=True)

    def start_window_drop(self) -> None:
        """Giật mình hụt chân rơi tự do ngắn khi cửa sổ đang lướt bị đóng/thu nhỏ."""
        pet = self.pet
        self.clear_click_through()
        pet.state = "window_drop"
        pet._window_drop_ticks = 36
        pet._surf_landed = False
        pet._surf_phase = "approach"
        pet._surf_snap_cooldown = int(3.6 * FPS)
        pet._perch_rect = None
        pet._perch_wid = 0
        pet.facing_front = False
        pet.vx *= 0.4
        pet.vy = 1.6
        pet.impulse_squash(0.80, 1.26)
        pet.spawn_particle("excl")
        pet.set_expression("surprised", 42)

    def enter_surf_on(
        self,
        tw: TrackedWindow,
        safe_min_x: float,
        safe_max_x: float,
        already_landed: bool = False,
    ) -> None:
        pet = self.pet
        pet._perch_wid = tw.wid
        pet._perch_rect = tw.rect
        pet._perch_safe_min = safe_min_x
        pet._perch_safe_max = safe_max_x
        pet.state = "window_surf"
        pet._perch_ticks = random.randint(420, 640)
        pet.facing_front = False
        pet.depth_target = 0.92
        pet._surf_landed = False
        pet._surf_balance_deg = 0.0
        pet._surf_drag_ticks = 0
        pet._porpoise_arcs_left = random.choice([1, 2, 2, 3])
        pet._porpoise_dip_ticks = 0
        pet._porpoise_dive_ticks = 0

        fcx = pet.px + SIZE / 2.0
        mid_safe = (safe_min_x + safe_max_x) * 0.5
        if safe_min_x + 30.0 <= fcx <= safe_max_x - 30.0:
            pet._perch_dir = 1 if fcx <= mid_safe else -1
            start_x = fcx
        elif fcx < safe_min_x + 30.0:
            pet._perch_dir = 1
            start_x = safe_min_x + 36.0
        else:
            pet._perch_dir = -1
            start_x = safe_max_x - 36.0

        pet.target_x = start_x - SIZE / 2.0
        pet.target_y = self.target_py(float(tw.rect.top()))

        if already_landed:
            self.launch_porpoise_arc(tw.rect)
        else:
            pet._surf_phase = "approach"
            if abs(pet.vx) > 0.2:
                pet._set_direction(1 if pet.vx > 0 else -1)

    def update_click_through(self, cur: QPoint) -> None:
        """Ủy quyền cho cơ chế Xuyên chuột thông minh 24/7 trên GoldenFishPet."""
        self.pet._update_smart_click_through(cur)

    def clear_click_through(self) -> None:
        self.pet._clear_click_through()

    def trigger_perch(self, mode: str | None = None) -> bool:
        """Chủ động tìm cửa sổ đủ rộng & đủ khoảng trống trần để nhảy sóng hoặc thò đầu ngó."""
        pet = self.pet
        if (
            pet.state in ("caged", "breaking_out", "starved_dead", "shake_head_full", "revive")
            or pet.hunger_state == HungerState.DEAD
        ):
            return False
        if not pet.tracked_windows:
            pet.tracked_windows = pet.window_tracker.sample_tracked()
            pet.open_windows = [tw.rect for tw in pet.tracked_windows]

        eligible: list[tuple[TrackedWindow, float, float]] = []
        for tw in pet.tracked_windows[: min(6, len(pet.tracked_windows))]:
            zone = window_safe_zone(tw.rect)
            if zone is None:
                continue
            _, avail_rise = self.ceiling_info(tw.rect)
            if avail_rise >= 24.0:
                eligible.append((tw, zone[0], zone[1]))
        if not eligible:
            return False

        tw, safe_min_x, safe_max_x = random.choice(eligible)
        win = tw.rect
        bounds = pet.virtual_rect()
        has_peek_headroom = win.top() >= bounds.top() + 36
        if mode is not None:
            chosen = mode
        elif has_peek_headroom:
            chosen = "window_surf" if random.random() < 0.80 else "window_peek"
        else:
            chosen = "window_surf"

        if chosen == "window_surf":
            self.enter_surf_on(tw, safe_min_x, safe_max_x, already_landed=False)
            return True

        pet._perch_wid = tw.wid
        pet._perch_rect = win
        pet._perch_safe_min = safe_min_x
        pet._perch_safe_max = safe_max_x
        pet.state = "window_peek"
        pet._perch_ticks = random.randint(220, 340)
        pet._perch_dir = random.choice([-1, 1])
        pet.facing_front = False
        pet.depth_target = 0.92
        tx = random.uniform(safe_min_x + 20.0, max(safe_min_x + 24.0, safe_max_x - 20.0))
        pet.target_x = tx - SIZE / 2.0
        pet.target_y = win.top() - SIZE / 2.0 - 19.0
        return True
