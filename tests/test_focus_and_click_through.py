"""Kiểm thử Lớp 1 (Non-Activating không cướp focus) & Lớp 2 (Xuyên chuột thông minh 24/7) cho macOS/Windows/Linux."""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication

from pet.config import SIZE, PetStateStore
from pet.core.pet import GoldenFishPet
from pet.platform import os_window
from pet.widgets import (
    ClipboardBubble,
    FallingCageOverlay,
    FishFood,
    ParticleFieldOverlay,
    SplashRippleOverlay,
    ThoughtBubbleOverlay,
    WaterOverlay,
)


class TestFocusAndClickThrough(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self) -> None:
        tmp = tempfile.mkdtemp(prefix="pet_test_focus_")
        self.pet = GoldenFishPet(state_store=PetStateStore(os.path.join(tmp, "pet_state.json")))
        self.pet.px = 500.0
        self.pet.py = 300.0

    def tearDown(self) -> None:
        self.pet.close()

    def test_layer1_non_activating_flags_on_pet_and_overlays(self) -> None:
        # Cửa sổ chính không được nhận focus bàn phím và không tự kích hoạt app khi hiện
        self.assertTrue(bool(self.pet.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus))
        self.assertTrue(self.pet.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.assertEqual(self.pet.focusPolicy(), Qt.FocusPolicy.NoFocus)

        passive_overlays = [
            self.pet.water_overlay,
            self.pet.splash_overlay,
            self.pet.falling_cage_overlay,
            self.pet.particle_overlay,
            self.pet.thought_bubble,
            FishFood(100, 100, 800, word="OK"),
        ]
        try:
            for ov in passive_overlays:
                self.assertTrue(ov._PASSIVE_CLICK_THROUGH, f"{type(ov).__name__} must be passive click-through")
                self.assertTrue(bool(ov.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus))
                self.assertTrue(bool(ov.windowFlags() & Qt.WindowType.WindowTransparentForInput))
                self.assertTrue(ov.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
                self.assertTrue(ov.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
                self.assertEqual(ov.focusPolicy(), Qt.FocusPolicy.NoFocus)
        finally:
            passive_overlays[-1].close()

        # ClipboardBubble có thể click nhưng cũng không được cướp focus bàn phím
        cb = ClipboardBubble("text", "hello", 120, 120, lambda _: None, lambda _: None)
        try:
            self.assertFalse(cb._PASSIVE_CLICK_THROUGH)
            self.assertTrue(bool(cb.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus))
            self.assertTrue(cb.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
            self.assertEqual(cb.focusPolicy(), Qt.FocusPolicy.NoFocus)
        finally:
            cb.close()

    def test_layer2_smart_click_through_swim_and_hysteresis(self) -> None:
        cx = int(self.pet.px + SIZE / 2.0)
        cy = int(self.pet.py + SIZE / 2.0)

        self.pet.state = "swim"
        self.pet.puff_factor = 0.0
        self.pet._click_through_active = True

        # Góc trong suốt trong khung 188x188 (cách tâm ~85px) -> PHẢI xuyên chuột
        self.assertTrue(self.pet.compute_want_click_through(QPoint(int(self.pet.px + 8), int(self.pet.py + 8))))
        # Ngoài bán kính thân 58px -> xuyên chuột
        self.assertTrue(self.pet.compute_want_click_through(QPoint(cx + 62, cy)))
        # Đi vào trong thân cá (50px <= 58px) -> mở nhận chuột
        self.assertFalse(self.pet.compute_want_click_through(QPoint(cx + 50, cy)))

        # Đang ở trạng thái nhận chuột (_click_through_active=False): có vùng đệm hysteresis +6px (<= 64px)
        self.pet._click_through_active = False
        self.assertFalse(self.pet.compute_want_click_through(QPoint(cx + 61, cy)))
        # Ra xa hẳn khỏi vùng đệm (> 64px) -> bật lại xuyên chuột
        self.assertTrue(self.pet.compute_want_click_through(QPoint(cx + 68, cy)))

    def test_layer2_smart_click_through_special_states(self) -> None:
        cx = int(self.pet.px + SIZE / 2.0)
        cy = int(self.pet.py + SIZE / 2.0)
        far_pt = QPoint(cx + 400, cy + 400)

        # Đang kéo cá / đang nhận file kéo thả -> tuyệt đối KHÔNG xuyên chuột
        for active_state in ("drag", "swallow_ready", "swallow_gulp"):
            self.pet.state = active_state
            self.assertFalse(self.pet.compute_want_click_through(far_pt))

        # Các pha chuyển cảnh không tương tác -> luôn xuyên chuột kể cả ở tâm cá
        for passive_state in ("dive_hide", "hidden", "surface_show", "breaking_out"):
            self.pet.state = passive_state
            self.assertTrue(self.pet.compute_want_click_through(QPoint(cx, cy)))

        # Trong lồng giam: chỉ nhận chuột bên trong khung lồng
        self.pet.state = "caged"
        self.pet.cage_dragging = False
        self.pet._click_through_active = True
        self.assertFalse(self.pet.compute_want_click_through(QPoint(cx, cy)))
        self.assertTrue(self.pet.compute_want_click_through(QPoint(cx + 80, cy)))
        self.pet.cage_dragging = True
        self.assertFalse(self.pet.compute_want_click_through(far_pt))
        self.pet.cage_dragging = False

        # Đang nhảy sóng trên thanh tiêu đề cửa sổ: vùng dưới mép cửa sổ luôn xuyên chuột để bấm tab!
        self.pet.state = "window_surf"
        self.pet._surf_phase = "arc"
        self.pet._perch_rect = QRect(300, cy + 10, 900, 600)
        self.pet._click_through_active = True
        self.assertFalse(self.pet.compute_want_click_through(QPoint(cx, cy)))
        self.assertTrue(self.pet.compute_want_click_through(QPoint(cx, cy + 24)))
        self.assertTrue(self.pet.compute_want_click_through(QPoint(cx + 60, cy)))

    def test_macos_native_non_activating_and_order_front_mocked(self) -> None:
        calls: list[tuple] = []
        fake_rt = {
            "cls_ns_panel": 0x999,
            "sel_is_kind_of": "isKindOfClass:",
            "sel_get_style": "styleMask",
            "sel_set_style": "setStyleMask:",
            "sel_responds": "respondsToSelector:",
            "sel_set_becomes_key": "setBecomesKeyOnlyIfNeeded:",
            "sel_set_floating": "setFloatingPanel:",
            "sel_set_hide_deact": "setHidesOnDeactivate:",
            "sel_set_can_hide": "setCanHide:",
            "sel_order_front": "orderFrontRegardless",
            "sel_set_ign_mouse": "setIgnoresMouseEvents:",
            "msg_bool_ptr": lambda win, sel, cls: True,
            "msg_ulong": lambda win, sel: 0x01,
            "msg_bool_sel": lambda win, sel, target: True,
            "msg_void_ulong": lambda win, sel, val: calls.append((sel, val)),
            "msg_void_bool": lambda win, sel, val: calls.append((sel, val)),
            "msg_void": lambda win, sel: calls.append((sel,)),
        }

        with (
            patch.object(os_window.sys, "platform", "darwin"),
            patch.object(os_window, "_get_macos_nswindow", return_value=(fake_rt, 0x1234)),
        ):
            self.assertTrue(os_window.configure_non_activating_window(self.pet))
            self.assertTrue(os_window.bring_window_to_front_no_activate(self.pet))
            self.assertTrue(os_window.set_window_click_through(self.pet, True))

        self.assertIn(("setStyleMask:", 0x01 | os_window._NS_STYLE_MASK_NONACTIVATING_PANEL), calls)
        self.assertIn(("setBecomesKeyOnlyIfNeeded:", True), calls)
        self.assertIn(("setFloatingPanel:", True), calls)
        self.assertIn(("setHidesOnDeactivate:", False), calls)
        self.assertIn(("setCanHide:", False), calls)
        self.assertIn(("orderFrontRegardless",), calls)
        self.assertIn(("setIgnoresMouseEvents:", True), calls)

    def test_windows_native_noactivate_and_click_through_mocked(self) -> None:
        state = {"ex": 0}

        class FakeUser32:
            def GetWindowLongPtrW(self, hwnd, idx):
                return state["ex"]

            def SetWindowLongPtrW(self, hwnd, idx, val):
                state["ex"] = val
                return val

            def SetWindowPos(self, hwnd, after, x, y, cx, cy, flags):
                state["swp_flags"] = flags
                return 1

        fake_windll = types.SimpleNamespace(user32=FakeUser32())
        with (
            patch.object(os_window.sys, "platform", "win32"),
            patch.object(os_window.ctypes, "windll", fake_windll, create=True),
        ):
            self.assertTrue(os_window.configure_non_activating_window(self.pet))
            self.assertTrue(bool(state["ex"] & os_window._WS_EX_NOACTIVATE))
            self.assertTrue(bool(state["ex"] & os_window._WS_EX_TOOLWINDOW))

            self.assertTrue(os_window.set_window_click_through(self.pet, True))
            self.assertTrue(bool(state["ex"] & os_window._WS_EX_TRANSPARENT))
            self.assertTrue(bool(state["ex"] & os_window._WS_EX_NOACTIVATE))

            self.assertTrue(os_window.set_window_click_through(self.pet, False))
            self.assertFalse(bool(state["ex"] & os_window._WS_EX_TRANSPARENT))
            self.assertTrue(bool(state["ex"] & os_window._WS_EX_NOACTIVATE))

            self.assertTrue(os_window.bring_window_to_front_no_activate(self.pet))
            self.assertTrue(bool(state["swp_flags"] & os_window._SWP_NOACTIVATE))


if __name__ == "__main__":
    unittest.main()
