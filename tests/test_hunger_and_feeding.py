"""Kiểm thử đầu-cuối cho Hệ thống Độ Đói, 3 File = No Căng, Chặn xóa file & Hồi sinh."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from pet.config import HungerState, PetStateStore
from pet.core.pet import GoldenFishPet


class TestHungerAndFeeding(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="pet_test_hunger_")
        self.state_file = os.path.join(self.tmp_dir, "pet_state.json")
        self.pet = GoldenFishPet(state_store=PetStateStore(self.state_file))
        self.pet._move_to_trash = self._fake_trash

    def tearDown(self) -> None:
        self.pet.close()

    @staticmethod
    def _fake_trash(path: str) -> bool:
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def _make_file(self, name: str) -> str:
        path = os.path.join(self.tmp_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("junk")
        return path

    def _drop_file(self, path: str) -> QDropEvent:
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        ev = QDropEvent(
            QPointF(94, 94),
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.pet.dropEvent(ev)
        return ev

    def test_default_hunger_and_states(self) -> None:
        self.assertAlmostEqual(self.pet.hunger, 80.0, places=2)
        self.assertEqual(self.pet.hunger_state, HungerState.NORMAL)

        self.pet.set_hunger_preset(25.0)
        self.assertEqual(self.pet.hunger_state, HungerState.HUNGRY)
        self.assertEqual(self.pet.state, "point_to_mouth")

        self.pet.set_hunger_preset(8.0)
        self.assertEqual(self.pet.hunger_state, HungerState.STARVING)
        self.assertEqual(self.pet.state, "point_to_mouth")

        self.pet.set_hunger_preset(0.0)
        self.assertEqual(self.pet.hunger_state, HungerState.DEAD)
        self.assertEqual(self.pet.state, "starved_dead")

    def test_three_files_full_and_fourth_file_safely_refused(self) -> None:
        self.pet.set_hunger_preset(1.0)
        files = [self._make_file(f"f_{i}.txt") for i in range(4)]

        for i in range(3):
            self._drop_file(files[i])
            self.assertFalse(os.path.exists(files[i]))

        self.assertTrue(self.pet.is_full)
        self.assertGreaterEqual(self.pet.hunger, 95.0)

        # File thứ 4 phải bị từ chối ở cả dragEnter và dropEvent, file gốc giữ nguyên trên đĩa
        mime4 = QMimeData()
        mime4.setUrls([QUrl.fromLocalFile(files[3])])
        enter4 = QDragEnterEvent(
            QPointF(94, 94).toPoint(),
            Qt.DropAction.MoveAction,
            mime4,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.pet.dragEnterEvent(enter4)
        self.assertFalse(enter4.isAccepted())

        drop4 = self._drop_file(files[3])
        self.assertFalse(drop4.isAccepted())
        self.assertTrue(os.path.exists(files[3]))
        self.assertEqual(self.pet.state, "shake_head_full")

    def test_dead_disables_playful_actions_and_revives_on_file_drop(self) -> None:
        self.pet.set_hunger_preset(0.0)
        self.assertEqual(self.pet.state, "starved_dead")

        self.pet.trigger_pufferfish()
        self.assertEqual(self.pet.state, "starved_dead")
        self.pet.trigger_sneeze()
        self.assertEqual(self.pet.state, "starved_dead")
        self.pet.trigger_nauseous_rainbow()
        self.assertEqual(self.pet.state, "starved_dead")

        revive_file = self._make_file("revive.txt")
        self._drop_file(revive_file)
        self.assertFalse(os.path.exists(revive_file))
        self.assertEqual(self.pet.state, "revive")
        self.assertAlmostEqual(self.pet.hunger, 50.0, places=2)

        # Kiểm tra lưu trữ bền vững JSON
        self.assertTrue(os.path.exists(self.state_file))
        with open(self.state_file, encoding="utf-8") as f:
            data = json.load(f)
        self.assertAlmostEqual(data["hunger"], 50.0, places=2)

    def test_preset_switch_during_revive_resets_spin(self) -> None:
        self.pet.set_hunger_preset(0.0)
        self.pet.emergency_feed()
        self.assertEqual(self.pet.state, "revive")
        for _ in range(4):
            self.pet.tick()
        self.pet.set_hunger_preset(25.0)
        self.assertEqual(self.pet.state, "point_to_mouth")
        self.assertAlmostEqual(self.pet.spin_deg, 0.0, places=2)


if __name__ == "__main__":
    unittest.main()
