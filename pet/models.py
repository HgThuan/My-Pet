"""Các mô hình dữ liệu dùng chung giữa các tầng của Golden Fish Pet."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor


@dataclass
class TrackedWindow:
    wid: int
    rect: QRect


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
    direction: int           # -1 = quay trái (mặc định), 1 = quay phải
    pitch_deg: float         # góc chúi lên/xuống khi bơi
    spin_deg: float          # góc xoay khi bị xoáy nước hoặc backflip
    depth: float             # 0.0 (lặn sâu 0.85x) .. 1.0 (sát mặt kính 1.10x)
    squash_x: float
    squash_y: float
    puff_factor: float       # 0.0 (bình thường) .. 1.0 (cá nóc phồng to)
    expression: str
    facing_front: bool
    blink: bool
    look_dx: float
    look_dy: float
    swim_speed: float
    water_helmet: bool
    seaweed_blanket: bool
    boiling: bool
    vortex_alpha: float
    suction_alpha: float
    audio_bands: list[float]
    audio_level: float
    particles: list[Particle]
    mouth_locked: bool = False
    eating_file_progress: float = -1.0
    eating_file_start: tuple[float, float] = (0.0, 0.0)
    eating_file_is_dir: bool = False
    tail_phase: float = 0.0
    bank_deg: float = 0.0
    chubby_factor: float = 0.0
    belly_up: bool = False
    peeking_window: bool = False
    dive_scale: float = 1.0
    cage_mode: str = "none"                  # "none" | "caged" | "breaking_out"
    cage_drop_progress: float = 1.0
    cage_swing_deg: float = 0.0
    cage_pleading: bool = False
    cage_bend_amount: float = 0.0
    cage_opacity: float = 1.0
    muscular_level: float = 0.0
    pupil_x: float = 0.0
    pupil_y: float = 0.0
    turn_progress: float = -1.0
    turn_from_dir: int = -1
    contact_shadow: float = 0.0
    contact_shadow_y: float = 0.0
    play_dead_peek: bool = False
    surfing_waterline: bool = False
    surf_waterline_y: float = 0.0
    surf_speed: float = 0.0
    full_shake_t: float = -1.0
    point_to_mouth: float = 0.0
    starved_dead: bool = False
