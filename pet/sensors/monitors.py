"""Các cảm biến ngữ cảnh: CPU/RAM, màu hình nền và khung giờ khuya."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from datetime import datetime

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QGuiApplication


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




def is_late_night() -> bool:
    """Kiểm tra đã qua 23:30 đêm (từ 23:30 tới 04:30 sáng) chưa."""
    now = datetime.now()
    mins = now.hour * 60 + now.minute
    return mins >= 23 * 60 + 30 or mins < 4 * 60 + 30


