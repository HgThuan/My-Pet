"""Theo dõi danh sách và tọa độ các cửa sổ ứng dụng đang mở (Linux X11 / Windows / macOS)."""
from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication

from pet.models import TrackedWindow
from pet.platform.os_window import _SILENT_X_ERR_HANDLER, _XWindowAttributes, _load_x11


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


