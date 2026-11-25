"""Kiểm thử kiến trúc module, toán học lướt cửa sổ và bảng trạng thái hành vi + render."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from pet.config import PetStateStore
from pet.core.behaviors import STATE_HANDLERS
from pet.core.math_utils import check_window_surface_snap, window_safe_zone
from pet.core.pet import GoldenFishPet
from pet.models import TrackedWindow


class TestArchitectureAndBehaviors(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self) -> None:
        tmp = tempfile.mkdtemp(prefix="pet_test_arch_")
        self.pet = GoldenFishPet(state_store=PetStateStore(os.path.join(tmp, "pet_state.json")))

    def tearDown(self) -> None:
        self.pet.close()

    def test_window_safe_zone_and_snap(self) -> None:
        narrow = QRect(100, 200, 300, 400)
        self.assertIsNone(window_safe_zone(narrow))

        wide = QRect(100, 200, 900, 600)
        zone = window_safe_zone(wide)
        self.assertIsNotNone(zone)
        smin, smax = zone
        self.assertGreaterEqual(smax - smin, 310.0)

        tw = TrackedWindow(wid=1, rect=wide)
        snapped, found, _, _ = check_window_surface_snap(
            fish_x=smin + 100.0 - 94.0,
            fish_y=200.0 - 188.0 * 0.72,
            fish_w=188.0,
            fish_h=188.0,
            tracked_windows=[tw],
        )
        self.assertTrue(snapped)
        self.assertEqual(found, tw)

    def test_state_handlers_registry_and_smoke_render(self) -> None:
        expected_states = {
            "swim", "caged", "breaking_out", "dive_hide", "surface_show",
            "drag", "swallow_ready", "starved_dead", "revive",
            "shake_head_full", "point_to_mouth", "swallow_gulp", "eat_file",
            "nauseous_vomit", "belly_up", "sneeze_windup", "sneeze_burst",
            "celebrate_fig8", "window_drop", "window_surf", "window_peek",
            "puffed", "deflate_zoom", "play_dead", "eat",
        }
        self.assertTrue(expected_states.issubset(set(STATE_HANDLERS.keys())))

        # Kiểm thử chạy tick + grab() qua các trạng thái chính không crash
        scenarios = [
            lambda: self.pet.set_hunger_preset(80.0),
            lambda: self.pet.set_hunger_preset(25.0),
            lambda: self.pet.set_hunger_preset(100.0),
            lambda: self.pet.set_hunger_preset(0.0),
            lambda: self.pet.emergency_feed(),
            lambda: self.pet.trigger_pufferfish(),
            lambda: self.pet.trigger_nauseous_rainbow(),
            lambda: self.pet.trigger_sneeze(),
            lambda: self.pet.enter_cage_mode(),
            lambda: self.pet.start_cage_breakout(),
        ]
        for action in scenarios:
            action()
            for _ in range(3):
                self.pet.tick()
            pm = self.pet.grab()
            self.assertEqual(pm.width(), 188)
            self.assertEqual(pm.height(), 188)


if __name__ == "__main__":
    unittest.main()
