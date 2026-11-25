"""Bộ máy trạng thái hành vi (State Behavior Handlers) dạng bảng điều phối cho Golden Fish Pet.

Mỗi trạng thái (caged, breaking_out, starved_dead, revive, shake_head_full, point_to_mouth,
window_surf, window_peek, puffed, deflate_zoom, play_dead, swim...) được tách thành hàm độc lập
và đăng ký vào STATE_HANDLERS để dễ bảo trì, đọc hiểu và mở rộng thêm hành vi mới.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QPoint, QRectF

from pet.config import (
    BODY_TILT_DAMPING,
    BODY_TILT_MAX_DEG,
    BODY_TILT_THRESHOLD_DEG,
    CURSOR_ATTENTION_RADIUS,
    FLIP_HYSTERESIS_PX,
    FPS,
    SIZE,
    HungerState,
)
from pet.core.math_utils import (
    check_window_surface_snap,
    lerp_angle_deg,
    window_safe_zone,
)

if TYPE_CHECKING:
    from pet.core.pet import GoldenFishPet


@dataclass(slots=True)
class StepContext:
    bounds: QRectF
    cur: QPoint
    min_x: float
    max_x: float
    min_y: float
    max_y: float


StateHandler = Callable[["GoldenFishPet", StepContext], None]


def step_caged(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.vx = 0.0
    pet.vy = 0.0
    pet.pitch_deg = 0.0
    pet.bank_deg = 0.0
    pet.puff_factor *= 0.85
    pet.facing_front = True
    pet.depth_target = 0.60

    if pet.cage_drop_ticks > 0:
        pet.cage_drop_ticks -= 1
        if pet.cage_drop_ticks == 6 and not pet.cage_lock_played:
            pet.cage_lock_played = True
            pet.sound.play_cage_lock()
            pet.impulse_squash(1.18, 0.84)
            for sx in (-28.0, 0.0, 28.0):
                pet.spawn_particle("smoke", SIZE / 2.0 + sx, SIZE / 2.0 + 52.0)
            for _ in range(2):
                pet.spawn_particle("spark", SIZE / 2.0, SIZE / 2.0 - 54.0)
    elif not pet.cage_dragging:
        if pet.cage_plead_ticks > 0:
            pet.cage_plead_ticks -= 1
            target_swing = math.sin(pet.frame * 0.24) * 3.0
            pet.cage_swing_deg += (target_swing - pet.cage_swing_deg) * 0.24
            pet.cage_swing_vel = 0.0
            if pet.frame % 36 == 0:
                pet.spawn_particle("tear")
            if pet.cage_plead_ticks == 0:
                pet.cage_plead_cooldown = random.randint(8 * FPS, 15 * FPS)
        else:
            pet.cage_plead_cooldown -= 1
            pet.cage_swing_vel = (pet.cage_swing_vel - pet.cage_swing_deg * 0.09) * 0.86
            pet.cage_swing_deg += pet.cage_swing_vel
            if abs(pet.cage_swing_deg) < 0.03 and abs(pet.cage_swing_vel) < 0.03:
                pet.cage_swing_deg = 0.0
                pet.cage_swing_vel = 0.0
            if pet.cage_plead_cooldown <= 0:
                pet.cage_plead_ticks = random.randint(int(3.2 * FPS), int(4.4 * FPS))
                pet.spawn_particle("tear")


def step_breaking_out(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.cage_break_ticks -= 1
    prog = 1.0 - (pet.cage_break_ticks / max(1, pet.cage_break_total))

    if prog < 0.36:
        pet.vx = 0.0
        pet.vy = 0.0
        pet.facing_front = True
        pet.cage_muscular = min(1.0, prog / 0.30)
        pet.cage_swing_deg = math.sin(pet.frame * 1.45) * (2.2 + 2.8 * prog)
        pet.squash_x = 1.0 + 0.11 * pet.cage_muscular
        pet.squash_y = 1.0 + 0.07 * pet.cage_muscular
        if pet.frame % 6 == 0:
            pet.spawn_particle("smoke", SIZE / 2.0 + random.uniform(-22, 22), SIZE / 2.0 - 8.0)
    elif prog < 0.78:
        if not pet.cage_break_sound_played:
            pet.cage_break_sound_played = True
            pet.sound.play_metal_bend()
        bp = (prog - 0.36) / 0.42
        pet.cage_bend_amount = 1.0 - ((1.0 - bp) ** 2.3)
        pet.cage_muscular = 1.0
        pet.cage_swing_deg = math.sin(pet.frame * 1.9) * (4.2 * (1.0 - bp * 0.35))
        grip_x = 17.5 + pet.cage_bend_amount * 28.5
        if pet.frame % 2 == 0:
            pet.spawn_particle("spark", SIZE / 2.0 - grip_x, SIZE / 2.0 + 11.0)
            pet.spawn_particle("spark", SIZE / 2.0 + grip_x, SIZE / 2.0 + 11.0)
        if pet.frame % 4 == 0:
            pet.spawn_particle("smoke", SIZE / 2.0 + random.choice([-1, 1]) * grip_x, SIZE / 2.0 + 10.0)
    else:
        if not pet.cage_break_released:
            pet.cage_break_released = True
            pet.falling_cage_overlay.trigger_at(
                pet.px + SIZE / 2.0,
                pet.py + SIZE / 2.0 + 4.0,
                pet.cage_swing_deg,
                pet.cage_bend_amount,
                ctx.bounds.bottom(),
            )
            pet.sound.play_pop()
            for _ in range(10):
                pet.spawn_particle("spark", SIZE / 2.0 + random.uniform(-35, 35), SIZE / 2.0 + random.uniform(-10, 20))
            for _ in range(6):
                pet.spawn_particle("smoke", SIZE / 2.0 + random.uniform(-35, 35), SIZE / 2.0 + random.uniform(-10, 25))
            for _ in range(7):
                pet.spawn_particle("star")
            dir_out = random.choice([-1, 1])
            pet.direction = dir_out
            pet.facing_front = False
            pet.vx = dir_out * 4.4
            pet.vy = -5.4
            pet.impulse_squash(0.76, 1.28)
        pet.vy += 0.22
        pet.vx *= 0.97
        pet.px += pet.vx
        pet.py += pet.vy
        pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y, bouncy=True)
        pet.pitch_deg = max(-28.0, min(28.0, pet.vy * 4.2 * pet.direction))
        if pet.frame % 3 == 0:
            pet.spawn_particle("star")

    if pet.cage_break_ticks <= 0:
        pet.state = "swim"
        pet.cage_bend_amount = 0.0
        pet.cage_muscular = 0.0
        pet.cage_swing_deg = 0.0
        pet.cage_swing_vel = 0.0
        pet.cage_break_released = False
        pet.set_expression("proud", int(2.5 * FPS))
        pet._pick_new_swim_target(min_y=ctx.min_y)


def step_dive_hide(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.vy = min(22.0, pet.vy + 1.1)
    pet.py += pet.vy
    pet.pitch_deg = 52.0 * pet.direction
    pet.dive_scale = max(0.25, pet.dive_scale - 0.032)
    if pet.frame % 2 == 0:
        pet.spawn_particle("trail_bubble")
    if pet.py >= ctx.bounds.bottom() - SIZE * 0.35:
        pet.sound.play_splash()
        pet.splash_overlay.trigger_at(pet.px + SIZE / 2.0, ctx.bounds.bottom())
        pet.state = "hidden"
        pet.hide()


def step_surface_show(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.vy *= 0.91
    pet.py += pet.vy
    pet.px = max(ctx.min_x, min(ctx.max_x, pet.px + pet.vx))
    pet.dive_scale = min(1.0, pet.dive_scale + 0.045)
    pet.pitch_deg = -32.0 * pet.direction
    if pet.frame % 2 == 0:
        pet.spawn_particle("trail_bubble")
    if pet.dive_scale >= 0.99 and (abs(pet.vy) < 1.2 or pet.py <= pet._saved_surface_y):
        pet.dive_scale = 1.0
        pet.state = "swim"
        pet.set_expression("happy", 90)
        pet.impulse_squash(1.16, 0.86)


def step_drag(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.puff_factor *= 0.85
    pet.pitch_deg = max(-22.0, min(22.0, pet._drag_vel_y * 1.4))


def step_swallow_ready(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.vx *= 0.72
    pet.vy *= 0.72
    if pet._drag_leave_grace > 0:
        pet._drag_leave_grace -= 1
        if pet._drag_leave_grace == 0:
            if pet.hunger_state == HungerState.DEAD:
                pet.enter_starved_dead()
            else:
                pet.state = "swim"
            pet.suction_alpha = 0.0
            pet.mouth_locked = False


def step_starved_dead(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.puff_factor *= 0.90
    pet.facing_front = False
    top_dead_y = ctx.min_y + 4.0
    dy_top = top_dead_y - pet.py
    if abs(dy_top) > 6.0:
        pet.vy = pet.vy * 0.94 + max(-0.08, min(0.08, dy_top * 0.004))
    else:
        pet.vy = pet.vy * 0.92 + math.sin(pet.frame * 0.03) * 0.02
    pet.vx *= 0.97
    pet.px = max(ctx.min_x, min(ctx.max_x, pet.px + pet.vx + math.sin(pet.frame * 0.02) * 0.14))
    pet.py = max(ctx.min_y, min(ctx.max_y, pet.py + pet.vy))
    pet.pitch_deg *= 0.90
    pet.depth_target = 0.72


def step_revive(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.revive_ticks -= 1
    prog = 1.0 - (pet.revive_ticks / max(1, pet.revive_total))
    pet.spin_deg = 180.0 * max(0.0, 1.0 - min(1.0, prog * 2.2))
    pet.vx *= 0.92
    pet.vy *= 0.92
    pet.px = max(ctx.min_x, min(ctx.max_x, pet.px + pet.vx))
    pet.py = max(ctx.min_y, min(ctx.max_y, pet.py + pet.vy))
    if pet.revive_ticks % 12 == 0:
        pet.spawn_particle("heart")
    if pet.revive_ticks <= 0:
        pet.spin_deg = 0.0
        pet.state = "swim"
        pet.set_expression("happy", 90)


def step_shake_head_full(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.full_shake_ticks -= 1
    pet.vx *= 0.84
    pet.vy *= 0.84
    pet.pitch_deg *= 0.85
    pet.facing_front = True
    pet.px = max(ctx.min_x, min(ctx.max_x, pet.px + pet.vx))
    pet.py = max(ctx.min_y, min(ctx.max_y, pet.py + pet.vy))
    if pet.full_shake_ticks % 28 == 0:
        pet.spawn_particle("bubble")
    if pet.full_shake_ticks <= 0:
        pet.state = "swim"
        pet.facing_front = False


def step_point_to_mouth(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.point_mouth_ticks -= 1
    pet.vx *= 0.84
    pet.vy *= 0.84
    pet.pitch_deg *= 0.88
    fcx, _ = pet.center_global()
    if abs(ctx.cur.x() - fcx) > 25.0:
        pet._set_direction(1 if ctx.cur.x() > fcx else -1)
    pet.px = max(ctx.min_x, min(ctx.max_x, pet.px + pet.vx))
    pet.py = max(ctx.min_y, min(ctx.max_y, pet.py + pet.vy))
    if pet.point_mouth_ticks <= 0 or pet.hunger_state == HungerState.NORMAL:
        pet.state = "swim"
        pet.facing_front = False


def step_swallow_gulp(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.swallow_ticks -= 1
    pet.vx *= 0.82
    pet.vy *= 0.82
    pet.eating_file_progress = min(1.0, 1.0 - pet.swallow_ticks / 24.0)
    if pet.swallow_ticks <= 0:
        pet.eating_file_progress = -1.0
        pet.suction_alpha = 0.0
        pet.state = "eat_file"
        pet.impulse_squash(1.20, 0.84)
        for _ in range(5):
            pet.spawn_particle("crumb")


def step_eat_file(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.chew_ticks -= 1
    pet.vx *= 0.84
    pet.vy *= 0.84
    pet.pitch_deg *= 0.88
    if pet.chew_ticks % 11 == 0:
        pet.impulse_squash(1.12, 0.90)
        pet.spawn_particle("crumb")
        if pet.chew_ticks % 22 == 0:
            pet.spawn_particle("star")
    if pet.chew_ticks == 12:
        pet.sound.play_pop()
        for _ in range(9):
            pet.spawn_particle("bubble")
    if pet.chew_ticks <= 0:
        pet.trigger_celebrate_figure8()


def step_nauseous_vomit(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.nauseous_ticks -= 1
    pet.vx *= 0.88
    pet.vy *= 0.88
    pet.pitch_deg = -10.0 * pet.direction
    if pet.nauseous_ticks % 3 == 0:
        pet.spawn_particle("rainbow_bubble")
        pet.spawn_particle("rainbow_bubble")
        pet.impulse_squash(1.10, 0.92)
    if pet.nauseous_ticks <= 0:
        pet.state = "belly_up"
        pet.belly_up_ticks = 3 * FPS
        pet.vx = random.uniform(-0.4, 0.4)
        pet.vy = -0.35
        pet.pitch_deg = 0.0


def step_belly_up(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.belly_up_ticks -= 1
    pet.vx *= 0.985
    pet.vy = pet.vy * 0.98 - 0.008
    pet.px += pet.vx
    pet.py += pet.vy
    pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y, bouncy=False)
    if pet.belly_up_ticks <= 0:
        pet.state = "swim"
        pet.impulse_squash(1.16, 0.86)
        pet.set_expression("sleepy", 50)


def step_sneeze_windup(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.sneeze_ticks -= 1
    pet.vx *= 0.80
    pet.vy *= 0.80
    pet.pitch_deg = -12.0 * pet.direction
    pet.squash_x = 1.14
    pet.squash_y = 1.12
    if pet.sneeze_ticks <= 0:
        pet.state = "sneeze_burst"
        pet.sneeze_ticks = 26
        pet.vx = -pet.direction * 7.8
        pet.vy = random.uniform(-1.4, 1.4)
        pet.impulse_squash(0.74, 1.30)
        pet.sound.play_pop()
        for _ in range(5):
            pet.spawn_particle("water_drop")
        for _ in range(3):
            pet.spawn_particle("bubble")


def step_sneeze_burst(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.sneeze_ticks -= 1
    pet.vx *= 0.91
    pet.vy *= 0.91
    pet.px += pet.vx
    pet.py += pet.vy
    pet.pitch_deg *= 0.86
    pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y)
    if pet.sneeze_ticks <= 0:
        pet.state = "swim"
        pet.set_expression("shy", 65)


def step_celebrate_fig8(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.fig8_ticks -= 1
    prog = 1.0 - (pet.fig8_ticks / max(1, pet.fig8_total))
    t = prog * math.tau
    ox, oy = pet.fig8_origin
    nx = max(ctx.min_x, min(ctx.max_x, ox + math.sin(t) * 62.0))
    ny = max(ctx.min_y, min(ctx.max_y, oy + math.sin(2.0 * t) * 28.0))
    pet.vx = nx - pet.px
    pet.vy = ny - pet.py
    pet.px, pet.py = nx, ny
    if abs(pet.vx) > 0.25:
        pet.direction = 1 if pet.vx > 0 else -1
    pet.pitch_deg = max(-28.0, min(28.0, pet.vy * 4.5 * pet.direction))
    if pet.fig8_ticks % 4 == 0:
        pet.spawn_particle("trail_bubble")
    if pet.fig8_ticks <= 0:
        pet.state = "swim"
        pet.set_expression("happy", 70)


def step_window_drop(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet._window_drop_ticks -= 1
    pet.vy = min(10.5, pet.vy + 0.42)
    pet.vx *= 0.96
    pet.px += pet.vx
    pet.py += pet.vy
    pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y, bouncy=True)
    pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, 28.0 * pet.direction, 0.16)
    if pet.frame % 4 == 0:
        pet.spawn_particle("bubble")
    if pet._window_drop_ticks <= 0:
        pet.state = "swim"
        pet.vy *= 0.35
        pet.impulse_squash(1.18, 0.84)
        pet._pick_new_swim_target(min_y=ctx.min_y)


def step_window_perch(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet._perch_ticks -= 1
    if (
        pet._perch_rect is None
        or pet.is_overloaded
        or pet.foods
        or pet.hold_still
        or pet.chase_mode
    ):
        pet.surfing.clear_click_through()
        pet.state = "swim"
        pet._perch_rect = None
        pet._perch_wid = 0
        pet._surf_landed = False
        pet.facing_front = False
        return

    if pet._perch_wid and pet.frame % 3 == 0:
        live_rect = pet.window_tracker.get_window_rect(pet._perch_wid)
        if live_rect is None:
            pet.surfing.start_window_drop()
            return
        if live_rect != pet._perch_rect:
            wdx = live_rect.left() - pet._perch_rect.left()
            wdy = live_rect.top() - pet._perch_rect.top()
            pet._perch_rect = live_rect
            zone = window_safe_zone(live_rect)
            if zone is None:
                pet.surfing.start_window_drop()
                return
            pet._perch_safe_min, pet._perch_safe_max = zone
            if pet.state == "window_surf" and pet._surf_landed and (abs(wdx) >= 1 or abs(wdy) >= 1):
                pet.px += wdx
                pet.py += wdy
                target_bal = max(-32.0, min(32.0, -wdx * 2.2))
                pet._surf_balance_deg += (target_bal - pet._surf_balance_deg) * 0.48
                was_dragged = pet._surf_drag_ticks > 0
                pet._surf_drag_ticks = 24
                if not was_dragged:
                    pet.spawn_particle("excl")
                    pet.impulse_squash(0.86, 1.16)
                if pet.frame % 6 == 0:
                    pet.spawn_particle("water_drop", SIZE / 2.0, SIZE / 2.0 + 18.0)

    win = pet._perch_rect
    if pet.state == "window_surf":
        _step_window_surf(pet, ctx, win)
    else:
        _step_window_peek(pet, ctx)


def _step_window_surf(pet: GoldenFishPet, ctx: StepContext, win) -> None:
    zone = window_safe_zone(win)
    if zone is None:
        pet.surfing.start_window_drop()
        return
    safe_min_x, safe_max_x = zone
    pet._perch_safe_min, pet._perch_safe_max = safe_min_x, safe_max_x
    left_px = safe_min_x - SIZE / 2.0
    right_px = safe_max_x - SIZE / 2.0
    surf_py = pet.surfing.target_py(float(win.top()))
    fcx = pet.px + SIZE / 2.0

    if pet._surf_drag_ticks > 0:
        pet._surf_drag_ticks -= 1
    else:
        pet._surf_balance_deg *= 0.84

    if pet._surf_phase == "approach":
        tx = max(left_px + 28.0, min(right_px - 28.0, pet.target_x))
        ty = surf_py + 12.0
        dx, dy = tx - pet.px, ty - pet.py
        dist = max(1.0, math.hypot(dx, dy))
        steer_spd = min(3.6, max(2.2, dist * 0.045))
        pet.vx += ((dx / dist) * steer_spd - pet.vx) * 0.11
        pet.vy += ((dy / dist) * steer_spd - pet.vy) * 0.11
        pet.px += pet.vx
        pet.py += pet.vy
        if abs(pet.vx) > 0.20:
            pet._set_direction(1 if pet.vx > 0 else -1)
        vel_deg = max(-35.0, min(35.0, math.degrees(math.atan2(pet.vy, max(1.0, abs(pet.vx)))) * 0.78))
        pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, vel_deg * pet.direction, 0.18)

        if dist <= 22.0 or (abs(pet.py - surf_py) <= 16.0 and (safe_min_x + 20.0) <= (pet.px + SIZE / 2.0) <= (safe_max_x - 20.0)):
            pet.surfing.launch_porpoise_arc(win)
        elif pet._perch_ticks <= 0:
            pet.surfing.clear_click_through()
            pet.state = "swim"
            pet._perch_rect = None
            pet._perch_wid = 0
        return

    if pet._surf_phase == "arc":
        pet.vy += 0.30
        pet.px += pet.vx
        pet.py += pet.vy

        min_safe_py, _ = pet.surfing.ceiling_info(win, surf_py)
        if pet.py < min_safe_py:
            pet.py = min_safe_py
            if pet.vy < 0.0:
                pet.vy = 0.35

        if pet.px < left_px:
            pet.px = left_px
            pet.vx = abs(pet.vx) * 0.55
            pet._perch_dir = 1
        elif pet.px > right_px:
            pet.px = right_px
            pet.vx = -abs(pet.vx) * 0.55
            pet._perch_dir = -1

        if abs(pet.vx) > 0.20:
            pet._set_direction(1 if pet.vx > 0 else -1)

        vel_deg = max(-35.0, min(35.0, math.degrees(math.atan2(pet.vy, max(1.0, abs(pet.vx)))) * 0.88))
        pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, vel_deg * pet.direction + pet._surf_balance_deg, 0.30)

        if pet.frame % 4 == 0:
            pet.spawn_particle("trail_bubble")

        if pet.vy > 0.0 and pet.py >= surf_py:
            pet.surfing.spawn_surface_splash(float(win.top()), play_sound=True)
            pet.impulse_squash(1.22, 0.80)
            pet._porpoise_arcs_left -= 1
            if pet._porpoise_arcs_left > 0 and pet._perch_ticks > 28:
                pet._surf_phase = "dip"
                pet._porpoise_dip_ticks = 22
                pet.vy = min(2.2, pet.vy * 0.42)
            else:
                pet._surf_phase = "dive_out"
                pet._porpoise_dive_ticks = 28
                pet.vy = max(3.4, min(5.4, pet.vy * 0.82))
                pet.vx *= 0.88
        return

    if pet._surf_phase == "dip":
        pet._porpoise_dip_ticks -= 1
        if (fcx <= safe_min_x + 48.0 and pet._perch_dir < 0) or (fcx >= safe_max_x - 48.0 and pet._perch_dir > 0):
            pet._perch_dir *= -1
            pet.vx = pet._perch_dir * max(2.2, abs(pet.vx) * 0.75)
            pet._set_direction(pet._perch_dir)
        else:
            pet.vx += (pet._perch_dir * 3.6 - pet.vx) * 0.14
            if abs(pet.vx) > 0.20:
                pet._set_direction(1 if pet.vx > 0 else -1)

        pet.vy -= 0.22
        pet.px = max(left_px, min(right_px, pet.px + pet.vx))
        pet.py = max(surf_py - 2.0, min(surf_py + 18.0, pet.py + pet.vy))

        vel_deg = max(-30.0, min(30.0, math.degrees(math.atan2(pet.vy, max(1.0, abs(pet.vx)))) * 0.80))
        pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, vel_deg * pet.direction + pet._surf_balance_deg, 0.28)
        if pet.frame % 3 == 0:
            pet.spawn_particle("trail_bubble")

        if pet._porpoise_dip_ticks <= 0:
            pet.surfing.launch_porpoise_arc(win)
        return

    # dive_out
    pet._porpoise_dive_ticks -= 1
    pet.vx *= 0.97
    pet.vy = pet.vy * 0.94 + 0.06
    pet.px += pet.vx
    pet.py += pet.vy
    pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y, bouncy=True)

    if abs(pet.vx) > 0.20:
        pet._set_direction(1 if pet.vx > 0 else -1)
    vel_deg = max(-35.0, min(35.0, math.degrees(math.atan2(pet.vy, max(1.0, abs(pet.vx)))) * 0.82))
    pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, vel_deg * pet.direction, 0.20)

    if pet.frame % 2 == 0:
        pet.spawn_particle("trail_bubble")
    if pet.frame % 6 == 0:
        pet.spawn_particle("bubble")

    if pet._porpoise_dive_ticks <= 0:
        pet.surfing.clear_click_through()
        pet.state = "swim"
        pet._perch_rect = None
        pet._perch_wid = 0
        pet._surf_landed = False
        pet._surf_phase = "approach"
        pet._surf_snap_cooldown = int(6.0 * FPS)
        pet.set_expression("happy", 65)
        pet._pick_new_swim_target(min_y=ctx.min_y)


def _step_window_peek(pet: GoldenFishPet, ctx: StepContext) -> None:
    if pet._perch_ticks <= 0:
        pet.state = "swim"
        pet._perch_rect = None
        pet._perch_wid = 0
        pet.facing_front = False
        return
    dx = pet.target_x - pet.px
    dy = pet.target_y - pet.py
    dist = math.hypot(dx, dy)
    if dist > 10.0:
        pet.vx += ((dx / dist) * 2.6 - pet.vx) * 0.10
        pet.vy += ((dy / dist) * 2.6 - pet.vy) * 0.10
        pet.px += pet.vx
        pet.py += pet.vy
        if abs(pet.vx) > 0.3:
            pet._set_direction(1 if pet.vx > 0 else -1)
        pet.facing_front = False
    else:
        pet.vx *= 0.78
        pet.vy *= 0.78
        pet.facing_front = True
        pet.pitch_deg *= 0.85
    pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y, bouncy=False)


def step_puffed(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.puff_factor = min(1.0, pet.puff_factor + 0.075)
    pet.vx *= 0.90
    pet.vy *= 0.90
    pet.pitch_deg *= 0.85
    pet.px = max(ctx.min_x, min(ctx.max_x, pet.px + pet.vx))
    pet.py = max(ctx.min_y, min(ctx.max_y, pet.py + pet.vy))
    pet.puff_ticks -= 1
    if pet.puff_ticks % 45 == 0:
        pet.spawn_particle("anger")
    if pet.puff_ticks <= 0:
        pet.state = "deflate_zoom"
        pet.facing_front = False
        pet.deflate_ticks = int(2.6 * FPS)
        ang = random.uniform(0, math.tau)
        pet.vx = math.cos(ang) * 14.0
        pet.vy = math.sin(ang) * 14.0
        pet.sound.play_pop()


def step_deflate_zoom(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.deflate_ticks -= 1
    pet.puff_factor = max(0.0, pet.puff_factor - 0.018)
    turn = math.sin(pet.frame * 0.28) * 0.16 + random.uniform(-0.08, 0.08)
    ang = math.atan2(pet.vy, pet.vx) + turn
    spd = 13.5 * (0.45 + 0.55 * (pet.deflate_ticks / (2.6 * FPS)))
    pet.vx = math.cos(ang) * spd
    pet.vy = math.sin(ang) * spd
    pet.px += pet.vx
    pet.py += pet.vy
    pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y, bouncy=True)
    pet.direction = 1 if pet.vx >= 0 else -1
    pet.pitch_deg = max(-35.0, min(35.0, (pet.vy / max(1.0, spd)) * 35.0 * pet.direction))
    if pet.frame % 2 == 0:
        pet.spawn_particle("puff_air")
    if pet.deflate_ticks <= 0:
        pet.state = "swim"
        pet.puff_factor = 0.0
        pet.vx *= 0.25
        pet.vy *= 0.25
        pet.set_expression("dizzy", 80)


def step_play_dead(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.puff_factor *= 0.9
    dx = pet.target_x - pet.px
    dy = pet.target_y - pet.py
    pet.vx = pet.vx * 0.95 + max(-0.06, min(0.06, dx * 0.0015))
    pet.vy = pet.vy * 0.95 + max(-0.12, min(0.06, dy * 0.0028))
    pet.px = max(ctx.min_x, min(ctx.max_x, pet.px + pet.vx + math.sin(pet.frame * 0.025) * 0.25))
    pet.py = max(ctx.min_y, min(ctx.max_y, pet.py + pet.vy + math.sin(pet.frame * 0.032) * 0.28))
    pet.pitch_deg = math.sin(pet.frame * 0.022) * 6.5
    pet.depth_target = 0.78
    if pet._dead_peek_ticks > 0:
        pet._dead_peek_ticks -= 1
    else:
        pet._dead_peek_cd -= 1
        if pet._dead_peek_cd <= 0:
            pet._dead_peek_ticks = int(0.65 * FPS)
            pet._dead_peek_cd = random.randint(6 * FPS, 10 * FPS)


def step_eat(pet: GoldenFishPet, ctx: StepContext) -> None:
    pet.vx *= 0.80
    pet.vy *= 0.80
    pet.pitch_deg *= 0.85
    food = pet._eating_food
    if food is None or food not in pet.foods:
        pet._eating_food = None
        pet.state = "swim"
        return
    food.bite_progress = min(1.0, food.bite_progress + 1.0 / 26.0)
    food.update()
    if pet.frame % 7 == 0:
        pet.spawn_particle("bubble")
    if food.bite_progress >= 1.0:
        food.close()
        if food in pet.foods:
            pet.foods.remove(food)
        pet._eating_food = None
        pet.state = "swim"
        pet._on_ate_morsel()
        if not pet.foods:
            pet.set_expression("love", 105)


def step_swim(pet: GoldenFishPet, ctx: StepContext) -> None:
    """Bơi lội 360° với lực đẩy Tail-Beat Impulse, nhìn theo chuột 3 lớp & mức độ đói."""
    pet.puff_factor *= 0.90
    fcx, fcy = pet.center_global()
    if pet.hold_still and not pet.foods and not pet.is_overloaded:
        pet.vx *= 0.85
        pet.vy *= 0.85
        pet.facing_front = False
        gaze_dx = ctx.cur.x() - fcx
        gaze_dy = ctx.cur.y() - fcy
        if pet.cursor_gaze_enabled and math.hypot(gaze_dx, gaze_dy) <= CURSOR_ATTENTION_RADIUS:
            if gaze_dx > FLIP_HYSTERESIS_PX:
                pet._set_direction(1)
            elif gaze_dx < -FLIP_HYSTERESIS_PX:
                pet._set_direction(-1)
            raw_deg = math.degrees(math.atan2(gaze_dy, max(1.0, abs(gaze_dx))))
            if abs(raw_deg) > BODY_TILT_THRESHOLD_DEG:
                blend = min(1.0, (abs(raw_deg) - BODY_TILT_THRESHOLD_DEG) / 8.0)
                clamped = max(-BODY_TILT_MAX_DEG, min(BODY_TILT_MAX_DEG, raw_deg))
                pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, clamped * pet.direction * blend, BODY_TILT_DAMPING)
            else:
                pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, 0.0, BODY_TILT_DAMPING)
        else:
            pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, 0.0, BODY_TILT_DAMPING)
        pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y, bouncy=False)
        return

    max_spd = 2.4
    base_steer = 0.075
    use_tail_impulse = True

    gaze_dx = ctx.cur.x() - fcx
    gaze_dy = ctx.cur.y() - fcy
    gaze_dist = math.hypot(gaze_dx, gaze_dy)
    gaze_active = (
        pet.cursor_gaze_enabled
        and gaze_dist <= CURSOR_ATTENTION_RADIUS
        and not pet.is_overloaded
        and not pet.foods
    )

    if pet.foods:
        nearest = min(pet.foods, key=lambda f: math.hypot(f.center()[0] - fcx, f.center()[1] - fcy))
        tx, ty = nearest.center()
        if math.hypot(tx - fcx, ty - fcy) < 38.0:
            pet._eating_food = nearest
            pet.state = "eat"
            pet.impulse_squash(1.18, 0.86)
            return
        max_spd = 5.4
        base_steer = 0.16
        pet.target_x, pet.target_y = tx - SIZE / 2.0, max(ctx.min_y, min(ctx.max_y, ty - SIZE / 2.0))
        pet.facing_front = False
    elif pet.is_overloaded:
        max_spd = 5.8
        base_steer = 0.18
        pet.retarget_ticks -= 2
        if pet.retarget_ticks <= 0:
            pet._pick_new_swim_target(min_y=ctx.min_y, fast=True)
        pet.facing_front = False
    elif pet.chase_mode:
        dx = ctx.cur.x() - fcx
        dy = ctx.cur.y() - fcy
        if math.hypot(dx, dy) > 48.0:
            max_spd = 4.6
            base_steer = 0.13
            pet.target_x = ctx.cur.x() - SIZE / 2.0
            pet.target_y = max(ctx.min_y, min(ctx.max_y, ctx.cur.y() - SIZE / 2.0))
            pet.facing_front = False
        else:
            pet.vx *= 0.88
            pet.vy *= 0.88
            pet.facing_front = True
            if pet.frame % 90 == 0:
                pet.set_expression("happy", 55)
            pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y, bouncy=False)
            return
    else:
        if pet.is_night_mode:
            max_spd = 1.1
            base_steer = 0.035
        elif pet.water_overlay.active and pet.water_overlay.phase == "break":
            max_spd = 2.8
            base_steer = 0.085
        elif pet.current_color_score < -0.32 and pet.wallpaper_aware:
            max_spd = 3.6
            base_steer = 0.11
            if pet.retarget_ticks > 25:
                pet.retarget_ticks = 20

        if gaze_active:
            max_spd = min(max_spd, 1.55)

        if pet.hunger_state == HungerState.HUNGRY:
            max_spd *= 0.50
            base_steer *= 0.65
        elif pet.hunger_state == HungerState.STARVING:
            max_spd *= 0.20
            base_steer *= 0.40
            starve_floor = max(ctx.min_y, ctx.max_y - 22.0)
            if pet.target_y < starve_floor - 30.0:
                pet.target_y = random.uniform(max(ctx.min_y, ctx.max_y - 55.0), ctx.max_y - 6.0)
            if pet.py < starve_floor:
                pet.vy += 0.045

        pet.retarget_ticks -= 1
        if pet.retarget_ticks <= 0 or math.hypot(pet.target_x - pet.px, pet.target_y - pet.py) < 30.0:
            pet._pick_new_swim_target(min_y=ctx.min_y)

    dx = pet.target_x - pet.px
    dy = pet.target_y - pet.py
    dist = math.hypot(dx, dy)
    if dist > 1.0:
        if use_tail_impulse:
            beat_pulse = abs(math.cos(pet.tail_phase)) ** 2.4
            impulse_mult = 0.35 + 1.55 * beat_pulse
            desired_vx = (dx / dist) * max_spd * (0.72 + 0.55 * beat_pulse)
            desired_vy = (dy / dist) * max_spd * (0.72 + 0.55 * beat_pulse)
            pet.vx += (desired_vx - pet.vx) * (base_steer * impulse_mult)
            pet.vy += (desired_vy - pet.vy) * (base_steer * impulse_mult)
        else:
            pet.vx += ((dx / dist) * max_spd - pet.vx) * base_steer
            pet.vy += ((dy / dist) * max_spd - pet.vy) * base_steer

    drag = 0.968 if use_tail_impulse else 0.975
    pet.vx *= drag
    pet.vy *= drag
    pet.px += pet.vx
    pet.py += pet.vy
    pet._apply_bounds(ctx.min_x, ctx.max_x, ctx.min_y, ctx.max_y, bouncy=True)

    # Tự động "tiếp nước" lên thanh tiêu đề cửa sổ
    if (
        pet.window_perch_enabled
        and pet.hunger_state == HungerState.NORMAL
        and pet._surf_snap_cooldown == 0
        and not pet.is_overloaded
        and not pet.foods
        and not pet.hold_still
        and not pet.chase_mode
        and not pet.water_overlay.active
        and not pet.is_night_mode
        and pet.vy > 0.15
        and pet.tracked_windows
    ):
        snapped, tw, s_min, s_max = check_window_surface_snap(
            pet.px, pet.py, SIZE, SIZE, pet.tracked_windows
        )
        if snapped and tw is not None:
            _, avail_rise = pet.surfing.ceiling_info(tw.rect)
            if avail_rise >= 24.0 and random.random() < 0.67:
                pet.surfing.enter_surf_on(tw, s_min, s_max, already_landed=False)
                return
            pet._surf_snap_cooldown = int(1.8 * FPS)

    spd_now = math.hypot(pet.vx, pet.vy)
    swim_pitch = 0.0
    if spd_now > 0.35:
        swim_pitch = max(
            -26.0,
            min(26.0, math.degrees(math.atan2(pet.vy, max(0.8, abs(pet.vx)))) * 0.55 * pet.direction),
        )

    if gaze_active:
        if gaze_dx > FLIP_HYSTERESIS_PX:
            pet._set_direction(1)
        elif gaze_dx < -FLIP_HYSTERESIS_PX:
            pet._set_direction(-1)
        raw_angle_deg = math.degrees(math.atan2(gaze_dy, max(1.0, abs(gaze_dx))))
        if abs(raw_angle_deg) > BODY_TILT_THRESHOLD_DEG:
            blend = min(1.0, (abs(raw_angle_deg) - BODY_TILT_THRESHOLD_DEG) / 8.0)
            clamped_deg = max(-BODY_TILT_MAX_DEG, min(BODY_TILT_MAX_DEG, raw_angle_deg))
            target_pitch = swim_pitch * (1.0 - blend) + (clamped_deg * pet.direction) * blend
        else:
            target_pitch = swim_pitch
        pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, target_pitch, BODY_TILT_DAMPING)
    else:
        if abs(pet.vx) > 0.32:
            pet._set_direction(1 if pet.vx > 0 else -1)
        pet.pitch_deg = lerp_angle_deg(pet.pitch_deg, swim_pitch, 0.12)


STATE_HANDLERS: dict[str, StateHandler] = {
    "caged": step_caged,
    "breaking_out": step_breaking_out,
    "dive_hide": step_dive_hide,
    "surface_show": step_surface_show,
    "drag": step_drag,
    "swallow_ready": step_swallow_ready,
    "starved_dead": step_starved_dead,
    "revive": step_revive,
    "shake_head_full": step_shake_head_full,
    "point_to_mouth": step_point_to_mouth,
    "swallow_gulp": step_swallow_gulp,
    "eat_file": step_eat_file,
    "nauseous_vomit": step_nauseous_vomit,
    "belly_up": step_belly_up,
    "sneeze_windup": step_sneeze_windup,
    "sneeze_burst": step_sneeze_burst,
    "celebrate_fig8": step_celebrate_fig8,
    "window_drop": step_window_drop,
    "window_surf": step_window_perch,
    "window_peek": step_window_perch,
    "puffed": step_puffed,
    "deflate_zoom": step_deflate_zoom,
    "play_dead": step_play_dead,
    "eat": step_eat,
    "swim": step_swim,
}


def dispatch_movement(pet: GoldenFishPet, bounds: QRectF, cur: QPoint) -> None:
    min_y = bounds.top() + 8.0
    if pet.water_overlay.active and pet.water_overlay.phase == "focus":
        min_y = max(min_y, pet.water_overlay.surface_global_y() - 18.0)
    ctx = StepContext(
        bounds=bounds,
        cur=cur,
        min_x=bounds.left() + 6.0,
        max_x=bounds.right() - SIZE - 6.0,
        min_y=min_y,
        max_y=bounds.bottom() - SIZE - 4.0,
    )
    handler = STATE_HANDLERS.get(pet.state, step_swim)
    handler(pet, ctx)
