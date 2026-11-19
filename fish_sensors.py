"""Các cảm biến hệ thống, X11 Window Tracker & Global Hotkey cho Desktop Pet Cá Vàng.

Bao gồm:
- SystemPressureMonitor: đo CPU% và RAM%.
- WallpaperColorAnalyzer: quét lưới màu màn hình (ưa xanh dương/lạnh, dè chừng đỏ/cam).
- AudioSpectrumMonitor: bắt biên độ & bass drop từ âm thanh hệ thống + chế độ Demo.
- WindowTracker: lấy tọa độ các cửa sổ ứng dụng đang mở (X11 libX11.so.6 / Windows)
  để cá lướt hoặc đậu ngó lên thanh tiêu đề cửa sổ (Window Perching / Surfing).
- GlobalHotkeyListener: bắt phím tắt toàn cục Ctrl+Shift+H (Boss Key) và Ctrl+Esc (Lồng giam)
  trên Linux X11, macOS (Carbon) và Windows mà không cần cài thêm thư viện ngoài.
- SoundPlayer: tổng hợp âm thanh "bụp" (pop), "tõm" (splash), khóa lồng "cạch" (cage_lock)
  và kim loại uốn cong (metal_bend) bằng code.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import math
import os
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, QPoint, QRect, QUrl, Signal
from PySide6.QtGui import QColor, QGuiApplication

try:
    from PySide6.QtMultimedia import QSoundEffect
except Exception:
    QSoundEffect = None

# Callback tĩnh cho XSetErrorHandler để giữ tham chiếu không bị GC
_X_ERR_HANDLER_TYPE = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
_SILENT_X_ERR_HANDLER = _X_ERR_HANDLER_TYPE(lambda dpy, ev: 0)


class _XWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("border_width", ctypes.c_int),
        ("depth", ctypes.c_int),
        ("visual", ctypes.c_void_p),
        ("root", ctypes.c_ulong),
        ("c_class", ctypes.c_int),
        ("bit_gravity", ctypes.c_int),
        ("win_gravity", ctypes.c_int),
        ("backing_store", ctypes.c_int),
        ("backing_planes", ctypes.c_ulong),
        ("backing_pixel", ctypes.c_ulong),
        ("save_under", ctypes.c_int),
        ("colormap", ctypes.c_ulong),
        ("map_installed", ctypes.c_int),
        ("map_state", ctypes.c_int),
        ("all_event_masks", ctypes.c_long),
        ("your_event_mask", ctypes.c_long),
        ("do_not_propagate_mask", ctypes.c_long),
        ("override_redirect", ctypes.c_int),
        ("screen", ctypes.c_void_p),
    ]


class _XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class _XEvent(ctypes.Union):
    _fields_ = [
        ("type", ctypes.c_int),
        ("xkey", _XKeyEvent),
        ("pad", ctypes.c_long * 24),
    ]


def _load_x11():
    if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
        return None
    try:
        lib = ctypes.CDLL("libX11.so.6")
        lib.XOpenDisplay.restype = ctypes.c_void_p
        lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        lib.XDefaultRootWindow.restype = ctypes.c_ulong
        lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        lib.XInternAtom.restype = ctypes.c_ulong
        lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        lib.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.c_long, ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.XGetWindowAttributes.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_XWindowAttributes),
        ]
        lib.XTranslateCoordinates.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong),
        ]
        lib.XFree.argtypes = [ctypes.c_void_p]
        lib.XSetErrorHandler.argtypes = [_X_ERR_HANDLER_TYPE]
        lib.XSetErrorHandler.restype = ctypes.c_void_p
        lib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        lib.XKeysymToKeycode.restype = ctypes.c_uint
        lib.XGrabKey.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_uint,
            ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ]
        lib.XUngrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong]
        lib.XSelectInput.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]
        lib.XConnectionNumber.argtypes = [ctypes.c_void_p]
        lib.XConnectionNumber.restype = ctypes.c_int
        lib.XPending.argtypes = [ctypes.c_void_p]
        lib.XPending.restype = ctypes.c_int
        lib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.POINTER(_XEvent)]
        lib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        return lib
    except Exception:
        return None


@dataclass
class TrackedWindow:
    wid: int
    rect: QRect


class WindowTracker:
    """Lấy danh sách cửa sổ ứng dụng đang mở kèm ID để theo dõi di chuyển / đóng / thu nhỏ trực tiếp."""

    def __init__(self):
        self._x11 = _load_x11()
        self._mac_cg = self._load_macos_cg() if sys.platform == "darwin" else None
        self._my_pid = os.getpid()
        self.tracked_windows: list[TrackedWindow] = []
        self.windows: list[QRect] = []

    def sample_tracked(self) -> list[TrackedWindow]:
        if self._x11 is not None:
            self.tracked_windows = self._sample_x11()
        elif self._mac_cg is not None:
            self.tracked_windows = self._sample_macos()
        elif sys.platform == "win32":
            self.tracked_windows = self._sample_windows()
        else:
            self.tracked_windows = []
        self.windows = [tw.rect for tw in self.tracked_windows]
        return self.tracked_windows

    def sample(self) -> list[QRect]:
        self.sample_tracked()
        return self.windows

    def get_window_rect(self, wid: int) -> QRect | None:
        """Truy vấn nhanh tọa độ hiện tại của một cửa sổ theo ID (trả về None nếu đã đóng/thu nhỏ)."""
        if not wid:
            return None
        for tw in self.sample_tracked():
            if tw.wid == wid:
                return tw.rect
        return None

    def _get_ulongs_prop(self, dpy, win: int, atom: int) -> list[int]:
        actual_type = ctypes.c_ulong()
        actual_fmt = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        prop = ctypes.c_void_p()
        st = self._x11.XGetWindowProperty(
            dpy, win, atom, 0, 1024, 0, 0,
            ctypes.byref(actual_type), ctypes.byref(actual_fmt),
            ctypes.byref(nitems), ctypes.byref(bytes_after), ctypes.byref(prop),
        )
        res: list[int] = []
        if st == 0 and prop.value and actual_fmt.value == 32 and nitems.value > 0:
            arr = (ctypes.c_ulong * nitems.value).from_address(prop.value)
            res = [int(arr[i]) for i in range(nitems.value)]
        if prop.value:
            self._x11.XFree(prop)
        return res

    def _sample_x11(self) -> list[TrackedWindow]:
        rects: list[TrackedWindow] = []
        dpy = None
        try:
            self._x11.XSetErrorHandler(_SILENT_X_ERR_HANDLER)
            dpy = self._x11.XOpenDisplay(None)
            if not dpy:
                return []
            root = self._x11.XDefaultRootWindow(dpy)
            a_stack = self._x11.XInternAtom(dpy, b"_NET_CLIENT_LIST_STACKING", 0)
            a_state = self._x11.XInternAtom(dpy, b"_NET_WM_STATE", 0)
            a_hidden = self._x11.XInternAtom(dpy, b"_NET_WM_STATE_HIDDEN", 0)
            a_skip = self._x11.XInternAtom(dpy, b"_NET_WM_STATE_SKIP_TASKBAR", 0)
            a_type = self._x11.XInternAtom(dpy, b"_NET_WM_WINDOW_TYPE", 0)
            a_desktop = self._x11.XInternAtom(dpy, b"_NET_WM_WINDOW_TYPE_DESKTOP", 0)
            a_dock = self._x11.XInternAtom(dpy, b"_NET_WM_WINDOW_TYPE_DOCK", 0)
            a_pid = self._x11.XInternAtom(dpy, b"_NET_WM_PID", 0)
            a_frame = self._x11.XInternAtom(dpy, b"_NET_FRAME_EXTENTS", 0)

            win_ids = self._get_ulongs_prop(dpy, root, a_stack)
            screen = QGuiApplication.primaryScreen()
            sgeo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

            # Duyệt từ cửa sổ trên cùng xuống dưới
            for wid in reversed(win_ids):
                pids = self._get_ulongs_prop(dpy, wid, a_pid)
                if pids and pids[0] == self._my_pid:
                    continue
                wtypes = self._get_ulongs_prop(dpy, wid, a_type)
                if any(t in (a_desktop, a_dock) for t in wtypes):
                    continue
                states = self._get_ulongs_prop(dpy, wid, a_state)
                if a_hidden in states or a_skip in states:
                    continue

                attr = _XWindowAttributes()
                if not self._x11.XGetWindowAttributes(dpy, wid, ctypes.byref(attr)):
                    continue
                if attr.map_state != 2:  # IsViewable = 2
                    continue
                if attr.width < 220 or attr.height < 140:
                    continue

                rx = ctypes.c_int()
                ry = ctypes.c_int()
                child = ctypes.c_ulong()
                self._x11.XTranslateCoordinates(
                    dpy, wid, root, 0, 0,
                    ctypes.byref(rx), ctypes.byref(ry), ctypes.byref(child),
                )
                ext = self._get_ulongs_prop(dpy, wid, a_frame)
                left_e, right_e, top_e, bot_e = (ext[0], ext[1], ext[2], ext[3]) if len(ext) >= 4 else (0, 0, 0, 0)
                x = rx.value - left_e
                y = ry.value - top_e
                w = attr.width + left_e + right_e
                h = attr.height + top_e + bot_e

                # Bỏ qua cửa sổ full-screen sát đỉnh (không còn chỗ phía trên để ngó đầu)
                # vẫn giữ nếu đỉnh >= top + 40 để cá đậu lên thanh tiêu đề
                if y >= sgeo.top() + 36 and y <= sgeo.bottom() - 120:
                    rects.append(TrackedWindow(wid=int(wid), rect=QRect(x, y, w, h)))
        except Exception:
            pass
        finally:
            if dpy:
                try:
                    self._x11.XCloseDisplay(dpy)
                except Exception:
                    pass
        return rects

    def _sample_windows(self) -> list[TrackedWindow]:
        rects: list[TrackedWindow] = []
        try:
            user32 = ctypes.windll.user32

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            pid_c = ctypes.c_ulong()

            def cb(hwnd, _):
                if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                    return True
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
                if pid_c.value == self._my_pid:
                    return True
                rc = RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rc)):
                    w = rc.right - rc.left
                    h = rc.bottom - rc.top
                    if w >= 240 and h >= 150 and rc.top >= 40:
                        rects.append(TrackedWindow(wid=int(hwnd), rect=QRect(rc.left, rc.top, w, h)))
                return True

            user32.EnumWindows(enum_proc(cb), 0)
        except Exception:
            pass
        return rects

    @staticmethod
    def _load_macos_cg() -> dict[str, object] | None:
        """Tải CoreGraphics + CoreFoundation qua ctypes để lấy danh sách cửa sổ ứng dụng trên macOS."""
        try:
            cg_path = ctypes.util.find_library("CoreGraphics")
            cf_path = ctypes.util.find_library("CoreFoundation")
            if not cg_path or not cf_path:
                return None
            cg = ctypes.CDLL(cg_path)
            cf = ctypes.CDLL(cf_path)

            class _CGPoint(ctypes.Structure):
                _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

            class _CGSize(ctypes.Structure):
                _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

            class _CGRect(ctypes.Structure):
                _fields_ = [("origin", _CGPoint), ("size", _CGSize)]

            cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
            cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
            cg.CGRectMakeWithDictionaryRepresentation.argtypes = [ctypes.c_void_p, ctypes.POINTER(_CGRect)]
            cg.CGRectMakeWithDictionaryRepresentation.restype = ctypes.c_bool

            cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
            cf.CFArrayGetCount.restype = ctypes.c_long
            cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
            cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
            cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            cf.CFDictionaryGetValue.restype = ctypes.c_void_p
            cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p]
            cf.CFNumberGetValue.restype = ctypes.c_bool
            cf.CFRelease.argtypes = [ctypes.c_void_p]

            return {
                "cg": cg,
                "cf": cf,
                "CGRect": _CGRect,
                "k_layer": ctypes.c_void_p.in_dll(cg, "kCGWindowLayer"),
                "k_pid": ctypes.c_void_p.in_dll(cg, "kCGWindowOwnerPID"),
                "k_bounds": ctypes.c_void_p.in_dll(cg, "kCGWindowBounds"),
                "k_alpha": ctypes.c_void_p.in_dll(cg, "kCGWindowAlpha"),
                "k_number": ctypes.c_void_p.in_dll(cg, "kCGWindowNumber"),
            }
        except Exception:
            return None

    def _sample_macos(self) -> list[TrackedWindow]:
        """Lấy tọa độ và ID các cửa sổ ứng dụng đang hiển thị trên macOS (ưu tiên từ trên xuống dưới)."""
        rects: list[TrackedWindow] = []
        rt = self._mac_cg
        if not rt:
            return rects
        cg = rt["cg"]
        cf = rt["cf"]
        CGRect = rt["CGRect"]
        arr = None
        try:
            # kCGWindowListOptionOnScreenOnly (1<<0) | kCGWindowListExcludeDesktopElements (1<<4)
            arr = cg.CGWindowListCopyWindowInfo((1 << 0) | (1 << 4), 0)  # type: ignore[attr-defined]
            if not arr:
                return rects

            screen = QGuiApplication.primaryScreen()
            sgeo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
            count = int(cf.CFArrayGetCount(arr))  # type: ignore[attr-defined]

            kCFNumberSInt64Type = 4
            kCFNumberFloat64Type = 6
            layer = ctypes.c_int64()
            pid = ctypes.c_int64()
            wnum = ctypes.c_int64()
            alpha = ctypes.c_double()
            rc = CGRect()  # type: ignore[operator]

            for i in range(count):
                d = cf.CFArrayGetValueAtIndex(arr, i)  # type: ignore[attr-defined]
                if not d:
                    continue
                layer_ref = cf.CFDictionaryGetValue(d, rt["k_layer"])  # type: ignore[attr-defined]
                pid_ref = cf.CFDictionaryGetValue(d, rt["k_pid"])  # type: ignore[attr-defined]
                bounds_ref = cf.CFDictionaryGetValue(d, rt["k_bounds"])  # type: ignore[attr-defined]
                if not (layer_ref and pid_ref and bounds_ref):
                    continue

                if not cf.CFNumberGetValue(layer_ref, kCFNumberSInt64Type, ctypes.byref(layer)):  # type: ignore[attr-defined]
                    continue
                if layer.value != 0:  # Chỉ lấy cửa sổ ứng dụng thông thường (bỏ menu bar, dock, overlay)
                    continue

                if not cf.CFNumberGetValue(pid_ref, kCFNumberSInt64Type, ctypes.byref(pid)):  # type: ignore[attr-defined]
                    continue
                if pid.value == self._my_pid:
                    continue

                alpha_ref = cf.CFDictionaryGetValue(d, rt["k_alpha"])  # type: ignore[attr-defined]
                if alpha_ref and cf.CFNumberGetValue(alpha_ref, kCFNumberFloat64Type, ctypes.byref(alpha)):  # type: ignore[attr-defined]
                    if alpha.value < 0.15:
                        continue

                if not cg.CGRectMakeWithDictionaryRepresentation(bounds_ref, ctypes.byref(rc)):  # type: ignore[attr-defined]
                    continue

                x = int(rc.origin.x)
                y = int(rc.origin.y)
                w = int(rc.size.width)
                h = int(rc.size.height)
                if w < 220 or h < 140:
                    continue
                if y >= sgeo.top() - 10 and y <= sgeo.bottom() - 100:
                    wnum.value = 0
                    num_ref = cf.CFDictionaryGetValue(d, rt["k_number"])  # type: ignore[attr-defined]
                    if num_ref:
                        cf.CFNumberGetValue(num_ref, kCFNumberSInt64Type, ctypes.byref(wnum))  # type: ignore[attr-defined]
                    rects.append(TrackedWindow(wid=int(wnum.value), rect=QRect(x, y, w, h)))
        except Exception:
            pass
        finally:
            if arr:
                try:
                    cf.CFRelease(arr)  # type: ignore[attr-defined]
                except Exception:
                    pass
        return rects


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

        if self._x11 is not None:
            self._thread = threading.Thread(target=self._run_x11_loop, daemon=True)
            self._thread.start()
        elif sys.platform == "darwin":
            self._setup_macos_hotkeys()
        elif sys.platform == "win32":
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


class SystemPressureMonitor:
    """Theo dõi mức tải CPU và RAM của hệ thống."""

    def __init__(self):
        self._prev_total = 0
        self._prev_idle = 0
        self.cpu_percent = 0.0
        self.ram_percent = 0.0
        self._psutil = None
        try:
            import psutil  # type: ignore
            self._psutil = psutil
            psutil.cpu_percent(interval=None)
        except Exception:
            self._read_linux_cpu()

    def sample(self) -> tuple[float, float]:
        if self._psutil is not None:
            try:
                self.cpu_percent = float(self._psutil.cpu_percent(interval=None))
                self.ram_percent = float(self._psutil.virtual_memory().percent)
                return self.cpu_percent, self.ram_percent
            except Exception:
                pass

        if sys.platform.startswith("linux"):
            self.cpu_percent = self._read_linux_cpu()
            self.ram_percent = self._read_linux_ram()
        elif sys.platform == "win32":
            self.cpu_percent, self.ram_percent = self._read_windows_stats()
        return self.cpu_percent, self.ram_percent

    def _read_linux_cpu(self) -> float:
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                line = f.readline()
            parts = [int(x) for x in line.split()[1:]]
            idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
            total = sum(parts)
            dt = total - self._prev_total
            di = idle - self._prev_idle
            self._prev_total, self._prev_idle = total, idle
            if dt <= 0:
                return self.cpu_percent
            return max(0.0, min(100.0, 100.0 * (dt - di) / dt))
        except Exception:
            return 0.0

    def _read_linux_ram(self) -> float:
        try:
            info: dict[str, int] = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if ":" not in line:
                        continue
                    k, v = line.split(":", 1)
                    if k in ("MemTotal", "MemAvailable"):
                        info[k] = int(v.strip().split()[0])
                    if len(info) == 2:
                        break
            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", total)
            if total <= 0:
                return 0.0
            return max(0.0, min(100.0, 100.0 * (total - avail) / total))
        except Exception:
            return 0.0

    def _read_windows_stats(self) -> tuple[float, float]:
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            return self.cpu_percent, float(mem.dwMemoryLoad)
        except Exception:
            return 0.0, 0.0


class WallpaperColorAnalyzer:
    """Quét nhanh lưới màu nền màn hình để nhận diện vùng xanh/lạnh vs đỏ/cam."""

    COLS = 12
    ROWS = 8

    def __init__(self):
        self.grid: list[list[float]] = [[0.0] * self.COLS for _ in range(self.ROWS)]
        self.screen_rect = QRect(0, 0, 1920, 1080)
        self.has_data = False

    def sample(self, exclude_rect: QRect | None = None):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        self.screen_rect = screen.geometry()
        try:
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                return
            img = pixmap.toImage().scaled(self.COLS, self.ROWS)
            if img.isNull():
                return
        except Exception:
            return

        cw = max(1.0, self.screen_rect.width() / self.COLS)
        ch = max(1.0, self.screen_rect.height() / self.ROWS)

        for r in range(self.ROWS):
            for c in range(self.COLS):
                if exclude_rect is not None:
                    cell_cx = self.screen_rect.left() + int((c + 0.5) * cw)
                    cell_cy = self.screen_rect.top() + int((r + 0.5) * ch)
                    if exclude_rect.contains(QPoint(cell_cx, cell_cy)):
                        continue
                col = QColor(img.pixel(c, r))
                h, s, v, _ = col.getHsv()
                if s < 45 or v < 35:
                    score = 0.0
                elif 170 <= h <= 255:
                    score = (s / 255.0) * (0.4 + 0.6 * (v / 255.0))
                elif h <= 34 or h >= 335:
                    score = -(s / 255.0) * (0.4 + 0.6 * (v / 255.0))
                else:
                    score = 0.0
                self.grid[r][c] = 0.65 * self.grid[r][c] + 0.35 * score
        self.has_data = True

    def score_at(self, gx: float, gy: float) -> float:
        if not self.has_data or self.screen_rect.width() <= 0 or self.screen_rect.height() <= 0:
            return 0.0
        u = (gx - self.screen_rect.left()) / self.screen_rect.width()
        v = (gy - self.screen_rect.top()) / self.screen_rect.height()
        c = max(0, min(self.COLS - 1, int(u * self.COLS)))
        r = max(0, min(self.ROWS - 1, int(v * self.ROWS)))
        return self.grid[r][c]

    def pick_cool_target(self) -> tuple[float, float] | None:
        if not self.has_data:
            return None
        cool_cells: list[tuple[float, int, int]] = []
        for r in range(self.ROWS):
            for c in range(self.COLS):
                if self.grid[r][c] > 0.25:
                    cool_cells.append((self.grid[r][c], r, c))
        if not cool_cells:
            return None
        cool_cells.sort(reverse=True)
        top = cool_cells[: max(1, min(4, len(cool_cells)))]
        _, r, c = top[int(time.time() * 13) % len(top)]
        cw = self.screen_rect.width() / self.COLS
        ch = self.screen_rect.height() / self.ROWS
        return (
            self.screen_rect.left() + (c + 0.5) * cw,
            self.screen_rect.top() + (r + 0.5) * ch,
        )


class AudioSpectrumMonitor:
    """Bắt mức âm thanh & bass drop hệ thống (PipeWire / PulseAudio) + chế độ Demo."""

    def __init__(self):
        self.mode = "auto"  # auto | demo | off
        self.bands = [0.0] * 8
        self.level = 0.0
        self.bass = 0.0
        self._bass_avg = 0.05
        self._beat_flag = False
        self._last_beat_t = 0.0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._start_capture_thread()

    def set_mode(self, mode: str):
        self.mode = mode
        if mode == "off":
            with self._lock:
                self.bands = [0.0] * 8
                self.level = 0.0
                self.bass = 0.0
                self._beat_flag = False

    def _start_capture_thread(self):
        if not sys.platform.startswith("linux"):
            return
        cmd = self._detect_linux_monitor_cmd()
        if cmd is None:
            return
        self._thread = threading.Thread(target=self._capture_loop, args=(cmd,), daemon=True)
        self._thread.start()

    @staticmethod
    def _detect_linux_monitor_cmd() -> list[str] | None:
        if shutil.which("parec"):
            return ["parec", "--format=s16le", "--rate=8000", "--channels=1", "--latency-msec=40"]
        if shutil.which("pw-record"):
            return [
                "pw-record",
                "--raw",
                "--format=s16",
                "--rate=8000",
                "--channels=1",
                "-P",
                "{ stream.capture.sink=true }",
                "-",
            ]
        return None

    def _capture_loop(self, cmd: list[str]):
        chunk_samples = 256
        chunk_bytes = chunk_samples * 2
        low_lp = 0.0
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=chunk_bytes,
            )
            assert self._proc.stdout is not None
            while not self._stop_event.is_set():
                raw = self._proc.stdout.read(chunk_bytes)
                if not raw or len(raw) < chunk_bytes:
                    break
                if self.mode != "auto":
                    continue
                samples = struct.unpack(f"<{chunk_samples}h", raw)
                sq_sum = 0.0
                bass_sum = 0.0
                band_acc = [0.0] * 8
                seg = chunk_samples // 8
                for i, s in enumerate(samples):
                    v = s / 32768.0
                    low_lp = low_lp * 0.86 + v * 0.14
                    sq_sum += v * v
                    bass_sum += low_lp * low_lp
                    band_acc[i // seg] += abs(v)

                rms = math.sqrt(sq_sum / chunk_samples)
                bass_rms = math.sqrt(bass_sum / chunk_samples)
                level = min(1.0, rms * 4.5)
                bass = min(1.0, bass_rms * 7.0)

                now = time.monotonic()
                is_beat = False
                if bass > 0.24 and bass > self._bass_avg * 1.75 and (now - self._last_beat_t) > 0.9:
                    is_beat = True
                    self._last_beat_t = now
                self._bass_avg = 0.92 * self._bass_avg + 0.08 * max(0.03, bass)

                bands = [min(1.0, (a / seg) * 5.2) for a in band_acc]
                with self._lock:
                    self.level = level
                    self.bass = bass
                    self.bands = bands
                    if is_beat:
                        self._beat_flag = True
        except Exception:
            pass
        finally:
            self._terminate_proc()

    def _terminate_proc(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=0.5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def poll(self) -> tuple[float, list[float], bool]:
        if self.mode == "off":
            return 0.0, [0.0] * 8, False

        if self.mode == "demo":
            t = time.monotonic()
            bpm_phase = (t * 124.0 / 60.0) % 1.0
            kick = math.exp(-bpm_phase * 8.0)
            bands = [
                max(0.08, min(1.0, kick * (0.95 - i * 0.07) + 0.28 * abs(math.sin(t * (3.2 + i * 1.1) + i))))
                for i in range(8)
            ]
            level = sum(bands) / 8.0
            beat = False
            if bpm_phase < 0.06 and (t - self._last_beat_t) > 1.8:
                beat = True
                self._last_beat_t = t
            return level, bands, beat

        with self._lock:
            beat = self._beat_flag
            self._beat_flag = False
            return self.level, list(self.bands), beat

    def stop(self):
        self._stop_event.set()
        self._terminate_proc()


class SoundPlayer:
    """Tổng hợp sẵn âm thanh 'bụp' (pop), 'tõm' (splash), khóa lồng 'cạch' và uốn cong kim loại."""

    def __init__(self):
        self._paths: dict[str, str] = {}
        self._effects: dict[str, object] = {}
        self._build_pop()
        self._build_splash()
        self._build_cage_lock()
        self._build_metal_bend()

    def _write_wav(self, name: str, frames: bytes, sample_rate: int = 22050):
        try:
            fd, path = tempfile.mkstemp(prefix=f"fish_{name}_", suffix=".wav")
            os.close(fd)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(frames)
            self._paths[name] = path
            if QSoundEffect is not None:
                eff = QSoundEffect()
                eff.setSource(QUrl.fromLocalFile(path))
                eff.setVolume(0.55)
                self._effects[name] = eff
        except Exception:
            pass

    def _build_pop(self):
        sr = 22050
        n = int(sr * 0.095)
        frames = bytearray()
        for i in range(n):
            t = i / sr
            p = i / n
            freq = 260.0 + 620.0 * (p ** 1.4)
            env = math.sin(math.pi * p) * math.exp(-p * 3.8)
            val = int(max(-1.0, min(1.0, math.sin(2 * math.pi * freq * t) * env * 0.65)) * 32767)
            frames.extend(struct.pack("<h", val))
        self._write_wav("pop", bytes(frames), sr)

    def _build_splash(self):
        sr = 22050
        n = int(sr * 0.22)
        frames = bytearray()
        for i in range(n):
            t = i / sr
            p = i / n
            # Tiếng "tõm" nước: giọt rơi hạ tần rồi vút lên + bọt khí nhẹ
            freq = 520.0 - 260.0 * p + 420.0 * (p ** 2.2)
            env = math.sin(math.pi * p) * math.exp(-p * 2.5)
            w = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * freq * 2.3 * t)
            val = int(max(-1.0, min(1.0, w * env * 0.52)) * 32767)
            frames.extend(struct.pack("<h", val))
        self._write_wav("splash", bytes(frames), sr)

    def _build_cage_lock(self):
        """Tổng hợp tiếng lồng sắt rơi nhẹ + chốt khóa 'cạch' kim loại."""
        sr = 22050
        n = int(sr * 0.25)
        frames = bytearray()
        # LCG giả ngẫu nhiên nhẹ để tạo xung nhiễu kim loại ngắn (không cần random import)
        seed = 1337
        for i in range(n):
            t = i / sr
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            noise = (seed / 0x3FFFFFFF) - 1.0

            # Nhịp 1 (t = 0.00s): tiếng khung sắt chạm xuống ("keng" trầm nhẹ)
            env1 = math.exp(-t * 28.0)
            clang1 = (
                0.50 * math.sin(2 * math.pi * 410.0 * t)
                + 0.35 * math.sin(2 * math.pi * 1085.0 * t)
                + 0.20 * math.sin(2 * math.pi * 1790.0 * t)
            ) * env1

            # Nhịp 2 (t = 0.065s): tiếng chốt khóa "cạch!" sắc gọn
            t2 = t - 0.065
            latch = 0.0
            if t2 >= 0.0:
                env2 = math.exp(-t2 * 45.0)
                snap = math.exp(-t2 * 140.0) * noise * 0.55
                ring = (
                    0.48 * math.sin(2 * math.pi * 1420.0 * t2)
                    + 0.34 * math.sin(2 * math.pi * 2380.0 * t2)
                    + 0.22 * math.sin(2 * math.pi * 3410.0 * t2)
                ) * env2
                latch = ring + snap

            w = (clang1 * 0.55 + latch * 0.78) * 0.68
            val = int(max(-1.0, min(1.0, w)) * 32767)
            frames.extend(struct.pack("<h", val))
        self._write_wav("cage_lock", bytes(frames), sr)

    def _build_metal_bend(self):
        """Tổng hợp âm thanh kim loại rên rỉ uốn cong và bật tách thanh sắt."""
        sr = 22050
        n = int(sr * 0.58)
        frames = bytearray()
        phase1 = 0.0
        phase2 = 0.0
        phase3 = 0.0
        seed = 4242
        for i in range(n):
            t = i / sr
            p = i / n
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            noise = (seed / 0x3FFFFFFF) - 1.0

            # Tiếng rít/uốn thanh sắt tăng dần ứng suất với rung FM kim loại
            strain_wobble = math.sin(2 * math.pi * 19.0 * t) * (18.0 + 35.0 * p)
            f1 = 195.0 + 360.0 * (p ** 1.35) + strain_wobble
            f2 = f1 * 2.76  # họa âm phi điều hòa đặc trưng của kim loại
            f3 = f1 * 4.43
            phase1 += (2 * math.pi * f1) / sr
            phase2 += (2 * math.pi * f2) / sr
            phase3 += (2 * math.pi * f3) / sr

            env_creak = math.sin(math.pi * min(1.0, p / 0.88)) * (0.45 + 0.55 * p)
            creak = (
                0.50 * math.sin(phase1)
                + 0.32 * math.sin(phase2)
                + 0.18 * math.sin(phase3)
            ) * env_creak

            # Cú bật/gãy thanh sắt ở cuối (p >= 0.76)
            t_snap = t - 0.44
            snap = 0.0
            if t_snap >= 0.0:
                s_env = math.exp(-t_snap * 24.0)
                snap = (
                    0.55 * math.sin(2 * math.pi * 880.0 * t_snap)
                    + 0.40 * math.sin(2 * math.pi * 1640.0 * t_snap)
                    + 0.30 * math.exp(-t_snap * 90.0) * noise
                ) * s_env

            w = (creak * 0.62 + snap * 0.72) * 0.65
            val = int(max(-1.0, min(1.0, w)) * 32767)
            frames.extend(struct.pack("<h", val))
        self._write_wav("metal_bend", bytes(frames), sr)

    def _play(self, name: str):
        eff = self._effects.get(name)
        if eff is not None:
            try:
                eff.play()  # type: ignore[attr-defined]
                return
            except Exception:
                pass
        path = self._paths.get(name)
        if not path:
            return
        if sys.platform.startswith("linux") and shutil.which("aplay"):
            try:
                subprocess.Popen(
                    ["aplay", "-q", path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        elif sys.platform == "darwin" and shutil.which("afplay"):
            try:
                subprocess.Popen(
                    ["afplay", path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def play_pop(self):
        self._play("pop")

    def play_splash(self):
        self._play("splash")

    def play_cage_lock(self):
        self._play("cage_lock")

    def play_metal_bend(self):
        self._play("metal_bend")

    def cleanup(self):
        for path in self._paths.values():
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        self._paths.clear()


def is_late_night() -> bool:
    """Kiểm tra đã qua 23:30 đêm (từ 23:30 tới 04:30 sáng) chưa."""
    now = datetime.now()
    mins = now.hour * 60 + now.minute
    return mins >= 23 * 60 + 30 or mins < 4 * 60 + 30


# ---------- Hỗ trợ macOS Multi-Desktop (Spaces) & Full-Screen ----------

_MACOS_OBJC_CACHE: dict[str, object] | None = None
_MACOS_OBJC_FAILED = False

_NS_CAN_JOIN_ALL_SPACES = 1 << 0
_NS_MOVE_TO_ACTIVE_SPACE = 1 << 1
_NS_STATIONARY = 1 << 4
_NS_FULLSCREEN_AUXILIARY = 1 << 8
_NS_ACTIVATION_POLICY_ACCESSORY = 1


def _get_macos_objc() -> dict[str, object] | None:
    """Tải và cache các chữ ký gọi Objective-C runtime an toàn cho cả Apple Silicon (arm64) & Intel."""
    global _MACOS_OBJC_CACHE, _MACOS_OBJC_FAILED
    if sys.platform != "darwin" or _MACOS_OBJC_FAILED:
        return None
    if _MACOS_OBJC_CACHE is not None:
        return _MACOS_OBJC_CACHE
    try:
        lib_path = ctypes.util.find_library("objc")
        if not lib_path:
            _MACOS_OBJC_FAILED = True
            return None
        objc = ctypes.CDLL(lib_path)
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p

        _MACOS_OBJC_CACHE = {
            "objc": objc,
            "msg_ptr": ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc)),
            "msg_ulong": ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc)),
            "msg_void_ulong": ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(("objc_msgSend", objc)),
            "msg_void_bool": ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)(("objc_msgSend", objc)),
            "msg_bool_sel": ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc)),
            "msg_bool_long": ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(("objc_msgSend", objc)),
            "sel_window": objc.sel_registerName(b"window"),
            "sel_get_beh": objc.sel_registerName(b"collectionBehavior"),
            "sel_set_beh": objc.sel_registerName(b"setCollectionBehavior:"),
            "sel_set_hide_deact": objc.sel_registerName(b"setHidesOnDeactivate:"),
            "sel_set_can_hide": objc.sel_registerName(b"setCanHide:"),
            "sel_set_ign_mouse": objc.sel_registerName(b"setIgnoresMouseEvents:"),
            "sel_responds": objc.sel_registerName(b"respondsToSelector:"),
            "sel_shared_app": objc.sel_registerName(b"sharedApplication"),
            "sel_set_policy": objc.sel_registerName(b"setActivationPolicy:"),
        }
        return _MACOS_OBJC_CACHE
    except Exception:
        _MACOS_OBJC_FAILED = True
        return None


def configure_macos_app_for_spaces() -> bool:
    """Đặt NSApplication ở chế độ Accessory trên macOS để Pet nổi trên mọi Desktop & Full-Screen
    mà không bị macOS kéo về Desktop cũ khi tương tác."""
    rt = _get_macos_objc()
    if rt is None:
        return False
    try:
        objc = rt["objc"]  # type: ignore[assignment]
        ns_app_cls = objc.objc_getClass(b"NSApplication")  # type: ignore[attr-defined]
        if not ns_app_cls:
            return False
        ns_app = rt["msg_ptr"](ns_app_cls, rt["sel_shared_app"])  # type: ignore[operator]
        if not ns_app:
            return False
        return bool(rt["msg_bool_long"](ns_app, rt["sel_set_policy"], _NS_ACTIVATION_POLICY_ACCESSORY))  # type: ignore[operator]
    except Exception:
        return False


def apply_macos_all_spaces(widget, enabled: bool = True) -> bool:
    """Cấu hình NSWindowCollectionBehavior cho một QWidget trên macOS để đi theo qua mọi Desktop (Spaces)
    và hiển thị được cả trên ứng dụng Full-Screen."""
    if QGuiApplication.platformName() != "cocoa":
        return False
    rt = _get_macos_objc()
    if rt is None or widget is None:
        return False
    try:
        wid = int(widget.winId())
        if not wid:
            return False
        ns_view = ctypes.c_void_p(wid)
        ns_win = rt["msg_ptr"](ns_view, rt["sel_window"])  # type: ignore[operator]
        if not ns_win:
            return False

        cur_beh = int(rt["msg_ulong"](ns_win, rt["sel_get_beh"]))  # type: ignore[operator]
        if enabled:
            # Gỡ MoveToActiveSpace vì AppKit cấm dùng chung với CanJoinAllSpaces
            new_beh = (
                (cur_beh & ~_NS_MOVE_TO_ACTIVE_SPACE)
                | _NS_CAN_JOIN_ALL_SPACES
                | _NS_STATIONARY
                | _NS_FULLSCREEN_AUXILIARY
            )
        else:
            new_beh = (cur_beh & ~(_NS_CAN_JOIN_ALL_SPACES | _NS_STATIONARY)) | _NS_FULLSCREEN_AUXILIARY

        rt["msg_void_ulong"](ns_win, rt["sel_set_beh"], new_beh)  # type: ignore[operator]

        if rt["msg_bool_sel"](ns_win, rt["sel_responds"], rt["sel_set_hide_deact"]):  # type: ignore[operator]
            rt["msg_void_bool"](ns_win, rt["sel_set_hide_deact"], False)  # type: ignore[operator]
        if rt["msg_bool_sel"](ns_win, rt["sel_responds"], rt["sel_set_can_hide"]):  # type: ignore[operator]
            rt["msg_void_bool"](ns_win, rt["sel_set_can_hide"], False)  # type: ignore[operator]
        return True
    except Exception:
        return False


def set_window_click_through(widget, enabled: bool) -> bool:
    """Bật/tắt chế độ xuyên chuột động (không làm nhấp nháy cửa sổ) cho macOS và Windows.

    Dùng khi cá đang bơi trên thanh tiêu đề để người dùng bấm tab / kéo cửa sổ xuyên qua vùng rìa
    mà vẫn bấm trực tiếp vào thân cá được.
    """
    if widget is None:
        return False
    if sys.platform == "darwin":
        if QGuiApplication.platformName() != "cocoa":
            return False
        rt = _get_macos_objc()
        if rt is None:
            return False
        try:
            wid = int(widget.winId())
            if not wid:
                return False
            ns_win = rt["msg_ptr"](ctypes.c_void_p(wid), rt["sel_window"])  # type: ignore[operator]
            if not ns_win:
                return False
            rt["msg_void_bool"](ns_win, rt["sel_set_ign_mouse"], bool(enabled))  # type: ignore[operator]
            return True
        except Exception:
            return False
    if sys.platform == "win32":
        try:
            hwnd = int(widget.winId())
            if not hwnd:
                return False
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_ex = (ex | WS_EX_TRANSPARENT) if enabled else (ex & ~WS_EX_TRANSPARENT)
            if new_ex != ex:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_ex)
            return True
        except Exception:
            return False
    return False
