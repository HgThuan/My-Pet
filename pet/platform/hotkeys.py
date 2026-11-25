"""Lắng nghe phím tắt toàn cục Ctrl+Shift+H (Boss Key) & Ctrl+Esc (Lồng giam)."""
from __future__ import annotations

import ctypes
import ctypes.util
import select
import sys
import threading
import time

from PySide6.QtCore import QObject, Signal

from pet.platform.os_window import _SILENT_X_ERR_HANDLER, _XEvent, _load_x11


class GlobalHotkeyListener(QObject):
    """Lắng nghe phím tắt toàn cục Ctrl+Shift+H (Boss Key) và Ctrl+Esc (Lồng giam).

    Hỗ trợ Linux (X11 XGrabKey), macOS (Carbon RegisterEventHotKey) và Windows
    (RegisterHotKey + WH_KEYBOARD_LL dự phòng cho Ctrl+Esc) không cần cài thêm thư viện ngoài.
    """

    triggered = Signal()       # Ctrl + Shift + H (Boss Key)
    cage_triggered = Signal()  # Ctrl + Esc (Chế độ Lồng giam)

    def __init__(self):
        super().__init__()
        self._x11 = _load_x11()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._win_thread_id: int | None = None

        # Tài nguyên Carbon trên macOS (giữ tham chiếu tránh GC)
        self._carbon = None
        self._mac_handler_cb = None
        self._mac_handler_ref = None
        self._mac_hotkey_refs: list[ctypes.c_void_p] = []
        self._last_fire_boss = 0.0
        self._last_fire_cage = 0.0
        self.is_active = False

        if self._x11 is not None:
            self.is_active = True
            self._thread = threading.Thread(target=self._run_x11_loop, daemon=True)
            self._thread.start()
        elif sys.platform == "darwin":
            self._setup_macos_hotkeys()
            self.is_active = bool(self._mac_hotkey_refs)
        elif sys.platform == "win32":
            self.is_active = True
            self._thread = threading.Thread(target=self._run_windows_loop, daemon=True)
            self._thread.start()

    def _emit_boss(self):
        now = time.monotonic()
        if now - self._last_fire_boss > 0.35:
            self._last_fire_boss = now
            self.triggered.emit()

    def _emit_cage(self):
        now = time.monotonic()
        if now - self._last_fire_cage > 0.35:
            self._last_fire_cage = now
            self.cage_triggered.emit()

    def _run_x11_loop(self):
        dpy = None
        try:
            self._x11.XSetErrorHandler(_SILENT_X_ERR_HANDLER)
            dpy = self._x11.XOpenDisplay(None)
            if not dpy:
                return
            root = self._x11.XDefaultRootWindow(dpy)
            # Boss Key: 'h' (0x0068) + Ctrl|Shift (4|1)
            # Cage Key: Escape (0xFF1B) + Ctrl (4)
            kc_boss = self._x11.XKeysymToKeycode(dpy, 0x0068)
            kc_cage = self._x11.XKeysymToKeycode(dpy, 0xFF1B)
            if not kc_boss and not kc_cage:
                return

            boss_mod = 4 | 1  # ControlMask | ShiftMask
            cage_mod = 4      # ControlMask
            # Grab cả các biến thể CapsLock (2) và NumLock (16)
            for extra in (0, 2, 16, 18):
                if kc_boss:
                    self._x11.XGrabKey(dpy, int(kc_boss), boss_mod | extra, root, 0, 1, 1)
                if kc_cage:
                    self._x11.XGrabKey(dpy, int(kc_cage), cage_mod | extra, root, 0, 1, 1)
            self._x11.XSelectInput(dpy, root, 1)  # KeyPressMask = 1
            self._x11.XSync(dpy, 0)

            fd = self._x11.XConnectionNumber(dpy)
            ev = _XEvent()

            while not self._stop_event.is_set():
                rlist, _, _ = select.select([fd], [], [], 0.25)
                if not rlist:
                    continue
                while self._x11.XPending(dpy) > 0:
                    self._x11.XNextEvent(dpy, ctypes.byref(ev))
                    if ev.type == 2:  # KeyPress = 2
                        kc = ev.xkey.keycode
                        mods = ev.xkey.state & (4 | 1 | 8)  # Ctrl, Shift, Alt
                        if kc_boss and kc == kc_boss and (mods & 5) == 5:
                            self._emit_boss()
                        elif kc_cage and kc == kc_cage and mods == 4:
                            self._emit_cage()

            for extra in (0, 2, 16, 18):
                if kc_boss:
                    self._x11.XUngrabKey(dpy, int(kc_boss), boss_mod | extra, root)
                if kc_cage:
                    self._x11.XUngrabKey(dpy, int(kc_cage), cage_mod | extra, root)
        except Exception:
            pass
        finally:
            if dpy:
                try:
                    self._x11.XCloseDisplay(dpy)
                except Exception:
                    pass

    def _setup_macos_hotkeys(self):
        """Đăng ký global hotkey trên macOS bằng Carbon RegisterEventHotKey (không cần quyền Accessibility)."""
        try:
            lib_path = ctypes.util.find_library("Carbon")
            if not lib_path:
                return
            carbon = ctypes.CDLL(lib_path)

            class EventTypeSpec(ctypes.Structure):
                _fields_ = [
                    ("eventClass", ctypes.c_uint32),
                    ("eventKind", ctypes.c_uint32),
                ]

            class EventHotKeyID(ctypes.Structure):
                _fields_ = [
                    ("signature", ctypes.c_uint32),
                    ("id", ctypes.c_uint32),
                ]

            handler_cb_type = ctypes.CFUNCTYPE(
                ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            )

            carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
            carbon.InstallEventHandler.argtypes = [
                ctypes.c_void_p,
                handler_cb_type,
                ctypes.c_ulong,
                ctypes.POINTER(EventTypeSpec),
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            carbon.InstallEventHandler.restype = ctypes.c_int32
            carbon.RemoveEventHandler.argtypes = [ctypes.c_void_p]
            carbon.RemoveEventHandler.restype = ctypes.c_int32
            carbon.RegisterEventHotKey.argtypes = [
                ctypes.c_uint32,
                ctypes.c_uint32,
                EventHotKeyID,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            carbon.RegisterEventHotKey.restype = ctypes.c_int32
            carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
            carbon.UnregisterEventHotKey.restype = ctypes.c_int32
            carbon.GetEventParameter.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            carbon.GetEventParameter.restype = ctypes.c_int32

            k_event_class_keyboard = int.from_bytes(b"keyb", "big")
            k_event_hotkey_pressed = 5
            k_param_direct_object = int.from_bytes(b"----", "big")
            type_hotkey_id = int.from_bytes(b"hkid", "big")
            sig = int.from_bytes(b"GFSH", "big")

            def _on_carbon_event(_next_handler, event_ref, _user_data):
                hk_id = EventHotKeyID()
                err = carbon.GetEventParameter(
                    event_ref,
                    k_param_direct_object,
                    type_hotkey_id,
                    None,
                    ctypes.sizeof(hk_id),
                    None,
                    ctypes.byref(hk_id),
                )
                if err == 0 and hk_id.signature == sig:
                    if hk_id.id == 1:
                        self._emit_boss()
                    elif hk_id.id == 2:
                        self._emit_cage()
                return 0

            self._carbon = carbon
            self._mac_handler_cb = handler_cb_type(_on_carbon_event)
            target = carbon.GetApplicationEventTarget()
            spec = EventTypeSpec(k_event_class_keyboard, k_event_hotkey_pressed)
            handler_ref = ctypes.c_void_p()
            if carbon.InstallEventHandler(
                target, self._mac_handler_cb, 1, ctypes.byref(spec), None, ctypes.byref(handler_ref)
            ) == 0:
                self._mac_handler_ref = handler_ref
                # id=1: Ctrl + Shift + H (kVK_ANSI_H = 0x04, controlKey|shiftKey = 0x1200)
                # id=2: Ctrl + Esc (kVK_Escape = 0x35, controlKey = 0x1000)
                for hk_num, vk_code, mods in ((1, 0x04, 0x1200), (2, 0x35, 0x1000)):
                    ref = ctypes.c_void_p()
                    status = carbon.RegisterEventHotKey(
                        vk_code, mods, EventHotKeyID(sig, hk_num), target, 0, ctypes.byref(ref)
                    )
                    if status == 0 and ref.value:
                        self._mac_hotkey_refs.append(ref)
        except Exception:
            pass

    def _run_windows_loop(self):
        """Đăng ký global hotkey trên Windows (RegisterHotKey + hook dự phòng cho Ctrl+Esc)."""
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._win_thread_id = int(kernel32.GetCurrentThreadId())

            MOD_CONTROL = 0x0002
            MOD_SHIFT = 0x0004
            MOD_NOREPEAT = 0x4000
            VK_H = 0x48
            VK_ESCAPE = 0x1B
            VK_CONTROL = 0x11
            VK_SHIFT = 0x10
            VK_MENU = 0x12
            WM_HOTKEY = 0x0312
            WM_KEYDOWN = 0x0100
            WM_SYSKEYDOWN = 0x0104
            WH_KEYBOARD_LL = 13

            reg_boss = bool(user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_H))
            reg_cage = bool(user32.RegisterHotKey(None, 2, MOD_CONTROL | MOD_NOREPEAT, VK_ESCAPE))

            hook_handle = None
            hook_proc_ref = None
            if not reg_cage:
                # Windows thường giữ Ctrl+Esc cho Start Menu nên dùng hook mức thấp dự phòng
                class KBDLLHOOKSTRUCT(ctypes.Structure):
                    _fields_ = [
                        ("vkCode", ctypes.c_uint32),
                        ("scanCode", ctypes.c_uint32),
                        ("flags", ctypes.c_uint32),
                        ("time", ctypes.c_uint32),
                        ("dwExtraInfo", ctypes.c_void_p),
                    ]

                hook_type = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p)

                def _ll_cb(n_code, w_param, l_param):
                    if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                        if kb.vkCode == VK_ESCAPE:
                            ctrl_down = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                            shift_down = bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
                            alt_down = bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)
                            if ctrl_down and not shift_down and not alt_down:
                                self._emit_cage()
                    return user32.CallNextHookEx(hook_handle, n_code, w_param, l_param)

                hook_proc_ref = hook_type(_ll_cb)
                hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_proc_ref, None, 0)

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", ctypes.c_void_p),
                    ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_ulong),
                    ("lParam", ctypes.c_long),
                    ("time", ctypes.c_uint),
                    ("pt", POINT),
                ]

            msg = MSG()
            while not self._stop_event.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                if msg.message == WM_HOTKEY:
                    if msg.wParam == 1:
                        self._emit_boss()
                    elif msg.wParam == 2:
                        self._emit_cage()

            if hook_handle:
                user32.UnhookWindowsHookEx(hook_handle)
            if reg_boss:
                user32.UnregisterHotKey(None, 1)
            if reg_cage:
                user32.UnregisterHotKey(None, 2)
            _ = hook_proc_ref
        except Exception:
            pass

    def stop(self):
        self._stop_event.set()
        if self._carbon is not None:
            try:
                for ref in self._mac_hotkey_refs:
                    self._carbon.UnregisterEventHotKey(ref)
                self._mac_hotkey_refs.clear()
                if self._mac_handler_ref is not None:
                    self._carbon.RemoveEventHandler(self._mac_handler_ref)
                    self._mac_handler_ref = None
            except Exception:
                pass
        if sys.platform == "win32" and self._win_thread_id is not None:
            try:
                ctypes.windll.user32.PostThreadMessageW(self._win_thread_id, 0x0012, 0, 0)  # WM_QUIT
            except Exception:
                pass


