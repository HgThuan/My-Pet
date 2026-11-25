"""Lõi điều khiển hành vi, độ đói, lướt cửa sổ và hệ thống hạt của Golden Fish Pet."""
from pet.core.behaviors import STATE_HANDLERS, StepContext, dispatch_movement
from pet.core.hunger import HungerController
from pet.core.math_utils import (
    angle_diff,
    check_window_surface_snap,
    lerp_angle_deg,
    window_safe_zone,
)
from pet.core.particles import ParticleSystem
from pet.core.pet import GoldenFishPet
from pet.core.surfing import WindowSurfController

__all__ = [
    "GoldenFishPet",
    "HungerController",
    "ParticleSystem",
    "STATE_HANDLERS",
    "StepContext",
    "WindowSurfController",
    "angle_diff",
    "check_window_surface_snap",
    "dispatch_movement",
    "lerp_angle_deg",
    "window_safe_zone",
]
