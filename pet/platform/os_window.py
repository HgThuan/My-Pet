"""Tích hợp tầng cửa sổ OS: X11 ctypes, macOS Spaces & Linux XShape click-through."""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys

from PySide6.QtGui import QGuiApplication

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


_XSHAPE_CACHE: dict[str, object] | None = None


def _get_linux_xshape() -> dict[str, object] | None:
    """Nạp libX11 + libXext để bật/tắt xuyên chuột bằng ShapeInput (không bao giờ cắt hình ảnh!)."""
    global _XSHAPE_CACHE
    if _XSHAPE_CACHE is not None:
        return _XSHAPE_CACHE or None
    if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
        _XSHAPE_CACHE = {}
        return None
    try:
        x11 = _load_x11()
        if x11 is None:
            _XSHAPE_CACHE = {}
            return None
        x11.XFlush.argtypes = [ctypes.c_void_p]
        xext = ctypes.CDLL("libXext.so.6")
        xext.XShapeCombineRectangles.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
            ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ]
        xext.XShapeCombineMask.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_ulong, ctypes.c_int,
        ]
        _XSHAPE_CACHE = {"x11": x11, "xext": xext}
        return _XSHAPE_CACHE
    except Exception:
        _XSHAPE_CACHE = {}
        return None


def set_window_click_through(widget, enabled: bool) -> bool:
    """Bật/tắt chế độ xuyên chuột động (không cắt hình, không nhấp nháy) cho macOS, Windows và Linux X11.

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
    if sys.platform.startswith("linux"):
        if QGuiApplication.platformName() != "xcb":
            return False
        xs = _get_linux_xshape()
        if xs is None:
            return False
        dpy = None
        try:
            wid = int(widget.winId())
            if not wid:
                return False
            x11 = xs["x11"]
            xext = xs["xext"]
            x11.XSetErrorHandler(_SILENT_X_ERR_HANDLER)  # type: ignore[attr-defined]
            dpy = x11.XOpenDisplay(None)  # type: ignore[attr-defined]
            if not dpy:
                return False
            SHAPE_INPUT = 2
            SHAPE_SET = 0
            UNSORTED = 0
            if enabled:
                # Chỉ rỗng vùng nhận chuột (ShapeInput), KHÔNG chạm tới ShapeBounding nên không bị cắt hình!
                xext.XShapeCombineRectangles(dpy, wid, SHAPE_INPUT, 0, 0, None, 0, SHAPE_SET, UNSORTED)  # type: ignore[attr-defined]
            else:
                # Khôi phục vùng nhận chuột đầy đủ của cửa sổ
                xext.XShapeCombineMask(dpy, wid, SHAPE_INPUT, 0, 0, 0, SHAPE_SET)  # type: ignore[attr-defined]
            x11.XFlush(dpy)  # type: ignore[attr-defined]
            return True
        except Exception:
            return False
        finally:
            if dpy:
                try:
                    xs["x11"].XCloseDisplay(dpy)  # type: ignore[attr-defined]
                except Exception:
                    pass
    return False
