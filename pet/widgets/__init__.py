"""Các overlay QWidget vệ tinh cho Golden Fish Pet."""
from pet.widgets.base import _AllSpacesWidget, set_widgets_all_spaces
from pet.widgets.clipboard_bubble import ClipboardBubble, paste_or_open_clipboard_payload
from pet.widgets.effects import (
    ParticleFieldOverlay,
    SplashRippleOverlay,
    ThoughtBubbleOverlay,
)
from pet.widgets.gameplay import FallingCageOverlay, FishFood, WaterOverlay

__all__ = [
    "_AllSpacesWidget",
    "ClipboardBubble",
    "FallingCageOverlay",
    "FishFood",
    "ParticleFieldOverlay",
    "SplashRippleOverlay",
    "ThoughtBubbleOverlay",
    "WaterOverlay",
    "paste_or_open_clipboard_payload",
    "set_widgets_all_spaces",
]
