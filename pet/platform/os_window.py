"""Tích hợp tầng cửa sổ OS: X11 ctypes, macOS Spaces/Non-Activating Panel, Win32 No-Activate & Click-Through."""
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


# ---------- Hỗ trợ macOS Multi-Desktop (Spaces), Non-Activating Panel & Full-Screen ----------

_MACOS_OBJC_CACHE: dict[str, object] | None = None
_MACOS_OBJC_FAILED = False

_NS_CAN_JOIN_ALL_SPACES = 1 << 0
_NS_MOVE_TO_ACTIVE_SPACE = 1 << 1
_NS_STATIONARY = 1 << 4
_NS_FULLSCREEN_AUXILIARY = 1 << 8
_NS_ACTIVATION_POLICY_ACCESSORY = 1
_NS_STYLE_MASK_NONACTIVATING_PANEL = 1 << 7  # 0x80 — không bao giờ kích hoạt app hay cướp focus!

# Hằng số Win32 cho Non-Activating & Click-Through
_GWL_EXSTYLE = -20
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_HWND_TOPMOST = -1
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010


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
            "msg_void": ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc)),
            "msg_ptr": ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc)),
            "msg_ulong": ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc)),
            "msg_void_ulong": ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(("objc_msgSend", objc)),
            "msg_void_bool": ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)(("objc_msgSend", objc)),
            "msg_bool_sel": ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc)),
            "msg_bool_ptr": ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc)),
            "msg_bool_long": ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(("objc_msgSend", objc)),
            "sel_window": objc.sel_registerName(b"window"),
            "sel_get_beh": objc.sel_registerName(b"collectionBehavior"),
            "sel_set_beh": objc.sel_registerName(b"setCollectionBehavior:"),
            "sel_get_style": objc.sel_registerName(b"styleMask"),
            "sel_set_style": objc.sel_registerName(b"setStyleMask:"),
            "sel_set_becomes_key": objc.sel_registerName(b"setBecomesKeyOnlyIfNeeded:"),
            "sel_set_floating": objc.sel_registerName(b"setFloatingPanel:"),
            "sel_order_front": objc.sel_registerName(b"orderFrontRegardless"),
            "sel_is_kind_of": objc.sel_registerName(b"isKindOfClass:"),
            "sel_set_hide_deact": objc.sel_registerName(b"setHidesOnDeactivate:"),
            "sel_set_can_hide": objc.sel_registerName(b"setCanHide:"),
            "sel_set_ign_mouse": objc.sel_registerName(b"setIgnoresMouseEvents:"),
            "sel_responds": objc.sel_registerName(b"respondsToSelector:"),
            "sel_shared_app": objc.sel_registerName(b"sharedApplication"),
            "sel_set_policy": objc.sel_registerName(b"setActivationPolicy:"),
            "cls_ns_panel": objc.objc_getClass(b"NSPanel"),
        }
        return _MACOS_OBJC_CACHE
    except Exception:
        _MACOS_OBJC_FAILED = True
        return None


def _get_macos_nswindow(widget) -> tuple[dict[str, object], ctypes.c_void_p] | None:
    if QGuiApplication.platformName() != "cocoa":
        return None
    rt = _get_macos_objc()
    if rt is None or widget is None:
        return None
    try:
        wid = int(widget.winId())
        if not wid:
            return None
        ns_win = rt["msg_ptr"](ctypes.c_void_p(wid), rt["sel_window"])  # type: ignore[operator]
        if not ns_win:
            return None
        return rt, ns_win
    except Exception:
        return None


def _win32_get_exstyle(user32, hwnd: int) -> int:
    getter = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    return int(getter(hwnd, _GWL_EXSTYLE))


def _win32_set_exstyle(user32, hwnd: int, exstyle: int) -> None:
    setter = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    setter(hwnd, _GWL_EXSTYLE, exstyle)


def configure_macos_app_for_spaces() -> bool:
    """Đặt NSApplication ở chế độ Accessory trên macOS để Pet nổi trên mọi Desktop & Full-Screen
    mà không hiện icon Dock và không cướp không gian làm việc khi tương tác."""
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


