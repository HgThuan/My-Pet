"""Các cảm biến hệ thống, X11 Window Tracker & Global Hotkey cho Desktop Pet Cá Vàng.

Bao gồm:
- SystemPressureMonitor: đo CPU% và RAM%.
- WallpaperColorAnalyzer: quét lưới màu màn hình (ưa xanh dương/lạnh, dè chừng đỏ/cam).
- AudioSpectrumMonitor: bắt biên độ & bass drop từ âm thanh hệ thống + chế độ Demo.
- WindowTracker: lấy tọa độ các cửa sổ ứng dụng đang mở (X11 libX11.so.6 / Windows)
  để cá lướt hoặc đậu ngó lên thanh tiêu đề cửa sổ (Window Perching / Surfing).
- GlobalHotkeyListener: bắt phím tắt toàn cục Ctrl+Shift+H (Boss Key / Lặn sâu ẩn mình)
  qua X11 XGrabKey mà không cần cài thêm thư viện ngoài.
- SoundPlayer: tổng hợp âm thanh "bụp" (pop) và "tõm" (splash) bằng code.
"""
from __future__ import annotations

import ctypes
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


class WindowTracker:
    """Lấy danh sách hình chữ nhật của các cửa sổ ứng dụng đang mở (trình duyệt, IDE, terminal...)."""

    def __init__(self):
        self._x11 = _load_x11()
        self._my_pid = os.getpid()
        self.windows: list[QRect] = []

    def sample(self) -> list[QRect]:
        if self._x11 is not None:
            self.windows = self._sample_x11()
        elif sys.platform == "win32":
            self.windows = self._sample_windows()
        else:
            self.windows = []
        return self.windows

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

    def _sample_x11(self) -> list[QRect]:
        rects: list[QRect] = []
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
                    rects.append(QRect(x, y, w, h))
        except Exception:
            pass
        finally:
            if dpy:
                try:
                    self._x11.XCloseDisplay(dpy)
                except Exception:
                    pass
        return rects

    def _sample_windows(self) -> list[QRect]:
        rects: list[QRect] = []
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
                        rects.append(QRect(rc.left, rc.top, w, h))
                return True

            user32.EnumWindows(enum_proc(cb), 0)
        except Exception:
            pass
        return rects


class GlobalHotkeyListener(QObject):
    """Lắng nghe phím tắt toàn cục Ctrl + Shift + H (Boss Key) trên X11 bằng ctypes."""

    triggered = Signal()

    def __init__(self):
        super().__init__()
        self._x11 = _load_x11()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        if self._x11 is not None:
            self._thread = threading.Thread(target=self._run_x11_loop, daemon=True)
            self._thread.start()

    def _run_x11_loop(self):
        dpy = None
        try:
            self._x11.XSetErrorHandler(_SILENT_X_ERR_HANDLER)
            dpy = self._x11.XOpenDisplay(None)
            if not dpy:
                return
            root = self._x11.XDefaultRootWindow(dpy)
            # Keysym 'h' = 0x0068, ControlMask = 1<<2 (4), ShiftMask = 1<<0 (1)
            keycode = self._x11.XKeysymToKeycode(dpy, 0x0068)
            if not keycode:
                return
            base_mod = 4 | 1  # Ctrl + Shift
            # Grab cả các biến thể CapsLock (2) và NumLock (16)
            for extra in (0, 2, 16, 18):
                self._x11.XGrabKey(dpy, int(keycode), base_mod | extra, root, 0, 1, 1)
            self._x11.XSelectInput(dpy, root, 1)  # KeyPressMask = 1
            self._x11.XSync(dpy, 0)

            fd = self._x11.XConnectionNumber(dpy)
            ev = _XEvent()
            last_fire = 0.0

            while not self._stop_event.is_set():
                rlist, _, _ = select.select([fd], [], [], 0.25)
                if not rlist:
                    continue
                while self._x11.XPending(dpy) > 0:
                    self._x11.XNextEvent(dpy, ctypes.byref(ev))
                    if ev.type == 2 and ev.xkey.keycode == keycode:  # KeyPress = 2
                        now = time.monotonic()
                        if now - last_fire > 0.35:
                            last_fire = now
                            self.triggered.emit()

            for extra in (0, 2, 16, 18):
                self._x11.XUngrabKey(dpy, int(keycode), base_mod | extra, root)
        except Exception:
            pass
        finally:
            if dpy:
                try:
                    self._x11.XCloseDisplay(dpy)
                except Exception:
                    pass

    def stop(self):
        self._stop_event.set()


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
    """Tổng hợp sẵn âm thanh 'bụp' (pop) và 'tõm' (splash) bằng WAV không cần file ngoài."""

    def __init__(self):
        self._paths: dict[str, str] = {}
        self._effects: dict[str, object] = {}
        self._build_pop()
        self._build_splash()

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

    def _play(self, name: str):
        eff = self._effects.get(name)
        if eff is not None:
            try:
                eff.play()  # type: ignore[attr-defined]
                return
            except Exception:
                pass
        path = self._paths.get(name)
        if path and sys.platform.startswith("linux") and shutil.which("aplay"):
            try:
                subprocess.Popen(
                    ["aplay", "-q", path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def play_pop(self):
        self._play("pop")

    def play_splash(self):
        self._play("splash")

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
