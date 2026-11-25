"""Bộ điều khiển Hệ thống Độ Đói & Sinh Tồn (Hunger & Starvation System)."""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint

from pet.config import (
    FPS,
    FULL_REFUSE_LINES,
    HUNGER_DECAY_PER_MIN,
    HUNGER_FILE_GAIN,
    HUNGER_FULL_THRESHOLD,
    HUNGER_REVIVE_LEVEL,
    HUNGRY_BEG_LINES,
    IDLE_SLEEP_SECS,
    HungerState,
    PetStateStore,
)

if TYPE_CHECKING:
    from pet.core.pet import GoldenFishPet


class HungerController:
    """Quản lý độ no (0–100%), lưu trữ JSON, tiêu hao, từ chối ăn khi no, đòi ăn & hồi sinh."""

    def __init__(self, pet: GoldenFishPet, store: PetStateStore | None = None):
        self.pet = pet
        self.store = store if store is not None else PetStateStore()
        self.value: float = self.store.load_hunger()
        self._save_ticks: int = 0

    @property
    def state(self) -> HungerState:
        if self.value <= 0.0:
            return HungerState.DEAD
        if self.value < 15.0:
            return HungerState.STARVING
        if self.value < 40.0:
            return HungerState.HUNGRY
        return HungerState.NORMAL

    @property
    def is_full(self) -> bool:
        return self.value >= HUNGER_FULL_THRESHOLD

    def save(self) -> None:
        self.store.save_hunger(self.value)

    def apply_delta(self, delta: float, save_now: bool = True) -> None:
        prev_state = self.state
        self.value = max(0.0, min(100.0, self.value + delta))
        if save_now:
            self.save()
        if self.value <= 0.0 and prev_state != HungerState.DEAD:
            self.enter_starved_dead()

    def tick(self, now: float, cur: QPoint, cursor_speed: float) -> None:
        pet = self.pet
        # Tiêu hao độ đói (-0.04%/phút) chỉ khi người dùng hoạt động và cá đang tỉnh táo
        user_active = (now - pet._last_user_activity) < IDLE_SLEEP_SECS
        if user_active and pet.state not in ("play_dead", "starved_dead", "dive_hide", "hidden", "revive"):
            self.apply_delta(-(HUNGER_DECAY_PER_MIN / (60.0 * FPS)), save_now=False)
            self._save_ticks += 1
            if self._save_ticks >= 30 * FPS:
                self._save_ticks = 0
                self.save()

        # Cử chỉ "Chỉ vây vào miệng đòi ăn" định kỳ 6–10s hoặc khi di chuột lại gần lúc Đói/Sắp chết đói
        if pet._hover_beg_cd > 0:
            pet._hover_beg_cd -= 1
        if (
            pet.state == "swim"
            and self.state in (HungerState.HUNGRY, HungerState.STARVING)
            and not pet.is_overloaded
            and not pet.foods
        ):
            pet._point_mouth_cd -= 1
            fcx, fcy = pet.center_global()
            near_mouse = cursor_speed > 2.0 and math.hypot(cur.x() - fcx, cur.y() - fcy) < 165.0
            if pet._point_mouth_cd <= 0:
                self.trigger_point_to_mouth()
            elif near_mouse and pet._hover_beg_cd == 0:
                pet._hover_beg_cd = 6 * FPS
                self.trigger_point_to_mouth()

    def _reset_pose_rotations(self) -> None:
        pet = self.pet
        pet.spin_deg = 0.0
        pet.spin_vel = 0.0
        pet.backflip_remaining = 0.0
        pet.bank_deg = 0.0
        pet.pitch_deg = 0.0

    def set_preset(self, value: float) -> None:
        """Đặt nhanh mức độ no (No / Bình thường / Đói / Rất đói / Chết đói)."""
        pet = self.pet
        val = max(0.0, min(100.0, float(value)))
        was_dead = pet.state == "starved_dead"
        self.value = val
        self.save()
        if val <= 0.0:
            self.enter_starved_dead()
        elif was_dead:
            self.revive(target_hunger=val)
        elif val >= HUNGER_FULL_THRESHOLD:
            pet.revive_ticks = 0
            pet.chubby_factor = max(pet.chubby_factor, 0.55)
            pet._chubby_ticks = max(pet._chubby_ticks, 60 * FPS)
            self.trigger_shake_head_full()
        elif val < 40.0:
            pet.revive_ticks = 0
            pet.state = "swim"
            self.trigger_point_to_mouth()
        else:
            pet.revive_ticks = 0
            self._reset_pose_rotations()
            pet.thought_bubble.dismiss()
            if pet.state in ("point_to_mouth", "shake_head_full", "starved_dead", "revive"):
                pet.state = "swim"
            pet.set_expression("happy", 70)

    def enter_starved_dead(self) -> None:
        """Chết đói (0%): lật ngửa bụng, mắt X_X, trôi nổi từ từ lên sát mép trên màn hình."""
        pet = self.pet
        if pet.state in ("dive_hide", "hidden"):
            return
        pet.surfing.clear_click_through()
        pet.thought_bubble.dismiss()
        pet.falling_cage_overlay.stop()
        pet.state = "starved_dead"
        pet.revive_ticks = 0
        pet.facing_front = False
        pet.puff_factor = 0.0
        self._reset_pose_rotations()
        pet.vx = random.uniform(-0.35, 0.35)
        pet.vy = -0.75
        pet.depth_target = 0.72
        pet._perch_rect = None
        pet._perch_wid = 0

    def revive(self, target_hunger: float = HUNGER_REVIVE_LEVEL) -> None:
        """Hồi sinh cá từ trạng thái DEAD: lật người 180°, tim/sao vui vẻ & đặt hunger = 50%."""
        pet = self.pet
        self.value = max(1.0, min(100.0, float(target_hunger)))
        self.save()
        pet.thought_bubble.dismiss()
        pet.state = "revive"
        pet.revive_ticks = pet.revive_total
        pet.facing_front = False
        self._reset_pose_rotations()
        pet.spin_deg = 180.0
        pet.vx = 0.0
        pet.vy = 1.6
        pet.impulse_squash(1.24, 0.80)
        pet.sound.play_pop()
        for _ in range(6):
            pet.spawn_particle("heart")
            pet.spawn_particle("star")

    def trigger_shake_head_full(self) -> None:
        """Biểu cảm No căng lắc đầu từ chối (SHAKE_HEAD_FULL ~1.5s) khi hunger >= 95%."""
        pet = self.pet
        if pet.state in ("caged", "breaking_out", "dive_hide", "hidden", "starved_dead"):
            return
        if pet.state == "play_dead":
            pet._wake_from_play_dead()
        pet.surfing.clear_click_through()
        pet.state = "shake_head_full"
        pet.full_shake_ticks = pet.full_shake_total
        pet.facing_front = True
        pet.suction_alpha = 0.0
        pet.mouth_locked = False
        pet.vx *= 0.25
        pet.vy *= 0.25
        self._reset_pose_rotations()
        pet.impulse_squash(1.12, 0.92)
        pet.sound.play_pop()
        pet.spawn_particle("sweat")
        for _ in range(3):
            pet.spawn_particle("bubble")
        pet.thought_bubble.show_text(random.choice(FULL_REFUSE_LINES), pet.full_shake_total + 15)

    def trigger_point_to_mouth(self) -> None:
        """Biểu cảm chỉ vây vào miệng đòi ăn (POINT_TO_MOUTH) khi Đói / Sắp chết đói."""
        pet = self.pet
        if pet.state not in ("swim", "point_to_mouth"):
            return
        if self.state not in (HungerState.HUNGRY, HungerState.STARVING):
            return
        pet.state = "point_to_mouth"
        pet.point_mouth_ticks = pet.point_mouth_total
        pet._point_mouth_cd = random.randint(6 * FPS, 10 * FPS)
        pet.facing_front = random.random() < 0.45
        pet.vx *= 0.25
        pet.vy *= 0.25
        self._reset_pose_rotations()
        if self.state == HungerState.STARVING:
            if random.random() < 0.60:
                pet.thought_bubble.show_trash_icon(pet.point_mouth_total)
            else:
                pet.thought_bubble.show_text("Đói quá... cho xin 1 file rác đi!", pet.point_mouth_total)
        else:
            if random.random() < 0.34:
                pet.thought_bubble.show_trash_icon(pet.point_mouth_total)
            else:
                pet.thought_bubble.show_text(random.choice(HUNGRY_BEG_LINES), pet.point_mouth_total)

    def emergency_feed(self) -> None:
        """Cho ăn khẩn cấp từ menu chuột phải (hồi sinh nếu DEAD, từ chối nếu No căng)."""
        pet = self.pet
        if pet.boss_hidden:
            pet.toggle_boss_hide()
        if pet.state == "starved_dead" or self.state == HungerState.DEAD:
            self.revive(HUNGER_REVIVE_LEVEL)
            return
        if self.is_full:
            self.trigger_shake_head_full()
            return
        if pet.state == "play_dead":
            pet._wake_from_play_dead()
        pet.thought_bubble.dismiss()
        self.apply_delta(HUNGER_FILE_GAIN, save_now=True)
        if self.is_full:
            pet.chubby_factor = max(pet.chubby_factor, 0.55)
            pet._chubby_ticks = max(pet._chubby_ticks, 90 * FPS)
        pet.impulse_squash(1.22, 0.84)
        pet.sound.play_pop()
        for _ in range(5):
            pet.spawn_particle("heart")
            pet.spawn_particle("bubble")
        pet.set_expression("love", 100)
        if pet.state == "point_to_mouth":
            pet.state = "swim"