def configure_non_activating_window(widget) -> bool:
    """Cấu hình cửa sổ Pet / Overlay ở tầng OS native để TUYỆT ĐỐI không cướp Focus bàn phím / IME.

    - macOS: bật NSWindowStyleMaskNonactivatingPanel + setBecomesKeyOnlyIfNeeded:YES trên NSPanel.
    - Windows: bật WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW.
    - Linux: Qt WindowDoesNotAcceptFocus + WA_ShowWithoutActivating + NoFocus đảm bảo WM_HINTS.input=False.
    """
    if widget is None:
        return False

    if sys.platform == "darwin":
        pair = _get_macos_nswindow(widget)
        if pair is None:
            return False
        rt, ns_win = pair
        try:
            ns_panel_cls = rt.get("cls_ns_panel")
            is_panel = bool(
                ns_panel_cls
                and rt["msg_bool_ptr"](ns_win, rt["sel_is_kind_of"], ns_panel_cls)  # type: ignore[operator]
            )
            if is_panel:
                cur_style = int(rt["msg_ulong"](ns_win, rt["sel_get_style"]))  # type: ignore[operator]
                if not (cur_style & _NS_STYLE_MASK_NONACTIVATING_PANEL):
                    rt["msg_void_ulong"](ns_win, rt["sel_set_style"], cur_style | _NS_STYLE_MASK_NONACTIVATING_PANEL)  # type: ignore[operator]
                if rt["msg_bool_sel"](ns_win, rt["sel_responds"], rt["sel_set_becomes_key"]):  # type: ignore[operator]
                    rt["msg_void_bool"](ns_win, rt["sel_set_becomes_key"], True)  # type: ignore[operator]
                if rt["msg_bool_sel"](ns_win, rt["sel_responds"], rt["sel_set_floating"]):  # type: ignore[operator]
                    rt["msg_void_bool"](ns_win, rt["sel_set_floating"], True)  # type: ignore[operator]

            if rt["msg_bool_sel"](ns_win, rt["sel_responds"], rt["sel_set_hide_deact"]):  # type: ignore[operator]
                rt["msg_void_bool"](ns_win, rt["sel_set_hide_deact"], False)  # type: ignore[operator]
            if rt["msg_bool_sel"](ns_win, rt["sel_responds"], rt["sel_set_can_hide"]):  # type: ignore[operator]
                rt["msg_void_bool"](ns_win, rt["sel_set_can_hide"], False)  # type: ignore[operator]
            return True
        except Exception:
            return False

    if sys.platform == "win32":
        try:
            hwnd = int(widget.winId())
            if not hwnd:
                return False
            user32 = ctypes.windll.user32
            ex = _win32_get_exstyle(user32, hwnd)
            new_ex = ex | _WS_EX_NOACTIVATE | _WS_EX_TOOLWINDOW
            if new_ex != ex:
                _win32_set_exstyle(user32, hwnd, new_ex)
            return True
        except Exception:
            return False

    return True


def bring_window_to_front_no_activate(widget) -> bool:
    """Đưa cửa sổ lên lớp hiển thị trên cùng mà KHÔNG kích hoạt app và KHÔNG cướp focus bàn phím."""
    if widget is None:
        return False

    if sys.platform == "darwin":
        pair = _get_macos_nswindow(widget)
        if pair is None:
            return False
        rt, ns_win = pair
        try:
            if rt["msg_bool_sel"](ns_win, rt["sel_responds"], rt["sel_order_front"]):  # type: ignore[operator]
                rt["msg_void"](ns_win, rt["sel_order_front"])  # type: ignore[operator]
                return True
        except Exception:
            return False
        return False

    if sys.platform == "win32":
        try:
            hwnd = int(widget.winId())
            if not hwnd:
                return False
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                _HWND_TOPMOST,
                0,
                0,
                0,
                0,
                _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE,
            )
            return True
        except Exception:
            return False

    # Linux (X11/Wayland): WindowStaysOnTopHint đã giữ lớp trên cùng, tránh gọi raise_() để không giật focus WM
    return True


def apply_macos_all_spaces(widget, enabled: bool = True) -> bool:
    """Cấu hình NSWindowCollectionBehavior cho một QWidget trên macOS để đi theo qua mọi Desktop (Spaces)
    và hiển thị được cả trên ứng dụng Full-Screen."""
    pair = _get_macos_nswindow(widget)
    if pair is None:
        return False
    rt, ns_win = pair
    try:
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
    """Bật/tắt chế độ xuyên chuột động (không cắt hình, không cướp focus) cho macOS, Windows và Linux X11."""
    if widget is None:
        return False
    if sys.platform == "darwin":
        pair = _get_macos_nswindow(widget)
        if pair is None:
            return False
        rt, ns_win = pair
        try:
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
            raw_ex = _win32_get_exstyle(user32, hwnd)
            ex = raw_ex | _WS_EX_NOACTIVATE | _WS_EX_TOOLWINDOW
            new_ex = (ex | _WS_EX_TRANSPARENT) if enabled else (ex & ~_WS_EX_TRANSPARENT)
            if new_ex != raw_ex:
                _win32_set_exstyle(user32, hwnd, new_ex)
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
                # Chỉ rỗng vùng nhận chuột (ShapeInput), KHÔNG chạm tới ShapeBounding nên không cắt hình!
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


def configure_overlay_window(
    widget,
    all_spaces: bool = True,
    click_through: bool | None = None,
) -> bool:
    """Áp dụng trọn bộ cấu hình cửa sổ overlay không cướp focus + All-Spaces + xuyên chuột native."""
    ok = configure_non_activating_window(widget)
    if sys.platform == "darwin":
        apply_macos_all_spaces(widget, all_spaces)
    if click_through is not None:
        set_window_click_through(widget, click_through)
    return ok
