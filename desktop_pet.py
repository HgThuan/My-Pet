"""Desktop Pet 2D - Cá Vàng (Golden Fish) bản nâng cấp đầy đủ vật lý, vi biểu cảm & tương tác thông minh.

Cài đặt:  pip install PySide6
Chạy:     python desktop_pet.py

Tính năng nổi bật:
1. Vật lý & Chuyển động 2D:
   - Lực đẩy theo nhịp vẫy đuôi (Tail-Beat Impulse) kết hợp lực cản nước mượt mà
   - Quán tính uốn cong (Banking), co giãn đàn hồi kiểu bóng cao su khi cua/chạm mép
   - Ánh sáng khúc xạ (Caustics) lấp lánh trên thân & đuôi bong bóng tan dần (Bubble Trail)
   - Bể cá 360° không trọng lực, chiều sâu 3D (0.85x..1.10x + bóng đổ động), Cursor Wake
2. Vi biểu cảm (Micro-Expressions):
   - Chóng mặt -> Nôn bong bóng cầu vồng -> Nằm ngửa bụng 3s (xoáy nước 3 lần trong 5s)
   - Hắt xì ngẫu nhiên (lấy hơi -> giật lùi + bắn bọt nước)
   - Tự hào / Khoe chiến lợi phẩm (cười ^‿^ bơi hình số 8 sau khi ăn file hoặc mở bong bóng Clipboard)
3. Tương tác thông minh & trò chơi:
   - Đậu / Lướt & Ngó đầu trên thanh tiêu đề cửa sổ đang mở (Window Perching / Surfing)
   - Cho ăn cám cá / Ký tự & Từ khóa rơi từ đỉnh màn hình (ăn no sẽ béo tròn vài phút!)
   - Bóng bàn Bong Bóng (Bubble Pong): tâng bong bóng qua lại giữa con trỏ chuột và mũi cá
   - Boss Key (Ctrl + Shift + H): giật mình lặn tòm xuống đáy kèm gợn sóng, ẩn sạch màn hình
   - Chế độ Lồng Giam (Ctrl + Esc): nhốt cá vào lồng sắt 2D kéo thả cố định vị trí, van xin
     bám thanh sắt, nhấn lần 2 hóa lực sĩ bẻ cong thanh sắt phá lồng thoát ra tự hào
   - Kéo thả file/folder vào miệng cá để ăn & xóa, Cá Nóc (Spam Click), Bong bóng Clipboard,
     Pomodoro Mực Nước Dâng, Cảm biến CPU/RAM > 85%, Bắt sóng âm thanh, Màu hình nền, Giờ khuya > 23:30
"""
from __future__ import annotations

import math
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import quote, unquote

from PySide6.QtCore import QFile, QPoint, QRect, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QCursor,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
    QRegion,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)

from fish_renderer import FISH_THEMES, FishRenderState, Particle, render_fish
from fish_sensors import (
    AudioSpectrumMonitor,
    GlobalHotkeyListener,
    SoundPlayer,
    SystemPressureMonitor,
    TrackedWindow,
    WallpaperColorAnalyzer,
    WindowTracker,
    apply_macos_all_spaces,
    configure_macos_app_for_spaces,
    is_late_night,
    set_window_click_through,
)
from fish_widgets import (
    DEFAULT_WORD_TOKENS,
    URL_RE,
    ClipboardBubble,
    FallingCageOverlay,
    FishFood,
    PongBubble,
    SplashRippleOverlay,
    WaterOverlay,
    paste_or_open_clipboard_payload,
    set_widgets_all_spaces,
)

SIZE = 188
FPS = 60
IDLE_SLEEP_SECS = 5 * 60
CPU_PANIC_THRESHOLD = 85.0
MAX_CLIPBOARD_BUBBLES = 5

# Hệ thống nhìn theo con trỏ chuột 3 lớp tự nhiên (Eye Tracking + Body Tilt + Hysteresis Flip)
CURSOR_ATTENTION_RADIUS = 350.0  # Ngoài 350px cá phớt lờ chuột, tự do bơi ngắm cảnh
FLIP_HYSTERESIS_PX = 35.0        # Vùng đệm ngang ±35px tránh lật trái/phải co giật khi chuột trên đỉnh đầu
EYE_MAX_OFFSET_X = 3.2           # Bán kính ngang tối đa con ngươi (2px - 4px)
EYE_MAX_OFFSET_Y = 2.6           # Bán kính dọc tối đa con ngươi
EYE_LERP_ALPHA = 0.30            # Hệ số lerp liếc mắt gần như tức thì (0.25 - 0.35)
BODY_TILT_THRESHOLD_DEG = 20.0   # Vượt > 20° mới xoay nghiêng thân theo
BODY_TILT_MAX_DEG = 35.0         # Giới hạn góc chúi lên/xuống trong [-35°, +35°]
BODY_TILT_DAMPING = 0.08         # Hệ số giảm chấn góc xoay thân (0.06 - 0.12)
TURN_AROUND_FRAMES = 9           # Chuyển cảnh quay đầu qua Front View (~150ms ở 60 FPS)

RAINBOW_COLORS = [
    QColor(255, 99, 132, 215),
    QColor(255, 159, 64, 215),
    QColor(255, 222, 89, 215),
    QColor(92, 225, 130, 215),
    QColor(72, 202, 245, 215),
    QColor(177, 133, 255, 215),
]

EXPRESSIONS_MENU = [
    ("happy", "😊 Vui vẻ"),
    ("love", "😍 Yêu thương"),
    ("proud", "🥳 Tự hào (Bơi số 8)"),
    ("excited", "🤩 Hào hứng"),
    ("shy", "😳 Ngại ngùng"),
    ("puffed", "🐡 Biến hình Cá Nóc"),
    ("dizzy", "😵 Chóng mặt"),
    ("nauseous", "🌈 Nôn cầu vồng -> Ngửa bụng"),
    ("sneeze", "🤧 Hắt xì!"),
    ("panic", "😱 Hốt hoảng"),
    ("grumpy", "😠 Dỗi hờn"),
    ("sleepy", "🥱 Buồn ngủ"),
]


def _angle_diff(a: float, b: float) -> float:
    return (b - a + math.pi) % math.tau - math.pi


def _lerp_angle_deg(current_deg: float, target_deg: float, alpha: float) -> float:
    """Nội suy góc ngắn nhất theo độ để tránh nhảy góc cứng nhắc."""
    diff = (target_deg - current_deg + 180.0) % 360.0 - 180.0
    return current_deg + diff * alpha


FISH_SURF_BODY_W = 100.0
PORPOISE_MIN_SAFE_W = 310.0  # Đủ rộng cho ít nhất 2 bước nhảy parabol liên tiếp (~150px/nhịp)


def _window_safe_zone(win: QRect) -> tuple[float, float] | None:
    """Tính vùng bơi an toàn [safe_min_x, safe_max_x] trên thanh tiêu đề cửa sổ.

    - macOS: chừa ~84px bên trái tránh 3 nút đèn giao thông, ~40px bên phải.
    - Windows/Linux: chừa ~30px bên trái và ~150px bên phải tránh cụm Minimize/Maximize/Close.
    - Trả về None nếu chiều rộng vùng khả dụng < 310px (không đủ cho ít nhất 2 nhịp nhảy parabol).
    """
    if sys.platform == "darwin":
        safe_min_x = float(win.left() + 84)
        safe_max_x = float(win.right() - 40)
    else:
        safe_min_x = float(win.left() + 30)
        safe_max_x = float(win.right() - 150)
    if (safe_max_x - safe_min_x) < PORPOISE_MIN_SAFE_W:
        return None
    return safe_min_x, safe_max_x


def check_window_surface_snap(
    fish_x: float,
    fish_y: float,
    fish_w: float,
    fish_h: float,
    tracked_windows: list[TrackedWindow],
) -> tuple[bool, TrackedWindow | None, float, float]:
    """Kiểm tra cá có đang lướt sát mép trên cửa sổ đủ rộng để tự động đáp xuống mặt nước hay không."""
    # Điểm đáy bụng cá (cho phép chìm nhẹ ~15% bụng vào thanh tiêu đề)
    fish_bottom = fish_y + fish_h * 0.72
    fish_center_x = fish_x + fish_w * 0.5

    for tw in tracked_windows:
        zone = _window_safe_zone(tw.rect)
        if zone is None:
            continue
        safe_min_x, safe_max_x = zone
        if safe_min_x <= fish_center_x <= safe_max_x:
            if abs(fish_bottom - tw.rect.top()) <= 12.0:
                return True, tw, safe_min_x, safe_max_x
    return False, None, 0.0, 0.0


class GoldenFishPet(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptDrops, True)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.resize(SIZE, SIZE)

        # Giao diện màu sắc
        self.theme_name = "Cá Vàng 🐠"
        self.theme = FISH_THEMES[self.theme_name]

        # Vị trí & vật lý 360° không trọng lực + Tail-Beat Impulse + Banking
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.px = float(screen.center().x() - SIZE // 2)
        self.py = float(screen.center().y() - SIZE // 2)
        self.vx = -1.2
        self.vy = 0.0
        self.direction = -1
        self.pitch_deg = 0.0
        self.bank_deg = 0.0
        self.spin_deg = 0.0
        self.spin_vel = 0.0
        self.backflip_remaining = 0.0
        self.tail_phase = 0.0
        self._prev_heading = math.pi

        # Hệ lò xo co giãn đàn hồi (Procedural Squash & Stretch)
        self.squash_x = 1.0
        self.squash_y = 1.0
        self._squash_vx = 0.0
        self._squash_vy = 0.0

        # Chiều sâu 3D (0.0 = lặn sâu 0.85x, 1.0 = sát kính 1.10x)
        self.depth = 0.65
        self.depth_target = 0.65
        self.dive_scale = 1.0

        # Trạng thái vận động chính:
        # swim | play_dead | drag | puffed | deflate_zoom | eat | swallow_ready
        # swallow_gulp | eat_file | nauseous_vomit | belly_up
        # sneeze_windup | sneeze_burst | celebrate_fig8 | window_surf | window_peek
        # dive_hide | hidden | surface_show | caged | breaking_out
        self.state = "swim"
        self.target_x = self.px
        self.target_y = self.py
        self.retarget_ticks = 90

        # Biểu cảm tạm thời
        self.expression = "normal"
        self.expression_ticks = 0
        self.facing_front = False

        # Biến hoạt hình chuyên biệt
        self.frame = 0
        self.puff_factor = 0.0
        self.puff_ticks = 0
        self.deflate_ticks = 0
        self.swallow_ticks = 0
        self.chew_ticks = 0
        self.vortex_alpha = 0.0
        self.suction_alpha = 0.0
        self.mouth_locked = False
        self._drag_leave_grace = 0
        self.eating_file_progress = -1.0
        self.eating_file_start = (SIZE / 2.0, SIZE / 2.0)
        self.eating_file_is_dir = False

        # Vi biểu cảm: Post-Dizzy cầu vồng, Hắt xì, Ăn mừng số 8
        self._vortex_timestamps: list[float] = []
        self.nauseous_ticks = 0
        self.belly_up_ticks = 0
        self._sneeze_cd = random.randint(28 * FPS, 52 * FPS)
        self.sneeze_ticks = 0
        self.fig8_ticks = 0
        self.fig8_total = int(3.0 * FPS)
        self.fig8_origin = (self.px, self.py)

        # Nhảy sóng kiểu cá heo (Porpoising) & ngó trên thanh tiêu đề cửa sổ
        self.window_perch_enabled = True
        self._perch_wid: int = 0
        self._perch_rect: QRect | None = None
        self._perch_safe_min: float = 0.0
        self._perch_safe_max: float = 0.0
        self._perch_ticks = 0
        self._perch_dir = 1
        self._surf_phase = "approach"  # "approach" | "arc" | "dip" | "dive_out"
        self._porpoise_arcs_left = 0
        self._porpoise_dip_ticks = 0
        self._porpoise_dive_ticks = 0
        self._surf_landed = False
        self._surf_dip = 0.0
        self._surf_dip_vel = 0.0
        self._surf_balance_deg = 0.0
        self._surf_drag_ticks = 0
        self._surf_elapsed = 0
        self._surf_snap_cooldown = 0
        self._surf_nip_phase = "none"  # "none" | "chase" | "nip" | "flee"
        self._surf_nip_ticks = 0
        self._surf_nip_cd = 0
        self._window_leap_ticks = 0
        self._window_drop_ticks = 0
        self._click_through_active = False
        self._linux_mask_active = False

        # Độ no / béo tròn sau khi ăn cám hoặc ký tự
        self.fullness = 0.0        # số hạt đã ăn gần đây
        self.chubby_factor = 0.0   # 0..1 độ béo tròn hiển thị
        self._chubby_ticks = 0     # đếm ngược 2 phút béo tròn

        # Boss Key (Lặn sâu ẩn mình)
        self.boss_hidden = False
        self._saved_surface_y = self.py

        # Chế độ Lồng Giam (Cage Mode: FREE_SWIM -> CAGED -> BREAKING_OUT -> FREE_SWIM)
        self.cage_drop_total = 22
        self.cage_drop_ticks = 0
        self.cage_lock_played = False
        self.cage_dragging = False
        self.cage_swing_deg = 0.0
        self.cage_swing_vel = 0.0
        self.cage_plead_cooldown = 0
        self.cage_plead_ticks = 0
        self.cage_break_total = int(1.5 * FPS)
        self.cage_break_ticks = 0
        self.cage_bend_amount = 0.0
        self.cage_muscular = 0.0
        self.cage_break_sound_played = False
        self.cage_break_released = False

        self.blink_timer = random.randint(90, 240)
        self.blink_frames = 0
        self._bubble_cd = random.randint(60, 120)  # Sinh bong bóng động mỗi 1–2 giây
        self._music_bubble_cd = 0
        self._dead_peek_cd = random.randint(5 * FPS, 9 * FPS)
        self._dead_peek_ticks = 0

        # Vuốt ve & Spam Click
        self.pet_rub_energy = 0.0
        self.pet_love_streak = 0
        self.last_hover_pos: QPoint | None = None
        self.click_timestamps: list[float] = []

        # Kéo thả chuột trái
        self._press_global: QPoint | None = None
        self._drag_offset: QPoint | None = None
        self._last_drag_global: QPoint | None = None
        self._drag_vel_x = 0.0
        self._drag_vel_y = 0.0

        # Theo dõi chuột, nhìn theo chuột 3 lớp & idle
        self._last_cursor = QCursor.pos()
        self._last_user_activity = time.monotonic()
        self._wake_cooldown = 0
        self.cursor_gaze_enabled = True
        self.pupil_x = 0.0
        self.pupil_y = 0.0
        self._turn_ticks = 0
        self._turn_from_dir = self.direction

        # Tùy chọn
        self.chase_mode = False
        self.hold_still = False
        self.all_spaces_enabled = True
        self.delete_mode = "trash"
        self.clipboard_bubbles_enabled = True
        self.wallpaper_aware = True
        self.simulate_overload = False
        self.simulate_late_night = False
        self._ignore_clipboard_until = 0.0
        self._last_clip_sig = ""

        # Cảm biến & Widget vệ tinh
        self.pressure = SystemPressureMonitor()
        self.wallpaper = WallpaperColorAnalyzer()
        self.audio = AudioSpectrumMonitor()
        self.window_tracker = WindowTracker()
        self.sound = SoundPlayer()
        self.water_overlay = WaterOverlay()
        self.splash_overlay = SplashRippleOverlay()
        self.falling_cage_overlay = FallingCageOverlay()

        self.cpu_percent = 0.0
        self.ram_percent = 0.0
        self.is_overloaded = False
        self.is_night_mode = False
        self.audio_level = 0.0
        self.audio_bands = [0.0] * 8
        self.current_color_score = 0.0
        self.tracked_windows: list[TrackedWindow] = []
        self.open_windows: list[QRect] = []

        self.foods: list[FishFood] = []
        self._eating_food: FishFood | None = None
        self.pong_bubble: PongBubble | None = None
        self.clipboard_bubbles: list[ClipboardBubble] = []
        self.particles: list[Particle] = []

        # Clipboard listener
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

        # Phím tắt toàn cục: Ctrl+Shift+H (Boss Key) & Ctrl+Esc (Lồng giam) + nội bộ Qt + System Tray
        self.hotkey = GlobalHotkeyListener()
        self.hotkey.triggered.connect(self.toggle_boss_hide)
        self.hotkey.cage_triggered.connect(self.toggle_cage_mode)
        self._local_boss_shortcut = QShortcut(QKeySequence("Ctrl+Shift+H"), self)
        self._local_boss_shortcut.activated.connect(self.toggle_boss_hide)
        self._local_cage_shortcut = QShortcut(QKeySequence("Ctrl+Esc"), self)
        self._local_cage_shortcut.activated.connect(self.toggle_cage_mode)
        self._init_tray_icon()

        self.move(int(self.px), int(self.py))
        self._pick_new_swim_target()

        # Vòng lặp chính 60 FPS
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000 // FPS)

        # Bộ đếm cảm biến định kỳ
        self.sensor_timer = QTimer(self)
        self.sensor_timer.timeout.connect(self._poll_slow_sensors)
        self.sensor_timer.start(1800)

        self.wallpaper_timer = QTimer(self)
        self.wallpaper_timer.timeout.connect(self._poll_wallpaper)
        self.wallpaper_timer.start(3200)
        QTimer.singleShot(700, self._poll_wallpaper)
        QTimer.singleShot(500, self._poll_slow_sensors)

        self.set_expression("happy", 90)
        for _ in range(4):
            self.spawn_particle("bubble")

    def _init_tray_icon(self):
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        pm = QPixmap(32, 32)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#ffd93b"))
        p.setPen(QColor("#3b182c"))
        p.drawEllipse(QRectF(5, 6, 20, 20))
        p.setBrush(QColor("#3b182c"))
        p.drawEllipse(QRectF(10, 12, 4, 4))
        p.end()

        tray = QSystemTrayIcon(QIcon(pm), self)
        tray.setToolTip("Cá Vàng Desktop Pet (Ctrl+Esc: Lồng giam | Ctrl+Shift+H: Ẩn/Hiện)")
        tmenu = QMenu()
        tmenu.addAction("🔒 Lồng giam / Phá lồng (Ctrl+Esc)", self.toggle_cage_mode)
        tmenu.addAction("🕶️ Lặn / Ngoi lên (Ctrl+Shift+H)", self.toggle_boss_hide)
        tmenu.addAction("🍤 Thả mưa cám cá", lambda: self.spawn_food_shower(5))
        tmenu.addAction("🏓 Bóng bàn Bong Bóng", self.toggle_bubble_pong)
        tmenu.addSeparator()
        tmenu.addAction("❌ Thoát", QApplication.quit)
        tray.setContextMenu(tmenu)
        tray.activated.connect(
            lambda reason: self.toggle_boss_hide()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        tray.show()
        self.tray = tray

    # ---------- Hình học & tiện ích ----------
    def virtual_rect(self) -> QRectF:
        screens = QGuiApplication.screens()
        left = min(s.availableGeometry().left() for s in screens)
        top = min(s.availableGeometry().top() for s in screens)
        right = max(s.availableGeometry().right() for s in screens)
        bottom = max(s.availableGeometry().bottom() for s in screens)
        return QRectF(left, top, right - left, bottom - top)

    def center_global(self) -> tuple[float, float]:
        return self.px + SIZE / 2.0, self.py + SIZE / 2.0

    def _mouth_local_pos(self) -> tuple[float, float]:
        depth_scale = 0.85 + 0.25 * max(0.0, min(1.0, self.depth))
        mx = SIZE / 2.0 + (14.8 if self.direction > 0 else -14.8) * depth_scale
        my = SIZE / 2.0 + 4.0 + 9.8 * depth_scale
        return mx, my

    def _tail_tip_local_pos(self) -> tuple[float, float]:
        depth_scale = 0.85 + 0.25 * max(0.0, min(1.0, self.depth))
        tx = SIZE / 2.0 + (-50.0 if self.direction > 0 else 50.0) * depth_scale
        ty = SIZE / 2.0 + 4.0 + math.sin(self.tail_phase) * 8.0 * depth_scale
        return tx, ty

    def impulse_squash(self, target_sx: float, target_sy: float):
        """Tạo lực nén/kéo đàn hồi kiểu bóng cao su."""
        self.squash_x = target_sx
        self.squash_y = target_sy
        self._squash_vx = (target_sx - 1.0) * 0.22
        self._squash_vy = (target_sy - 1.0) * 0.22

    def _set_direction(self, new_dir: int, smooth: bool = True):
        """Đổi hướng Trái (-1) / Phải (+1) kèm chuyển cảnh quay đầu qua Front View (~150ms)."""
        if new_dir not in (-1, 1) or new_dir == self.direction:
            return
        if smooth and self.state not in ("caged", "breaking_out", "puffed", "play_dead", "dive_hide", "hidden"):
            self._turn_from_dir = self.direction
            self._turn_ticks = TURN_AROUND_FRAMES
        self.direction = new_dir

    def _update_cursor_eye_tracking(self, cur: QPoint):
        """Lớp 1: Liếc con ngươi độc lập theo con trỏ chuột (lerp 0.30, giới hạn elip 2–3.2px)."""
        fcx, fcy = self.center_global()
        dx = cur.x() - fcx
        dy = cur.y() - fcy
        dist = math.hypot(dx, dy)

        in_cage = self.state == "caged"
        gaze_allowed = in_cage or (
            self.cursor_gaze_enabled
            and dist <= CURSOR_ATTENTION_RADIUS
            and self.state in ("swim", "window_surf", "window_peek", "drag", "play_dead")
        )

        if gaze_allowed and dist > 1.0:
            eye_angle = math.atan2(dy, dx)
            eye_offset = min(dist * 0.05, EYE_MAX_OFFSET_X)
            target_px = math.cos(eye_angle) * eye_offset
            target_py = math.sin(eye_angle) * eye_offset
            # Giới hạn trong hình elip của tròng mắt (rx=3.2px, ry=2.6px)
            norm_e = math.hypot(target_px / EYE_MAX_OFFSET_X, target_py / EYE_MAX_OFFSET_Y)
            if norm_e > 1.0:
                target_px /= norm_e
                target_py /= norm_e
            self.pupil_x += (target_px - self.pupil_x) * EYE_LERP_ALPHA
            self.pupil_y += (target_py - self.pupil_y) * EYE_LERP_ALPHA
        else:
            # Chuột ngoài vùng chú ý 350px -> thả lỏng ánh mắt về tâm tự nhiên
            self.pupil_x *= 0.85
            self.pupil_y *= 0.85
            if abs(self.pupil_x) < 0.03:
                self.pupil_x = 0.0
            if abs(self.pupil_y) < 0.03:
                self.pupil_y = 0.0

    # ---------- Biểu cảm & hạt hiệu ứng ----------
    def set_expression(self, expr: str, duration_ticks: int = 120):
        self.expression = expr
        self.expression_ticks = duration_ticks
        if expr == "happy":
            for _ in range(2):
                self.spawn_particle("heart")
                self.spawn_particle("bubble")
        elif expr == "love":
            for _ in range(4):
                self.spawn_particle("heart")
        elif expr == "proud":
            for _ in range(4):
                self.spawn_particle("star")
        elif expr == "excited":
            self.spawn_particle("excl")
            for _ in range(3):
                self.spawn_particle("star")
        elif expr == "grumpy":
            self.spawn_particle("anger")
        elif expr == "shy":
            self.spawn_particle("sweat")
        elif expr == "dizzy":
            for _ in range(3):
                self.spawn_particle("star")

    def active_expression(self) -> str:
        if self.state == "caged":
            return "pleading" if self.cage_plead_ticks > 0 else "caged_sad"
        if self.state == "breaking_out":
            return "proud" if self.cage_break_released else "muscle_strain"
        if self.state == "play_dead":
            return "play_dead"
        if self.state == "puffed":
            return "puffed"
        if self.state in ("deflate_zoom", "dive_hide"):
            return "panic"
        if self.state == "surface_show":
            return "excited"
        if self.state in ("swallow_ready", "swallow_gulp"):
            return "swallow"
        if self.state in ("eat", "eat_file"):
            return "eat"
        if self.state == "nauseous_vomit":
            return "nauseous"
        if self.state == "belly_up":
            return "belly_up"
        if self.state == "sneeze_windup":
            return "sneeze_windup"
        if self.state == "sneeze_burst":
            return "sneeze_burst"
        if self.state == "celebrate_fig8":
            return "proud"
        if self.state == "window_peek":
            return "peeking"
        if self.state == "window_surf":
            if self._surf_drag_ticks > 0:
                return "surprised"
            if self._surf_nip_phase == "nip":
                return "eat"
            if self._surf_phase == "arc" or self._surf_nip_phase == "chase":
                return "happy"
        if self.state == "window_drop":
            return "surprised"
        if self.state == "window_leap":
            return "excited"
        if self.state == "drag":
            return "panic"
        if self.is_overloaded:
            return "panic"
        if self.foods or (self.pong_bubble is not None and self.pong_bubble.in_rally):
            return "excited"
        if self.expression_ticks > 0:
            return self.expression
        if self.is_night_mode:
            return "sleepy"
        if self.current_color_score < -0.32 and self.wallpaper_aware:
            return "cautious"
        return "normal"

    def spawn_particle(self, kind: str, x: float | None = None, y: float | None = None):
        cx = SIZE / 2.0 if x is None else x
        cy = SIZE / 2.0 if y is None else y

        if kind == "bubble":
            if x is None and y is None:
                # Sinh tự nhiên ngay tại vị trí miệng hoặc đuôi cá
                if random.random() < 0.68:
                    bx, by = self._mouth_local_pos()
                    bx += random.uniform(-4.0, 4.0)
                    by += random.uniform(-4.0, 2.0)
                else:
                    bx, by = self._tail_tip_local_pos()
                    bx += random.uniform(-5.0, 5.0)
                    by += random.uniform(-6.0, 4.0)
            else:
                bx, by = cx, cy
            self.particles.append(Particle(
                kind="bubble",
                x=bx,
                y=by,
                vx=-self.vx * 0.14 + random.uniform(-0.28, 0.28),
                vy=random.uniform(-1.35, -0.70),
                life=62, max_life=62,
                size=random.uniform(4.8, 9.8),
                color=QColor(220, 248, 255, 170),
            ))
        elif kind == "trail_bubble":
            tx, ty = self._tail_tip_local_pos()
            self.particles.append(Particle(
                kind="trail_bubble",
                x=tx + random.uniform(-6, 6),
                y=ty + random.uniform(-6, 6),
                vx=-self.vx * 0.16 + random.uniform(-0.35, 0.35),
                vy=-self.vy * 0.16 + random.uniform(-0.6, -0.15),
                life=34, max_life=34,
                size=random.uniform(4.5, 8.5),
                color=QColor(225, 250, 255, 185),
            ))
        elif kind == "rainbow_bubble":
            mx, my = self._mouth_local_pos()
            self.particles.append(Particle(
                kind="rainbow_bubble",
                x=mx + random.uniform(-5, 5),
                y=my + random.uniform(-4, 4),
                vx=self.direction * random.uniform(1.6, 3.8) + random.uniform(-0.5, 0.5),
                vy=random.uniform(-2.0, 0.6),
                life=56, max_life=56,
                size=random.uniform(7.5, 14.0),
                color=random.choice(RAINBOW_COLORS),
            ))
        elif kind == "water_drop":
            mx, my = self._mouth_local_pos()
            self.particles.append(Particle(
                kind="water_drop",
                x=mx if x is None else x,
                y=my if y is None else y,
                vx=self.direction * random.uniform(3.2, 6.2),
                vy=random.uniform(-2.6, 1.4),
                life=30, max_life=30,
                size=random.uniform(7.0, 10.5),
                color=QColor("#72efdd"),
            ))
        elif kind == "boil":
            self.particles.append(Particle(
                kind="boil",
                x=cx + random.uniform(-52, 52),
                y=cy + random.uniform(10, 48),
                vx=random.uniform(-0.6, 0.6),
                vy=random.uniform(-3.6, -1.9),
                life=34, max_life=34,
                size=random.uniform(6.0, 14.0),
                color=QColor(255, 232, 214, 175),
            ))
        elif kind == "puff_air":
            ang = math.atan2(-self.vy, -self.vx) + random.uniform(-0.35, 0.35)
            spd = random.uniform(2.5, 4.8)
            self.particles.append(Particle(
                kind="puff_air",
                x=cx + math.cos(ang) * 18,
                y=cy + math.sin(ang) * 18,
                vx=math.cos(ang) * spd,
                vy=math.sin(ang) * spd,
                life=24, max_life=24,
                size=random.uniform(6.0, 11.0),
                color=QColor(235, 250, 255, 200),
            ))
        elif kind == "heart":
            self.particles.append(Particle(
                kind="heart",
                x=cx + random.uniform(-26, 26),
                y=cy - 24 + random.uniform(-8, 8),
                vx=random.uniform(-0.4, 0.4),
                vy=random.uniform(-1.3, -0.7),
                life=55, max_life=55,
                size=random.uniform(8, 12),
                color=QColor("#ff4d6d"),
            ))
        elif kind == "ghost":
            self.particles.append(Particle(
                kind="ghost",
                x=cx + random.uniform(-14, 14),
                y=cy - 26,
                vx=random.uniform(-0.18, 0.18),
                vy=random.uniform(-0.85, -0.50),
                life=78, max_life=78,
                size=random.uniform(13.0, 17.0),
                color=QColor(225, 244, 255, 195),
            ))
        elif kind == "zzz":
            self.particles.append(Particle(
                kind="zzz",
                x=cx + 28 * (-self.direction),
                y=cy - 34,
                vx=0.25 * (-self.direction),
                vy=-0.55,
                life=75, max_life=75,
                size=random.uniform(11, 15),
                color=QColor("#4361ee"),
            ))
        elif kind == "star":
            self.particles.append(Particle(
                kind="star",
                x=cx + random.uniform(-32, 32),
                y=cy - 18 + random.uniform(-16, 12),
                vx=random.uniform(-1.4, 1.4),
                vy=random.uniform(-1.8, -0.5),
                life=42, max_life=42,
                size=random.uniform(7, 11),
                color=QColor("#ffd166"),
            ))
        elif kind == "excl":
            self.particles.append(Particle(
                kind="excl",
                x=cx + 26 * self.direction,
                y=cy - 38,
                vx=0.0, vy=-0.45,
                life=42, max_life=42,
                size=16, color=QColor("#ff595e"),
            ))
        elif kind == "anger":
            self.particles.append(Particle(
                kind="anger",
                x=cx + 32 * (-self.direction),
                y=cy - 34,
                vx=0.0, vy=-0.12,
                life=55, max_life=55,
                size=15, color=QColor("#e63946"),
            ))
        elif kind == "sweat":
            self.particles.append(Particle(
                kind="sweat",
                x=cx - 30 * self.direction,
                y=cy - 18,
                vx=0.0, vy=0.35,
                life=45, max_life=45,
                size=9, color=QColor("#4cc9f0"),
            ))
        elif kind == "crumb":
            mx, my = self._mouth_local_pos()
            self.particles.append(Particle(
                kind="crumb",
                x=mx + random.uniform(-6, 6),
                y=my + random.uniform(-4, 4),
                vx=self.direction * random.uniform(1.0, 2.8) + random.uniform(-0.8, 0.8),
                vy=random.uniform(-2.6, -0.6),
                life=32, max_life=32,
                size=random.uniform(5.0, 8.5),
                color=random.choice([QColor("#ffffff"), QColor("#dce6f2"), QColor("#ffca3a")]),
            ))
        elif kind == "spark":
            ang = random.uniform(0.0, math.tau)
            spd = random.uniform(2.8, 6.4)
            self.particles.append(Particle(
                kind="spark",
                x=cx + random.uniform(-4, 4),
                y=cy + random.uniform(-4, 4),
                vx=math.cos(ang) * spd,
                vy=math.sin(ang) * spd - 1.2,
                life=20, max_life=20,
                size=random.uniform(7.5, 13.5),
                color=random.choice([QColor("#fff3a3"), QColor("#ffbe0b"), QColor("#ff6b35")]),
            ))
        elif kind == "smoke":
            self.particles.append(Particle(
                kind="smoke",
                x=cx + random.uniform(-14, 14),
                y=cy + random.uniform(-10, 10),
                vx=random.uniform(-1.3, 1.3),
                vy=random.uniform(-1.6, -0.4),
                life=32, max_life=32,
                size=random.uniform(6.5, 12.0),
                color=random.choice([QColor(215, 222, 230, 175), QColor(185, 195, 206, 165)]),
            ))
        elif kind == "tear":
            self.particles.append(Particle(
                kind="tear",
                x=cx + random.choice([-14.0, 14.0]) + random.uniform(-2, 2),
                y=cy + 6.0,
                vx=random.uniform(-0.4, 0.4),
                vy=random.uniform(0.6, 1.4),
                life=32, max_life=32,
                size=random.uniform(6.0, 8.2),
                color=QColor("#9ce8ff"),
            ))

    # ---------- Cảm biến định kỳ ----------
    def _poll_slow_sensors(self):
        if self.boss_hidden:
            return
        self.cpu_percent, self.ram_percent = self.pressure.sample()
        was_overloaded = self.is_overloaded
        self.is_overloaded = (
            self.simulate_overload
            or self.cpu_percent >= CPU_PANIC_THRESHOLD
            or self.ram_percent >= CPU_PANIC_THRESHOLD
        )
        if self.is_overloaded and not was_overloaded:
            if self.state == "play_dead":
                self._wake_from_play_dead()
            self.spawn_particle("excl")

        self.is_night_mode = self.simulate_late_night or is_late_night()
        if self.window_perch_enabled:
            self.tracked_windows = self.window_tracker.sample_tracked()
            self.open_windows = [tw.rect for tw in self.tracked_windows]

    def _poll_wallpaper(self):
        if not self.wallpaper_aware or self.boss_hidden:
            return
        my_rect = QRect(int(self.px), int(self.py), SIZE, SIZE)
        self.wallpaper.sample(exclude_rect=my_rect)

    # ---------- Hành động & Vi biểu cảm ----------
    def trigger_pufferfish(self):
        if self.state in ("caged", "breaking_out"):
            return
        if self.state == "play_dead":
            self._wake_from_play_dead()
        self.state = "puffed"
        self.puff_ticks = 3 * FPS
        self.facing_front = True
        self.vx *= 0.2
        self.vy *= 0.2
        self.spawn_particle("anger")
        for _ in range(4):
            self.spawn_particle("bubble")

    def trigger_nauseous_rainbow(self):
        """Post-Dizzy: mặt tái xanh -> nôn bong bóng cầu vồng -> nằm ngửa bụng 3s."""
        if self.state in ("caged", "breaking_out"):
            return
        if self.state == "play_dead":
            self._wake_from_play_dead()
        self.state = "nauseous_vomit"
        self.nauseous_ticks = int(1.8 * FPS)
        self.facing_front = False
        self.spin_vel = 0.0
        self.spin_deg = 0.0
        self.vx *= 0.25
        self.vy *= 0.25
        self.impulse_squash(1.20, 0.84)
        self.sound.play_pop()

    def trigger_sneeze(self):
        """Hắt xì ngẫu nhiên: nhăn mặt lấy hơi -> giật lùi + bắn bọt nước."""
        if self.state in ("drag", "puffed", "deflate_zoom", "dive_hide", "hidden", "swallow_ready", "swallow_gulp", "caged", "breaking_out"):
            return
        if self.state == "play_dead":
            self._wake_from_play_dead()
        self.state = "sneeze_windup"
        self.sneeze_ticks = 38
        self.facing_front = False
        self.vx *= 0.15
        self.vy *= 0.15

    def trigger_celebrate_figure8(self):
        """Tự hào / Khoe chiến lợi phẩm: cười ^‿^ bơi hình số 8 (∞)."""
        if self.state in ("drag", "dive_hide", "hidden", "puffed", "caged", "breaking_out"):
            return
        self.state = "celebrate_fig8"
        self.fig8_total = int(3.0 * FPS)
        self.fig8_ticks = self.fig8_total
        self.fig8_origin = (self.px, self.py)
        self.facing_front = False
        for _ in range(5):
            self.spawn_particle("star")

    def _surf_target_py(self, win_top: float) -> float:
        """Tính tọa độ Y của cửa sổ Pet sao cho bụng cá chìm ~10px dưới đường viền cửa sổ."""
        depth_scale = (0.85 + 0.25 * max(0.0, min(1.0, self.depth))) * max(0.15, self.dive_scale)
        bounds = self.virtual_rect()
        raw_y = win_top - (SIZE / 2.0 + 4.0 + 20.0 * depth_scale)
        return max(bounds.top() - 42.0, min(bounds.bottom() - SIZE - 4.0, raw_y))

    def _spawn_surface_splash(self, win_top: float, play_sound: bool = True):
        """Sinh 4–6 giọt nước bắn tung tóe và một vòng gợn sóng dẹt ngay tại điểm xuyên qua window.top."""
        fcx = self.px + SIZE / 2.0
        self.splash_overlay.trigger_takeoff_at(fcx, win_top)
        if play_sound:
            self.sound.play_splash()
        local_wy = max(46.0, min(SIZE - 16.0, win_top - self.py))
        for side in (-1, 1):
            for _ in range(3):
                self.particles.append(Particle(
                    kind="water_drop",
                    x=SIZE / 2.0 + side * random.uniform(8.0, 22.0),
                    y=local_wy - random.uniform(0.0, 5.0),
                    vx=side * random.uniform(1.8, 4.4),
                    vy=random.uniform(-4.8, -2.1),
                    life=28,
                    max_life=28,
                    size=random.uniform(5.2, 8.6),
                    color=QColor("#9bf6ff"),
                ))

    def _launch_porpoise_arc(self, win: QRect):
        """Phóng cá lên theo cung parabol kiểu cá heo nhảy sóng, luôn đồng bộ hướng mặt với dấu vx."""
        fcx = self.px + SIZE / 2.0
        safe_min_x = self._perch_safe_min
        safe_max_x = self._perch_safe_max
        # Nếu gần sát biên vùng an toàn (< 115px), quay đầu mượt qua Front View về hướng ngược lại
        rem = (safe_max_x - fcx) if self._perch_dir > 0 else (fcx - safe_min_x)
        if rem < 115.0:
            self._perch_dir *= -1

        bounds = self.virtual_rect()
        headroom = float(win.top()) - bounds.top()
        # Điều chỉnh độ cao cung nhảy phù hợp khoảng trống phía trên cửa sổ (tránh đụng trần màn hình)
        vy_mag = random.uniform(5.6, 6.4) if headroom >= 78.0 else random.uniform(3.9, 4.7)
        safe_span = max(250.0, safe_max_x - safe_min_x)
        vx_mag = min(4.6, max(3.5, safe_span / 82.0))

        self.vx = self._perch_dir * vx_mag
        self.vy = -vy_mag
        # Đảm bảo tuyệt đối: hướng mặt đồng bộ với dấu vx (vx < 0 -> Trái -1, vx > 0 -> Phải +1)
        self._set_direction(1 if self.vx > 0 else -1)
        self._surf_phase = "arc"
        self._surf_landed = True
        self.facing_front = False
        self.impulse_squash(1.20, 0.82)
        self._spawn_surface_splash(float(win.top()), play_sound=True)

    def _start_window_leap(self, win_top: float, leap_dir: int):
        """Nhảy vọt qua mép cửa sổ (cá vượt vũ môn) + để lại vòng gợn sóng 0.5s tại điểm cất cánh."""
        self._clear_click_through()
        fcx = self.px + SIZE / 2.0
        self.splash_overlay.trigger_takeoff_at(fcx, win_top)
        self.sound.play_splash()
        self.state = "window_leap"
        self._window_leap_ticks = 34
        self._surf_landed = False
        self._surf_phase = "approach"
        self._surf_nip_phase = "none"
        self._surf_snap_cooldown = int(3.0 * FPS)
        self._perch_rect = None
        self._perch_wid = 0
        self.facing_front = False
        self.vx = leap_dir * 5.0
        self.vy = -6.8
        self._set_direction(1 if self.vx > 0 else -1)
        self.impulse_squash(0.74, 1.32)
        for _ in range(4):
            self.spawn_particle("star")

    def _start_window_drop(self):
        """Giật mình hụt chân rơi tự do một đoạn ngắn khi cửa sổ đang lướt bị đóng/thu nhỏ."""
        self._clear_click_through()
        self.state = "window_drop"
        self._window_drop_ticks = 36
        self._surf_landed = False
        self._surf_phase = "approach"
        self._surf_nip_phase = "none"
        self._surf_snap_cooldown = int(2.4 * FPS)
        self._perch_rect = None
        self._perch_wid = 0
        self.facing_front = False
        self.vx *= 0.4
        self.vy = 1.6
        self.impulse_squash(0.80, 1.26)
        self.spawn_particle("excl")
        self.set_expression("surprised", 42)

    def _enter_window_surf_on(
        self,
        tw: TrackedWindow,
        safe_min_x: float,
        safe_max_x: float,
        already_landed: bool = False,
    ):
        """Bắt đầu chuỗi Porpoising (2–4 nhịp nhảy vồng cung) mà không snap cứng tọa độ Y."""
        self._perch_wid = tw.wid
        self._perch_rect = tw.rect
        self._perch_safe_min = safe_min_x
        self._perch_safe_max = safe_max_x
        self.state = "window_surf"
        self._perch_ticks = random.randint(420, 640)
        self.facing_front = False
        self.depth_target = 0.92
        self._surf_landed = False
        self._surf_dip = 0.0
        self._surf_dip_vel = 0.0
        self._surf_balance_deg = 0.0
        self._surf_drag_ticks = 0
        self._surf_elapsed = 0
        self._surf_nip_phase = "none"
        self._surf_nip_ticks = 0
        self._surf_nip_cd = 0
        self._porpoise_arcs_left = random.randint(2, 4)
        self._porpoise_dip_ticks = 0
        self._porpoise_dive_ticks = 0

        fcx = self.px + SIZE / 2.0
        mid_safe = (safe_min_x + safe_max_x) * 0.5
        # Chọn hướng nhảy vào phía còn rộng hơn trong vùng an toàn để đủ chỗ cho 2–4 cung parabol
        if safe_min_x + 30.0 <= fcx <= safe_max_x - 30.0:
            self._perch_dir = 1 if fcx <= mid_safe else -1
            start_x = fcx
        elif fcx < safe_min_x + 30.0:
            self._perch_dir = 1
            start_x = safe_min_x + 36.0
        else:
            self._perch_dir = -1
            start_x = safe_max_x - 36.0

        self.target_x = start_x - SIZE / 2.0
        self.target_y = self._surf_target_py(float(tw.rect.top()))

        if already_landed:
            # Nếu cá đã đang ngay tại mặt nước trong vùng an toàn -> ngoi bật lên cung nhảy đầu tiên luôn!
            self._launch_porpoise_arc(tw.rect)
        else:
            # Giai đoạn 1: Lái mượt tiếp cận mặt nước, không snap cứng tọa độ Y
            self._surf_phase = "approach"
            if abs(self.vx) > 0.2:
                self._set_direction(1 if self.vx > 0 else -1)

    def _update_surf_click_through(self, cur: QPoint):
        """Xuyên chuột vùng rìa xung quanh khi cá đang tương tác trên thanh tiêu đề để không chặn click tab/nút."""
        active = self.state == "window_surf" and self._surf_phase in ("arc", "dip")
        if not active:
            self._clear_click_through()
            return
        fcx, fcy = self.center_global()
        dist = math.hypot(cur.x() - fcx, cur.y() - fcy)
        below_water = self._perch_rect is not None and cur.y() > (self._perch_rect.top() + 8)
        want_pass = (dist > 46.0) or below_water
        if sys.platform in ("darwin", "win32"):
            if want_pass != self._click_through_active:
                if set_window_click_through(self, want_pass):
                    self._click_through_active = want_pass
        else:
            # Fallback cho Linux X11: mặt nạ elip ôm sát thân cá
            if not self._linux_mask_active:
                self.setMask(QRegion(SIZE // 2 - 52, SIZE // 2 - 44, 104, 82, QRegion.RegionType.Ellipse))
                self._linux_mask_active = True

    def _clear_click_through(self):
        if self._click_through_active:
            set_window_click_through(self, False)
            self._click_through_active = False
        if self._linux_mask_active:
            self.clearMask()
            self._linux_mask_active = False

    def trigger_window_perch(self, mode: str | None = None) -> bool:
        """Đậu/lướt mặt nước trên mép trên cửa sổ ứng dụng đủ rộng (vùng an toàn >= 250px)."""
        if self.state in ("caged", "breaking_out"):
            return False
        if not self.tracked_windows:
            self.tracked_windows = self.window_tracker.sample_tracked()
            self.open_windows = [tw.rect for tw in self.tracked_windows]
        # Lọc các cửa sổ đủ rộng (safe_max_x - safe_min_x >= 2.5 * fish_w ≈ 250px)
        eligible: list[tuple[TrackedWindow, float, float]] = []
        for tw in self.tracked_windows[: min(6, len(self.tracked_windows))]:
            zone = _window_safe_zone(tw.rect)
            if zone is not None:
                eligible.append((tw, zone[0], zone[1]))
        if not eligible:
            return False

        tw, safe_min_x, safe_max_x = random.choice(eligible)
        win = tw.rect
        bounds = self.virtual_rect()
        has_peek_headroom = win.top() >= bounds.top() + 36
        if mode is not None:
            chosen = mode
        elif has_peek_headroom:
            # Ưu tiên mạnh chế độ bơi lướt dọc mặt nước cửa sổ (80% surf / 20% peek)
            chosen = "window_surf" if random.random() < 0.80 else "window_peek"
        else:
            chosen = "window_surf"

        if chosen == "window_surf":
            self._enter_window_surf_on(tw, safe_min_x, safe_max_x, already_landed=False)
            return True

        self._perch_wid = tw.wid
        self._perch_rect = win
        self._perch_safe_min = safe_min_x
        self._perch_safe_max = safe_max_x
        self.state = "window_peek"
        self._perch_ticks = random.randint(220, 340)
        self._perch_dir = random.choice([-1, 1])
        self.facing_front = False
        self.depth_target = 0.92
        tx = random.uniform(safe_min_x + 20.0, max(safe_min_x + 24.0, safe_max_x - 20.0))
        self.target_x = tx - SIZE / 2.0
        self.target_y = win.top() - SIZE / 2.0 - 19.0
        return True

    def trigger_backflip(self):
        if self.state in ("puffed", "play_dead", "drag", "dive_hide", "hidden", "caged", "breaking_out"):
            return
        if self.backflip_remaining <= 10.0:
            self.backflip_remaining = 360.0
            self.impulse_squash(0.84, 1.20)
            for _ in range(3):
                self.spawn_particle("star")

    def enter_play_dead(self):
        """Chuyển sang trạng thái Giả chết: lật ngửa bụng nổi lềnh bềnh lên sát đỉnh màn hình!"""
        if self.state in ("caged", "breaking_out"):
            return
        self.state = "play_dead"
        self.facing_front = False
        self.puff_factor = 0.0
        self.spin_deg = 0.0
        self.spin_vel = 0.0
        self.bank_deg = 0.0
        self.vx *= 0.25
        self.vy = -0.9
        screen = QGuiApplication.primaryScreen().availableGeometry()
        # Nổi bụng từ từ lên mặt nước phía trên màn hình gần vị trí hiện tại
        float_x = max(screen.left() + 26.0, min(screen.right() - SIZE - 26.0, self.px))
        float_y = float(screen.top() + 26)
        self.target_x = float_x
        self.target_y = float_y
        self._dead_peek_cd = random.randint(5 * FPS, 9 * FPS)
        self._dead_peek_ticks = 0
        self.sound.play_pop()
        self.spawn_particle("ghost")
        for _ in range(3):
            self.spawn_particle("bubble")

    def _wake_from_play_dead(self):
        """Hồi sinh / giật mình lật người lại khi bị người dùng phát hiện giả chết!"""
        if self.state == "play_dead":
            self.state = "swim"
            self._dead_peek_ticks = 0
            self.sound.play_pop()
            self.impulse_squash(0.78, 1.26)
            self.spawn_particle("excl")
            for _ in range(4):
                self.spawn_particle("star")
            for _ in range(5):
                self.spawn_particle("bubble")
            self.set_expression("shy", 95)
        self._last_user_activity = time.monotonic()

    # ---------- Chế độ Lồng Giam (Cage Mode - Ctrl+Esc) ----------
    def toggle_cage_mode(self):
        """Chuyển đổi giữa Bơi tự do (FREE_SWIM) -> Bị giam (CAGED) -> Hóa lực sĩ phá lồng (BREAKING_OUT)."""
        if self.boss_hidden or self.state in ("dive_hide", "hidden", "surface_show", "breaking_out"):
            return
        if self.state == "caged":
            self.start_cage_breakout()
        else:
            self.enter_cage_mode()

    def enter_cage_mode(self):
        """Khởi tạo lồng sắt tại vị trí hiện tại của cá với hiệu ứng rơi nhẹ khóa 'cạch'."""
        self._last_user_activity = time.monotonic()
        self._clear_click_through()
        self.falling_cage_overlay.stop()
        self.state = "caged"
        # Vô hiệu hóa toàn bộ vector vận tốc bơi tự do & đưa cá vào tâm lồng
        self.vx = 0.0
        self.vy = 0.0
        self.pitch_deg = 0.0
        self.bank_deg = 0.0
        self.spin_deg = 0.0
        self.spin_vel = 0.0
        self.backflip_remaining = 0.0
        self.puff_factor = 0.0
        self.vortex_alpha = 0.0
        self.suction_alpha = 0.0
        self.mouth_locked = False
        self.eating_file_progress = -1.0
        self._eating_food = None
        self._perch_rect = None
        self._press_global = None
        self._drag_offset = None
        self._last_drag_global = None

        self.direction = -1
        self.facing_front = True
        self.depth_target = 0.60
        self.expression = "normal"
        self.expression_ticks = 0

        # Giữ lồng nằm gọn trong màn hình hiện tại
        bounds = self.virtual_rect()
        self.px = max(bounds.left() + 4.0, min(bounds.right() - SIZE - 4.0, self.px))
        self.py = max(bounds.top() + 4.0, min(bounds.bottom() - SIZE - 4.0, self.py))

        self.cage_drop_total = 22
        self.cage_drop_ticks = self.cage_drop_total
        self.cage_lock_played = False
        self.cage_dragging = False
        self.cage_swing_deg = random.choice([-1.0, 1.0]) * 3.2
        self.cage_swing_vel = 0.0
        self.cage_plead_ticks = 0
        self.cage_plead_cooldown = random.randint(8 * FPS, 15 * FPS)
        self.cage_bend_amount = 0.0
        self.cage_muscular = 0.0
        self.cage_break_sound_played = False
        self.cage_break_released = False
        self.move(int(self.px), int(self.py))
        self.raise_()
        self.update()

    def start_cage_breakout(self):
        """Chuyển sang trạng thái BREAKING_OUT (~1.5s): hóa lực sĩ bẻ cong 2 thanh sắt giữa lồng."""
        if self.state != "caged":
            return
        self._last_user_activity = time.monotonic()
        self.state = "breaking_out"
        self.cage_dragging = False
        self._press_global = None
        self._drag_offset = None
        self._last_drag_global = None
        self.cage_plead_ticks = 0
        self.cage_drop_ticks = 0
        self.cage_break_total = int(1.5 * FPS)
        self.cage_break_ticks = self.cage_break_total
        self.cage_bend_amount = 0.0
        self.cage_muscular = 0.0
        self.cage_break_sound_played = False
        self.cage_break_released = False
        self.vx = 0.0
        self.vy = 0.0
        self.facing_front = True
        self.impulse_squash(1.16, 0.88)
        self.spawn_particle("anger")

    # ---------- Boss Key: Lặn sâu ẩn mình (Ctrl+Shift+H) ----------
    def toggle_boss_hide(self):
        if self.state == "dive_hide" or self.state == "surface_show":
            return
        if not self.boss_hidden:
            # Lặn tòm xuống đáy màn hình biến mất
            self._clear_click_through()
            self.boss_hidden = True
            self._saved_surface_y = self.py
            self.state = "dive_hide"
            self.cage_dragging = False
            self.cage_plead_ticks = 0
            self.cage_bend_amount = 0.0
            self.cage_muscular = 0.0
            self.falling_cage_overlay.stop()
            self.facing_front = False
            self.puff_factor = 0.0
            self.vx = 0.0
            self.vy = 14.0
            self.spawn_particle("excl")
            self.impulse_squash(0.76, 1.32)
            # Ẩn các widget phụ ngay để màn hình sạch tuyệt đối
            if self.water_overlay.active:
                self.water_overlay.hide()
            for b in self.clipboard_bubbles:
                b.hide()
            for f in self.foods:
                f.hide()
            if self.pong_bubble is not None:
                self.pong_bubble.hide()
        else:
            # Ngoi lên lại kèm gợn sóng nước!
            self.boss_hidden = False
            bounds = self.virtual_rect()
            self.py = bounds.bottom() - SIZE / 2.0
            self.dive_scale = 0.30
            self.state = "surface_show"
            self.vy = -12.0
            self.vx = random.uniform(-1.5, 1.5)
            self.show()
            self.raise_()
            self.sound.play_splash()
            self.splash_overlay.trigger_at(self.px + SIZE / 2.0, bounds.bottom())
            for _ in range(8):
                self.spawn_particle("water_drop", SIZE / 2.0, SIZE / 2.0)
            if self.water_overlay.active:
                self.water_overlay.show()
            for b in self.clipboard_bubbles:
                if b.alive:
                    b.show()
            for f in self.foods:
                f.show()
            if self.pong_bubble is not None and self.pong_bubble.alive:
                self.pong_bubble.show()

    # ---------- Cho ăn: Mưa cám cá & Ký tự / Từ khóa ----------
    def spawn_food_shower(self, count: int = 5):
        if self.boss_hidden:
            self.toggle_boss_hide()
        if self.state == "play_dead":
            self._wake_from_play_dead()
        bounds = self.virtual_rect()
        top_y = int(bounds.top() + 18)
        if self.water_overlay.active and self.water_overlay.phase == "focus":
            top_y = int(max(top_y, self.water_overlay.surface_global_y() + 10))
        cx = self.px + SIZE / 2.0
        for i in range(count):
            fx = int(max(bounds.left() + 45, min(bounds.right() - 80, cx + random.randint(-300, 300))))
            fy = top_y + i * random.randint(12, 28)
            self.foods.append(FishFood(fx, fy, int(bounds.bottom())))
        self.set_expression("excited", 100)

    def spawn_word_food(self, words: list[str] | None = None):
        """Thả các ký tự / từ khóa / emoji rơi từ đỉnh màn hình để cá đuổi theo đớp."""
        if self.boss_hidden:
            self.toggle_boss_hide()
        if self.state == "play_dead":
            self._wake_from_play_dead()
        tokens = words if words else random.sample(DEFAULT_WORD_TOKENS, k=6)
        bounds = self.virtual_rect()
        top_y = int(bounds.top() + 16)
        if self.water_overlay.active and self.water_overlay.phase == "focus":
            top_y = int(max(top_y, self.water_overlay.surface_global_y() + 10))
        cx = self.px + SIZE / 2.0
        for i, tok in enumerate(tokens[:10]):
            fx = int(max(bounds.left() + 50, min(bounds.right() - 110, cx + random.randint(-320, 320))))
            fy = top_y + i * random.randint(18, 36)
            self.foods.append(FishFood(fx, fy, int(bounds.bottom()), word=tok))
        self.set_expression("excited", 110)

    def prompt_custom_word_food(self):
        text, ok = QInputDialog.getText(
            self,
            "Cho Cá Vàng ăn chữ",
            "Nhập các từ khóa / ký tự cách nhau bằng dấu cách:",
            text="Python BUG ✨ 2026 OK",
        )
        if ok and text.strip():
            words = [w for w in text.strip().split() if w][:10]
            if words:
                self.spawn_word_food(words)

    def _on_ate_morsel(self):
        self.fullness = min(10.0, self.fullness + 1.0)
        if self.fullness >= 4.0:
            # Ăn đủ no -> béo tròn dễ thương trong 2 phút!
            self._chubby_ticks = 120 * FPS
        self.impulse_squash(1.20, 0.85)
        self.sound.play_pop()
        for _ in range(4):
            self.spawn_particle("bubble")

    # ---------- Trò chơi Bóng bàn Bong Bóng (Bubble Pong) ----------
    def toggle_bubble_pong(self):
        if self.pong_bubble is not None and self.pong_bubble.alive:
            self.pong_bubble.close_with_pop()
            self.pong_bubble = None
            return
        if self.boss_hidden:
            self.toggle_boss_hide()
        if self.state == "play_dead":
            self._wake_from_play_dead()
        cx, cy = self.center_global()
        bounds = self.virtual_rect()
        bx = max(bounds.left() + 50, min(bounds.right() - 110, cx + self.direction * 95))
        by = max(bounds.top() + 50, min(bounds.bottom() - 110, cy - 30))
        self.pong_bubble = PongBubble(bx, by, self._on_pong_player_hit, self._on_pong_closed)
        self.set_expression("excited", 90)
        self.sound.play_pop()

    def _on_pong_player_hit(self, bubble: PongBubble, global_click: QPoint):
        fcx, fcy = self.center_global()
        bcx, bcy = bubble.center()
        # Hất bong bóng bay chéo về phía xa để cá lao đi đón!
        dx = fcx - bcx + random.uniform(-160, 160)
        dy = fcy - bcy + random.uniform(-120, 120)
        dist = max(1.0, math.hypot(dx, dy))
        spd = 11.0
        bubble.launch((dx / dist) * spd, (dy / dist) * spd, hitter="player")
        self.sound.play_pop()
        if self.state == "play_dead":
            self._wake_from_play_dead()
        if self.state not in ("drag", "puffed", "deflate_zoom", "caged", "breaking_out"):
            self.state = "swim"
        self.set_expression("excited", 80)

    def _on_pong_closed(self, bubble: PongBubble):
        if self.pong_bubble is bubble:
            self.pong_bubble = None

    def start_pomodoro(self, focus_secs: int, break_secs: int):
        if self.boss_hidden:
            self.toggle_boss_hide()
        if self.state == "play_dead":
            self._wake_from_play_dead()
        self.water_overlay.start_pomodoro(focus_secs, break_secs)
        self.set_expression("excited", 80)

    def stop_pomodoro(self):
        self.water_overlay.stop_pomodoro()

    def set_theme(self, name: str):
        self.theme_name = name
        self.theme = FISH_THEMES[name]
        self.set_expression("happy", 70)
        for _ in range(4):
            self.spawn_particle("star")
        self.update()

    # ---------- Bong bóng Clipboard ----------
    def _on_clipboard_changed(self):
        if not self.clipboard_bubbles_enabled or self.boss_hidden:
            return
        if time.monotonic() < self._ignore_clipboard_until:
            return

        cb = QApplication.clipboard()
        md = cb.mimeData()
        if md is None:
            return

        kind = ""
        payload = None
        sig = ""
        if md.hasImage():
            img = cb.image()
            if not img.isNull():
                kind = "image"
                payload = img
                sig = f"img:{img.width()}x{img.height()}:{img.sizeInBytes()}"
        elif md.hasText():
            txt = md.text().strip()
            if txt:
                kind = "url" if URL_RE.match(txt) else "text"
                payload = txt
                sig = f"{kind}:{txt[:120]}"

        if not kind or payload is None or sig == self._last_clip_sig:
            return
        self._last_clip_sig = sig

        cx, cy = self.center_global()
        bx = cx + self.direction * 36 - ClipboardBubble.BUBBLE_SIZE / 2
        by = cy - 28
        bubble = ClipboardBubble(
            kind=kind,
            payload=payload,
            start_x=bx,
            start_y=by,
            on_activate=self._on_bubble_activate,
            on_closed=self._on_bubble_closed,
        )
        self.clipboard_bubbles.append(bubble)

        while len(self.clipboard_bubbles) > MAX_CLIPBOARD_BUBBLES:
            oldest = self.clipboard_bubbles.pop(0)
            oldest.trigger_pop(activate=False)

        self.impulse_squash(1.14, 0.88)
        self.spawn_particle("bubble")
        if self.state == "swim":
            self.set_expression("happy", 55)

    def _on_bubble_activate(self, bubble: ClipboardBubble):
        self.sound.play_pop()
        self._ignore_clipboard_until = time.monotonic() + 0.6
        paste_or_open_clipboard_payload(bubble.kind, bubble.payload)
        # Tự hào ăn mừng hình số 8 sau khi giúp mở/dán bong bóng!
        self.trigger_celebrate_figure8()

    def _on_bubble_closed(self, bubble: ClipboardBubble):
        if bubble in self.clipboard_bubbles:
            self.clipboard_bubbles.remove(bubble)

    def clear_clipboard_bubbles(self):
        for b in list(self.clipboard_bubbles):
            b.trigger_pop(activate=False)

    # ---------- Kéo file từ folder vào miệng cá để ăn & xóa ----------
    @staticmethod
    def _accept_drag_action(e):
        if e.possibleActions() & Qt.DropAction.CopyAction:
            e.setDropAction(Qt.DropAction.CopyAction)
            e.accept()
        else:
            e.acceptProposedAction()

    @staticmethod
    def _has_droppable_data(md) -> bool:
        if md is None:
            return False
        return (
            md.hasUrls()
            or md.hasFormat("text/uri-list")
            or md.hasFormat("x-special/gnome-copied-files")
            or md.hasText()
        )

    @staticmethod
    def _parse_uri_to_local_path(raw: str) -> str | None:
        s = raw.strip().strip("\x00")
        if not s or s.startswith("#"):
            return None
        if s.lower().startswith("file://"):
            url = QUrl(s)
            path = url.toLocalFile()
            if not path:
                path = unquote(s[7:])
            return path or None
        if os.path.isabs(s) and os.path.lexists(s):
            return s
        return None

    @classmethod
    def _extract_dropped_paths(cls, md) -> list[str]:
        paths: list[str] = []
        seen: set[str] = set()

        def add_path(p: str | None):
            if p and os.path.lexists(p):
                norm = os.path.abspath(p)
                if norm not in seen:
                    seen.add(norm)
                    paths.append(norm)

        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile():
                    add_path(url.toLocalFile())
                else:
                    add_path(cls._parse_uri_to_local_path(url.toString()))

        for fmt in ("text/uri-list", "x-special/gnome-copied-files"):
            if md.hasFormat(fmt):
                raw_bytes = bytes(md.data(fmt))
                text = raw_bytes.decode("utf-8", errors="ignore")
                lines = text.splitlines()
                if fmt == "x-special/gnome-copied-files" and lines and lines[0].strip() in ("copy", "cut"):
                    lines = lines[1:]
                for line in lines:
                    add_path(cls._parse_uri_to_local_path(line))

        if not paths and md.hasText():
            for line in md.text().splitlines():
                add_path(cls._parse_uri_to_local_path(line))

        return paths

    def _aim_mouth_at(self, local_pos: QPoint):
        self.facing_front = False
        dx = local_pos.x() - SIZE / 2.0
        dy = local_pos.y() - (SIZE / 2.0 + 4.0)
        if abs(dx) > 6.0:
            self.direction = 1 if dx > 0 else -1
        self.pitch_deg = max(-24.0, min(24.0, (dy / 70.0) * 20.0 * self.direction))
        mx, my = self._mouth_local_pos()
        self.mouth_locked = math.hypot(local_pos.x() - mx, local_pos.y() - my) <= 68.0

    def dragEnterEvent(self, e):
        if self.state in ("caged", "breaking_out"):
            e.ignore()
            return
        md = e.mimeData()
        if self._has_droppable_data(md):
            self._accept_drag_action(e)
            self._last_user_activity = time.monotonic()
            self._drag_leave_grace = 0
            if self.state == "play_dead":
                self._wake_from_play_dead()
            self.state = "swallow_ready"
            self.vx = 0.0
            self.vy = 0.0
            self._aim_mouth_at(e.position().toPoint())
            self.suction_alpha = 1.0
            self.update()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._has_droppable_data(e.mimeData()):
            self._drag_leave_grace = 0
            self.state = "swallow_ready"
            self._aim_mouth_at(e.position().toPoint())
            self.suction_alpha = 1.0
            self._accept_drag_action(e)
            self.update()
        else:
            e.ignore()

    def dragLeaveEvent(self, _):
        if self.state == "swallow_ready":
            self._drag_leave_grace = 18
            self.mouth_locked = False

    def dropEvent(self, e):
        md = e.mimeData()
        drop_pos = e.position().toPoint()
        self._drag_leave_grace = 0
        self.mouth_locked = False

        paths = self._extract_dropped_paths(md)
        if paths:
            self._accept_drag_action(e)
            self._eat_paths(paths, (float(drop_pos.x()), float(drop_pos.y())))
            return

        if md.hasText() and md.text().strip():
            self._accept_drag_action(e)
            self._start_eat_animation((float(drop_pos.x()), float(drop_pos.y())), is_dir=False)
            return

        e.ignore()
        self.state = "swim"
        self.suction_alpha = 0.0

    def _eat_paths(self, paths: list[str], drop_pos: tuple[float, float]):
        if not paths:
            self.state = "swim"
            self.suction_alpha = 0.0
            return

        if self.delete_mode == "permanent":
            names = "\n".join(f"• {os.path.basename(p) or p}" for p in paths[:8])
            if len(paths) > 8:
                names += f"\n... và {len(paths) - 8} mục nữa"
            reply = QMessageBox.warning(
                self,
                "Xác nhận xóa vĩnh viễn",
                f"Cá Vàng sẽ ăn và XÓA VĨNH VIỄN (không vào Thùng rác):\n\n{names}\n\nBạn có chắc chắn không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.state = "swim"
                self.suction_alpha = 0.0
                return

        deleted: list[str] = []
        failed: list[str] = []
        first_is_dir = os.path.isdir(paths[0])

        for path in paths:
            ok = self._permanently_delete_path(path) if self.delete_mode == "permanent" else self._move_path_to_trash(path)
            if ok:
                deleted.append(path)
                action_label = "xóa vĩnh viễn" if self.delete_mode == "permanent" else "chuyển vào Thùng rác"
                print(f"[Cá Vàng] Đã ăn & {action_label}: {path}", flush=True)
            else:
                failed.append(path)

        if failed and self.delete_mode == "trash":
            names = "\n".join(f"• {os.path.basename(p) or p}" for p in failed[:6])
            reply = QMessageBox.question(
                self,
                "Không thể đưa vào Thùng rác",
                f"Không thể chuyển vào Thùng rác hệ thống:\n\n{names}\n\nBạn có muốn xóa vĩnh viễn ngay không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                for path in failed:
                    if self._permanently_delete_path(path):
                        deleted.append(path)
                        print(f"[Cá Vàng] Đã ăn & xóa vĩnh viễn: {path}", flush=True)

        if deleted:
            self._start_eat_animation(drop_pos, is_dir=first_is_dir)
        else:
            self.state = "swim"
            self.suction_alpha = 0.0
            self.set_expression("grumpy", 60)

    def _start_eat_animation(self, start_pos: tuple[float, float], is_dir: bool = False):
        self.state = "swallow_gulp"
        self.swallow_ticks = 24
        self.chew_ticks = 52
        self.suction_alpha = 1.0
        self.eating_file_progress = 0.0
        self.eating_file_start = start_pos
        self.eating_file_is_dir = is_dir
        self.impulse_squash(1.22, 0.84)
        self.sound.play_pop()
        for _ in range(5):
            self.spawn_particle("bubble")

    def pick_files_to_eat(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn file cho Cá Vàng ăn",
            os.path.expanduser("~"),
        )
        if files:
            mx, my = self._mouth_local_pos()
            start = (mx + self.direction * 46.0, my - 10.0)
            self._eat_paths(files, start)

    @staticmethod
    def _permanently_delete_path(path: str) -> bool:
        try:
            if os.path.islink(path) or os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            return not os.path.lexists(path)
        except Exception:
            return False

    @staticmethod
    def _move_path_to_trash(path: str) -> bool:
        try:
            if QFile.moveToTrash(path) and not os.path.lexists(path):
                return True
        except Exception:
            pass
        if sys.platform.startswith("linux") and shutil.which("gio"):
            try:
                res = subprocess.run(["gio", "trash", path], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0 and not os.path.lexists(path):
                    return True
            except Exception:
                pass
        if sys.platform.startswith("linux"):
            try:
                trash_root = os.path.expanduser("~/.local/share/Trash")
                files_dir = os.path.join(trash_root, "files")
                info_dir = os.path.join(trash_root, "info")
                os.makedirs(files_dir, exist_ok=True)
                os.makedirs(info_dir, exist_ok=True)

                base = os.path.basename(path.rstrip(os.sep)) or "item"
                dest_name = base
                idx = 1
                while os.path.lexists(os.path.join(files_dir, dest_name)):
                    stem, ext = os.path.splitext(base)
                    dest_name = f"{stem}_{idx}{ext}"
                    idx += 1

                dest_path = os.path.join(files_dir, dest_name)
                info_path = os.path.join(info_dir, f"{dest_name}.trashinfo")
                del_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                with open(info_path, "w", encoding="utf-8") as f:
                    f.write("[Trash Info]\n")
                    f.write(f"Path={quote(os.path.abspath(path), safe='/')}\n")
                    f.write(f"DeletionDate={del_date}\n")
                shutil.move(path, dest_path)
                return not os.path.lexists(path)
            except Exception:
                pass
        return False

    # ---------- Vòng lặp chính 60 FPS ----------
    def tick(self):
        if self.state == "hidden":
            return

        self.frame += 1
        dt = 1.0 / FPS
        now = time.monotonic()
        bounds = self.virtual_rect()

        # 1. Cập nhật Pomodoro Mực Nước
        if self.water_overlay.active and not self.boss_hidden:
            transition = self.water_overlay.step(dt)
            if transition == "enter_break":
                self.set_expression("happy", 140)
                for _ in range(8):
                    self.spawn_particle("bubble")
            elif transition == "enter_focus":
                self.set_expression("excited", 90)

        # 2. Cập nhật âm thanh (Equalizer + Bass Drop Backflip)
        self.audio_level, self.audio_bands, bass_drop = self.audio.poll()
        if bass_drop and not self.boss_hidden:
            self.trigger_backflip()

        # 3. Theo dõi con trỏ chuột (Cursor Wake + Idle timer)
        cur = QCursor.pos()
        cdx = cur.x() - self._last_cursor.x()
        cdy = cur.y() - self._last_cursor.y()
        cursor_speed = math.hypot(cdx, cdy)
        self._last_cursor = cur

        if cursor_speed > 2.5:
            self._last_user_activity = now
            if self.state == "play_dead":
                fcx, fcy = self.center_global()
                if math.hypot(cur.x() - fcx, cur.y() - fcy) < 62.0:
                    self._wake_from_play_dead()

        # Kiểm tra Idle > 5 phút -> tự vào bong bóng ngủ
        if (
            self.state == "swim"
            and not self.hold_still
            and not self.is_overloaded
            and not self.water_overlay.active
            and (now - self._last_user_activity) >= IDLE_SLEEP_SECS
        ):
            self.enter_play_dead()

        # Tương tác dòng chảy Cursor Wake + Post-Dizzy (3 lần xoáy trong 5s -> nôn cầu vồng -> ngửa bụng 3s)
        if self._wake_cooldown > 0:
            self._wake_cooldown -= 1
        if (
            self.state in ("swim", "window_surf", "window_peek")
            and not self.hold_still
            and self._drag_leave_grace == 0
            and self._wake_cooldown == 0
            and cursor_speed > 30.0
        ):
            fcx, fcy = self.center_global()
            if math.hypot(cur.x() - fcx, cur.y() - fcy) < 64.0:
                self._wake_cooldown = 44  # ~0.73s để người dùng có thể vung 3 lần trong 5s
                self._vortex_timestamps = [t for t in self._vortex_timestamps if (now - t) <= 5.0]
                self._vortex_timestamps.append(now)

                if len(self._vortex_timestamps) >= 3:
                    self._vortex_timestamps.clear()
                    self.trigger_nauseous_rainbow()
                else:
                    self.state = "swim"
                    self.vortex_alpha = 1.0
                    self.spin_vel = (22.0 if cdx >= 0 else -22.0)
                    self.vx += max(-7.0, min(7.0, cdx * 0.12))
                    self.vy += max(-7.0, min(7.0, cdy * 0.12))
                    self.impulse_squash(0.84, 1.18)
                    self.set_expression("dizzy", 105)
                    for _ in range(7):
                        self.spawn_particle("bubble")

        # Hắt xì ngẫu nhiên khi đang bơi bình thường
        if self.state == "swim" and not self.is_overloaded and not self.foods and not self.hold_still:
            self._sneeze_cd -= 1
            if self._sneeze_cd <= 0:
                self._sneeze_cd = random.randint(30 * FPS, 55 * FPS)
                self.trigger_sneeze()

        # 4. Cập nhật đồ ăn (cám cá & ký tự), Bubble Pong, và bong bóng Clipboard
        alive_foods: list[FishFood] = []
        for f in self.foods:
            if f is self._eating_food or f.step():
                alive_foods.append(f)
            else:
                f.close()
        self.foods = alive_foods

        if self.pong_bubble is not None and self.pong_bubble.alive:
            self.pong_bubble.step(bounds)
            # Con trỏ chuột làm vợt đỡ khi bong bóng bay ngược lại phía người chơi!
            if (
                self.pong_bubble.in_rally
                and self.pong_bubble.last_hitter == "fish"
                and self.pong_bubble.hit_cooldown == 0
                and cursor_speed > 7.0
            ):
                bcx, bcy = self.pong_bubble.center()
                if math.hypot(cur.x() - bcx, cur.y() - bcy) < 46.0:
                    self._on_pong_player_hit(self.pong_bubble, cur)

        for b in list(self.clipboard_bubbles):
            b.step(bounds)

        # 5. Độ béo tròn sau khi ăn no
        if self._chubby_ticks > 0:
            self._chubby_ticks -= 1
            target_chubby = min(1.0, (self.fullness - 3.0) / 5.0)
            self.chubby_factor += (target_chubby - self.chubby_factor) * 0.03
            if self._chubby_ticks == 0:
                self.fullness = 0.0
        else:
            self.chubby_factor = max(0.0, self.chubby_factor - 0.005)

        # 6. Cập nhật chuyển động & vật lý Tail-Beat Impulse
        self._step_movement(bounds, cur)

        # 6b. Cập nhật Lớp 1 (liếc con ngươi mượt 0.30) & đếm nhịp quay đầu (~150ms)
        self._update_cursor_eye_tracking(cur)
        if self._turn_ticks > 0:
            self._turn_ticks -= 1
        if self._surf_snap_cooldown > 0:
            self._surf_snap_cooldown -= 1
        self._update_surf_click_through(cur)

        # 7. Quán tính Banking & Lò xo Squash-Stretch theo tốc độ và góc cua
        spd_now = math.hypot(self.vx, self.vy)
        if spd_now > 0.6 and self.state in ("swim", "celebrate_fig8", "deflate_zoom", "window_surf"):
            heading = math.atan2(self.vy, self.vx)
            turn_rate = _angle_diff(self._prev_heading, heading)
            self._prev_heading = heading
            target_bank = max(-18.0, min(18.0, turn_rate * 48.0))
            self.bank_deg += (target_bank - self.bank_deg) * 0.16
            stretch = min(0.14, (spd_now / 8.0) * 0.10 + abs(turn_rate) * 0.22)
        else:
            self.bank_deg *= 0.86
            stretch = 0.0

        target_sx = 1.0 + stretch
        target_sy = 1.0 / (1.0 + stretch * 0.85)
        self._squash_vx = (self._squash_vx + (target_sx - self.squash_x) * 0.16) * 0.72
        self._squash_vy = (self._squash_vy + (target_sy - self.squash_y) * 0.16) * 0.72
        self.squash_x = max(0.62, min(1.45, self.squash_x + self._squash_vx))
        self.squash_y = max(0.62, min(1.45, self.squash_y + self._squash_vy))

        # Pha vẫy đuôi đồng bộ với tốc độ bơi
        self.tail_phase += 0.09 + min(1.0, spd_now / 5.5) * 0.24

        # Đuôi bong bóng động (Bubble Trail) khi bơi nhanh
        if spd_now > 3.5 and self.frame % 3 == 0 and self.state not in ("drag", "dive_hide"):
            self.spawn_particle("trail_bubble")

        # Hồi phục các hiệu ứng phụ
        self.vortex_alpha = max(0.0, self.vortex_alpha - 0.025)
        if self.state not in ("swallow_ready", "swallow_gulp"):
            self.suction_alpha = max(0.0, self.suction_alpha - 0.08)
            self.mouth_locked = False
            self.eating_file_progress = -1.0

        if self.expression_ticks > 0:
            self.expression_ticks -= 1
            if self.expression_ticks == 0:
                self.expression = "normal"

        if self.blink_frames > 0:
            self.blink_frames -= 1
        else:
            self.blink_timer -= 1
            if self.blink_timer <= 0:
                self.blink_frames = 7
                self.blink_timer = random.randint(150, 320)

        self.pet_rub_energy = max(0.0, self.pet_rub_energy - 0.7)
        if self.pet_rub_energy == 0.0 and self.frame % 35 == 0:
            self.pet_love_streak = max(0, self.pet_love_streak - 1)

        # Backflip & spin xoáy nước
        if self.backflip_remaining > 0.0:
            step_rot = min(self.backflip_remaining, 18.0)
            self.backflip_remaining -= step_rot
            self.spin_deg += step_rot * (-self.direction)
            if self.backflip_remaining <= 0.0:
                self.spin_deg = 0.0
        else:
            self.spin_deg += self.spin_vel
            self.spin_vel *= 0.92
            if abs(self.spin_vel) < 0.4:
                self.spin_vel = 0.0
                norm = ((self.spin_deg + 180.0) % 360.0) - 180.0
                self.spin_deg = norm * 0.85
                if abs(self.spin_deg) < 0.5:
                    self.spin_deg = 0.0

        self.depth += (self.depth_target - self.depth) * 0.016

        # Cập nhật hạt hiệu ứng
        self._update_particles()

        expr = self.active_expression()
        if expr == "play_dead" and self.frame % 68 == 0:
            self.spawn_particle("ghost")
        elif expr == "love" and self.frame % 16 == 0:
            self.spawn_particle("heart")
        elif expr == "proud" and self.frame % 14 == 0:
            self.spawn_particle("star")
        elif expr == "happy" and self.frame % 26 == 0:
            self.spawn_particle("bubble")
        elif self.is_overloaded and self.state not in ("caged", "breaking_out") and self.frame % 4 == 0:
            self.spawn_particle("boil")

        # Hệ thống hạt bong bóng động (sinh từ miệng/đuôi mỗi 1–2s, nhiều hơn khi bơi nhanh / bật nhạc / thở dài)
        if self.state not in ("dive_hide", "hidden"):
            self._bubble_cd -= 1
            if self._bubble_cd <= 0:
                if expr in ("sleepy", "caged_sad") and random.random() < 0.45:
                    # Thở dài: thổi 2–3 bong bóng nhỏ liên tiếp từ miệng
                    mx, my = self._mouth_local_pos()
                    for _ in range(random.randint(2, 3)):
                        self.spawn_particle("bubble", mx + random.uniform(-4, 4), my + random.uniform(-3, 3))
                else:
                    self.spawn_particle("bubble")
                # Sinh nhanh hơn khi bơi nhanh, mặc định mỗi 1–2 giây (60–120 frame)
                self._bubble_cd = random.randint(28, 52) if spd_now > 2.6 else random.randint(60, 120)

            # Bật nhạc -> sinh thêm bong bóng động nhịp nhàng theo biên độ âm thanh
            if self.audio_level > 0.06:
                self._music_bubble_cd -= 1
                if self._music_bubble_cd <= 0:
                    self.spawn_particle("bubble")
                    self._music_bubble_cd = max(7, int(24 - self.audio_level * 16))
            else:
                self._music_bubble_cd = 0

        if self.wallpaper_aware and self.frame % 15 == 0:
            fcx, fcy = self.center_global()
            self.current_color_score = self.wallpaper.score_at(fcx, fcy)

        self.move(int(self.px), int(self.py))
        self.update()

    def _update_particles(self):
        alive: list[Particle] = []
        for pt in self.particles:
            pt.x += pt.vx
            pt.y += pt.vy
            if pt.kind == "bubble":
                # Trôi ziczac nhẹ lên trên và tăng nhẹ sức nổi tự nhiên
                pt.x += math.sin(self.frame * 0.16 + pt.size * 1.9) * 0.45
                pt.vy = max(-1.85, pt.vy - 0.01)
                pt.vx *= 0.97
            elif pt.kind == "ghost":
                pt.x += math.sin(self.frame * 0.10 + pt.size) * 0.42
            elif pt.kind in ("boil", "trail_bubble", "rainbow_bubble"):
                pt.x += math.sin(self.frame * 0.14 + pt.size) * 0.35
            elif pt.kind in ("crumb", "water_drop"):
                pt.vy += 0.18
            elif pt.kind == "spark":
                pt.vx *= 0.96
                pt.vy += 0.14
            elif pt.kind == "smoke":
                pt.vx *= 0.94
                pt.vy = pt.vy * 0.95 - 0.03
            elif pt.kind == "tear":
                pt.vy += 0.14
            pt.life -= 1
            if pt.life > 0:
                alive.append(pt)
        self.particles = alive

    def _step_movement(self, bounds: QRectF, cur: QPoint):
        min_y = bounds.top() + 8.0
        if self.water_overlay.active and self.water_overlay.phase == "focus":
            min_y = max(min_y, self.water_overlay.surface_global_y() - 18.0)
        max_y = bounds.bottom() - SIZE - 4.0
        min_x = bounds.left() + 6.0
        max_x = bounds.right() - SIZE - 6.0

        # --- Chế độ Lồng Giam (CAGED) ---
        if self.state == "caged":
            self.vx = 0.0
            self.vy = 0.0
            self.pitch_deg = 0.0
            self.bank_deg = 0.0
            self.puff_factor *= 0.85
            self.facing_front = True
            self.depth_target = 0.60

            if self.cage_drop_ticks > 0:
                self.cage_drop_ticks -= 1
                if self.cage_drop_ticks == 6 and not self.cage_lock_played:
                    self.cage_lock_played = True
                    self.sound.play_cage_lock()
                    self.impulse_squash(1.18, 0.84)
                    for sx in (-28.0, 0.0, 28.0):
                        self.spawn_particle("smoke", SIZE / 2.0 + sx, SIZE / 2.0 + 52.0)
                    for _ in range(2):
                        self.spawn_particle("spark", SIZE / 2.0, SIZE / 2.0 - 54.0)
            elif not self.cage_dragging:
                if self.cage_plead_ticks > 0:
                    self.cage_plead_ticks -= 1
                    # Lắc nhẹ chiếc lồng qua lại ±3° quanh móc treo khi van xin
                    target_swing = math.sin(self.frame * 0.24) * 3.0
                    self.cage_swing_deg += (target_swing - self.cage_swing_deg) * 0.24
                    self.cage_swing_vel = 0.0
                    if self.frame % 36 == 0:
                        self.spawn_particle("tear")
                    if self.cage_plead_ticks == 0:
                        self.cage_plead_cooldown = random.randint(8 * FPS, 15 * FPS)
                else:
                    self.cage_plead_cooldown -= 1
                    self.cage_swing_vel = (self.cage_swing_vel - self.cage_swing_deg * 0.09) * 0.86
                    self.cage_swing_deg += self.cage_swing_vel
                    if abs(self.cage_swing_deg) < 0.03 and abs(self.cage_swing_vel) < 0.03:
                        self.cage_swing_deg = 0.0
                        self.cage_swing_vel = 0.0
                    if self.cage_plead_cooldown <= 0:
                        self.cage_plead_ticks = random.randint(int(3.2 * FPS), int(4.4 * FPS))
                        self.spawn_particle("tear")
            return

        # --- Hóa lực sĩ bẻ thanh sắt phá lồng (BREAKING_OUT ~1.5s) ---
        if self.state == "breaking_out":
            self.cage_break_ticks -= 1
            prog = 1.0 - (self.cage_break_ticks / max(1, self.cage_break_total))

            if prog < 0.36:
                # Nhịp 1: Gồng mình hóa lực sĩ, mặt đỏ quyết tâm, rung lắc mạnh
                self.vx = 0.0
                self.vy = 0.0
                self.facing_front = True
                self.cage_muscular = min(1.0, prog / 0.30)
                self.cage_swing_deg = math.sin(self.frame * 1.45) * (2.2 + 2.8 * prog)
                self.squash_x = 1.0 + 0.11 * self.cage_muscular
                self.squash_y = 1.0 + 0.07 * self.cage_muscular
                if self.frame % 6 == 0:
                    self.spawn_particle("smoke", SIZE / 2.0 + random.uniform(-22, 22), SIZE / 2.0 - 8.0)
            elif prog < 0.78:
                # Nhịp 2: Bẻ cong 2 thanh sắt ở giữa lồng sang hai bên + tia lửa/khói bụi + tiếng kim loại
                if not self.cage_break_sound_played:
                    self.cage_break_sound_played = True
                    self.sound.play_metal_bend()
                bp = (prog - 0.36) / 0.42
                self.cage_bend_amount = 1.0 - ((1.0 - bp) ** 2.3)
                self.cage_muscular = 1.0
                self.cage_swing_deg = math.sin(self.frame * 1.9) * (4.2 * (1.0 - bp * 0.35))
                grip_x = 17.5 + self.cage_bend_amount * 28.5
                if self.frame % 2 == 0:
                    self.spawn_particle("spark", SIZE / 2.0 - grip_x, SIZE / 2.0 + 11.0)
                    self.spawn_particle("spark", SIZE / 2.0 + grip_x, SIZE / 2.0 + 11.0)
                if self.frame % 4 == 0:
                    self.spawn_particle("smoke", SIZE / 2.0 + random.choice([-1, 1]) * grip_x, SIZE / 2.0 + 10.0)
            else:
                # Nhịp 3: Lồng vỡ rơi xuống đáy màn hình & mờ dần; cá bật nhảy ra ngoài đầy tự hào!
                if not self.cage_break_released:
                    self.cage_break_released = True
                    self.falling_cage_overlay.trigger_at(
                        self.px + SIZE / 2.0,
                        self.py + SIZE / 2.0 + 4.0,
                        self.cage_swing_deg,
                        self.cage_bend_amount,
                        bounds.bottom(),
                    )
                    self.sound.play_pop()
                    for _ in range(10):
                        self.spawn_particle("spark", SIZE / 2.0 + random.uniform(-35, 35), SIZE / 2.0 + random.uniform(-10, 20))
                    for _ in range(6):
                        self.spawn_particle("smoke", SIZE / 2.0 + random.uniform(-35, 35), SIZE / 2.0 + random.uniform(-10, 25))
                    for _ in range(7):
                        self.spawn_particle("star")
                    dir_out = random.choice([-1, 1])
                    self.direction = dir_out
                    self.facing_front = False
                    self.vx = dir_out * 4.4
                    self.vy = -5.4
                    self.impulse_squash(0.76, 1.28)
                self.vy += 0.22
                self.vx *= 0.97
                self.px += self.vx
                self.py += self.vy
                self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=True)
                self.pitch_deg = max(-28.0, min(28.0, self.vy * 4.2 * self.direction))
                if self.frame % 3 == 0:
                    self.spawn_particle("star")

            if self.cage_break_ticks <= 0:
                self.state = "swim"
                self.cage_bend_amount = 0.0
                self.cage_muscular = 0.0
                self.cage_swing_deg = 0.0
                self.cage_swing_vel = 0.0
                self.cage_break_released = False
                self.set_expression("proud", int(2.5 * FPS))
                self._pick_new_swim_target(min_y=min_y)
            return

        # --- Boss Key: Lặn sâu xuống đáy ẩn mình ---
        if self.state == "dive_hide":
            self.vy = min(22.0, self.vy + 1.1)
            self.py += self.vy
            self.pitch_deg = 52.0 * self.direction
            self.dive_scale = max(0.25, self.dive_scale - 0.032)
            if self.frame % 2 == 0:
                self.spawn_particle("trail_bubble")
            if self.py >= bounds.bottom() - SIZE * 0.35:
                self.sound.play_splash()
                self.splash_overlay.trigger_at(self.px + SIZE / 2.0, bounds.bottom())
                self.state = "hidden"
                self.hide()
            return

        # --- Boss Key: Ngoi lên mặt nước lại ---
        if self.state == "surface_show":
            self.vy *= 0.91
            self.py += self.vy
            self.px = max(min_x, min(max_x, self.px + self.vx))
            self.dive_scale = min(1.0, self.dive_scale + 0.045)
            self.pitch_deg = -32.0 * self.direction
            if self.frame % 2 == 0:
                self.spawn_particle("trail_bubble")
            if self.dive_scale >= 0.99 and (abs(self.vy) < 1.2 or self.py <= self._saved_surface_y):
                self.dive_scale = 1.0
                self.state = "swim"
                self.set_expression("happy", 90)
                self.impulse_squash(1.16, 0.86)
            return

        # --- Kéo thả ---
        if self.state == "drag":
            self.puff_factor *= 0.85
            self.pitch_deg = max(-22.0, min(22.0, self._drag_vel_y * 1.4))
            return

        # --- Chờ thả file / Đang hút file / Đang nhai file ---
        if self.state == "swallow_ready":
            self.vx *= 0.72
            self.vy *= 0.72
            if self._drag_leave_grace > 0:
                self._drag_leave_grace -= 1
                if self._drag_leave_grace == 0:
                    self.state = "swim"
                    self.suction_alpha = 0.0
                    self.mouth_locked = False
            return

        if self.state == "swallow_gulp":
            self.swallow_ticks -= 1
            self.vx *= 0.82
            self.vy *= 0.82
            self.eating_file_progress = min(1.0, 1.0 - self.swallow_ticks / 24.0)
            if self.swallow_ticks <= 0:
                self.eating_file_progress = -1.0
                self.suction_alpha = 0.0
                self.state = "eat_file"
                self.impulse_squash(1.20, 0.84)
                for _ in range(5):
                    self.spawn_particle("crumb")
            return

        if self.state == "eat_file":
            self.chew_ticks -= 1
            self.vx *= 0.84
            self.vy *= 0.84
            self.pitch_deg *= 0.88
            if self.chew_ticks % 11 == 0:
                self.impulse_squash(1.12, 0.90)
                self.spawn_particle("crumb")
                if self.chew_ticks % 22 == 0:
                    self.spawn_particle("star")
            if self.chew_ticks == 12:
                self.sound.play_pop()
                for _ in range(9):
                    self.spawn_particle("bubble")
            if self.chew_ticks <= 0:
                # Ăn xong file -> ăn mừng tự hào hình số 8!
                self.trigger_celebrate_figure8()
            return

        # --- Post-Dizzy: Nôn bong bóng cầu vồng -> Nằm ngửa bụng 3s ---
        if self.state == "nauseous_vomit":
            self.nauseous_ticks -= 1
            self.vx *= 0.88
            self.vy *= 0.88
            self.pitch_deg = -10.0 * self.direction
            if self.nauseous_ticks % 4 == 0:
                self.spawn_particle("rainbow_bubble")
                self.impulse_squash(1.10, 0.92)
            if self.nauseous_ticks <= 0:
                self.state = "belly_up"
                self.belly_up_ticks = 3 * FPS  # 3 giây ngửa bụng trôi lờ đờ
                self.vx = random.uniform(-0.4, 0.4)
                self.vy = -0.35
                self.pitch_deg = 0.0
            return

        if self.state == "belly_up":
            self.belly_up_ticks -= 1
            self.vx *= 0.985
            self.vy = self.vy * 0.98 - 0.008  # nổi lờ đờ nhẹ lên trên
            self.px += self.vx
            self.py += self.vy
            self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=False)
            if self.belly_up_ticks <= 0:
                self.state = "swim"
                self.impulse_squash(1.16, 0.86)
                self.set_expression("sleepy", 50)
            return

        # --- Hắt xì (Lấy hơi -> Bùng nổ giật lùi) ---
        if self.state == "sneeze_windup":
            self.sneeze_ticks -= 1
            self.vx *= 0.80
            self.vy *= 0.80
            self.pitch_deg = -12.0 * self.direction
            self.squash_x = 1.14
            self.squash_y = 1.12
            if self.sneeze_ticks <= 0:
                self.state = "sneeze_burst"
                self.sneeze_ticks = 26
                # Giật lùi mạnh về phía sau!
                self.vx = -self.direction * 7.8
                self.vy = random.uniform(-1.4, 1.4)
                self.impulse_squash(0.74, 1.30)
                self.sound.play_pop()
                for _ in range(5):
                    self.spawn_particle("water_drop")
                for _ in range(3):
                    self.spawn_particle("bubble")
            return

        if self.state == "sneeze_burst":
            self.sneeze_ticks -= 1
            self.vx *= 0.91
            self.vy *= 0.91
            self.px += self.vx
            self.py += self.vy
            self.pitch_deg *= 0.86
            self._apply_bounds(min_x, max_x, min_y, max_y)
            if self.sneeze_ticks <= 0:
                self.state = "swim"
                self.set_expression("shy", 65)
            return

        # --- Tự hào / Ăn mừng lượn vòng hình số 8 (∞) ---
        if self.state == "celebrate_fig8":
            self.fig8_ticks -= 1
            prog = 1.0 - (self.fig8_ticks / max(1, self.fig8_total))
            t = prog * math.tau
            ox, oy = self.fig8_origin
            nx = max(min_x, min(max_x, ox + math.sin(t) * 62.0))
            ny = max(min_y, min(max_y, oy + math.sin(2.0 * t) * 28.0))
            self.vx = nx - self.px
            self.vy = ny - self.py
            self.px, self.py = nx, ny
            if abs(self.vx) > 0.25:
                self.direction = 1 if self.vx > 0 else -1
            self.pitch_deg = max(-28.0, min(28.0, self.vy * 4.5 * self.direction))
            if self.fig8_ticks % 4 == 0:
                self.spawn_particle("trail_bubble")
            if self.fig8_ticks <= 0:
                self.state = "swim"
                self.set_expression("happy", 70)
            return

        # --- Nhảy vọt "Vượt Vũ Môn" rời khỏi thanh tiêu đề cửa sổ ---
        if self.state == "window_leap":
            self._window_leap_ticks -= 1
            self.vy += 0.34  # Cung parabol rơi tự nhiên xuống bể nước
            self.vx *= 0.985
            self.px += self.vx
            self.py += self.vy
            self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=True)
            spd_now = math.hypot(self.vx, self.vy)
            target_pitch = max(-36.0, min(36.0, math.degrees(math.atan2(self.vy, max(0.8, abs(self.vx)))) * 0.72 * self.direction))
            self.pitch_deg = _lerp_angle_deg(self.pitch_deg, target_pitch, 0.22)
            if self.frame % 3 == 0:
                self.spawn_particle("trail_bubble")
            if self._window_leap_ticks <= 0:
                self.state = "swim"
                self.set_expression("happy", 65)
                self._pick_new_swim_target(min_y=min_y)
            return

        # --- Hụt chân rơi tự do khi cửa sổ đang lướt bị đóng / thu nhỏ ---
        if self.state == "window_drop":
            self._window_drop_ticks -= 1
            self.vy = min(10.5, self.vy + 0.42)
            self.vx *= 0.96
            self.px += self.vx
            self.py += self.vy
            self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=True)
            self.pitch_deg = _lerp_angle_deg(self.pitch_deg, 28.0 * self.direction, 0.16)
            if self.frame % 4 == 0:
                self.spawn_particle("bubble")
            if self._window_drop_ticks <= 0:
                self.state = "swim"
                self.vy *= 0.35
                self.impulse_squash(1.18, 0.84)
                self._pick_new_swim_target(min_y=min_y)
            return

        # --- Đậu / Lướt mặt nước & Ngó trên thanh tiêu đề cửa sổ ---
        if self.state in ("window_surf", "window_peek"):
            self._perch_ticks -= 1
            if (
                self._perch_rect is None
                or self.is_overloaded
                or self.foods
                or self.hold_still
                or self.chase_mode
            ):
                self._clear_click_through()
                self.state = "swim"
                self._perch_rect = None
                self._perch_wid = 0
                self._surf_landed = False
                self._surf_nip_phase = "none"
                self.facing_front = False
                return

            # Theo dõi trực tiếp cửa sổ mỗi 3 frame (~50ms): phát hiện kéo di chuyển hoặc đóng/thu nhỏ!
            if self._perch_wid and self.frame % 3 == 0:
                live_rect = self.window_tracker.get_window_rect(self._perch_wid)
                if live_rect is None:
                    # Cửa sổ vừa bị Đóng hoặc Thu nhỏ -> cá giật mình hụt chân rơi tự do!
                    self._start_window_drop()
                    return
                if live_rect != self._perch_rect:
                    wdx = live_rect.left() - self._perch_rect.left()
                    wdy = live_rect.top() - self._perch_rect.top()
                    self._perch_rect = live_rect
                    zone = _window_safe_zone(live_rect)
                    if zone is None:
                        self._start_window_drop()
                        return
                    self._perch_safe_min, self._perch_safe_max = zone
                    if self.state == "window_surf" and self._surf_landed and (abs(wdx) >= 1 or abs(wdy) >= 1):
                        # Giữ vị trí tương đối theo thanh cửa sổ nhưng ngả người ra sau theo quán tính + Ngạc nhiên!
                        self.px += wdx
                        self.py += wdy
                        target_bal = max(-32.0, min(32.0, -wdx * 2.2))
                        self._surf_balance_deg += (target_bal - self._surf_balance_deg) * 0.48
                        was_dragged = self._surf_drag_ticks > 0
                        self._surf_drag_ticks = 24
                        if not was_dragged:
                            self.spawn_particle("excl")
                            self.impulse_squash(0.86, 1.16)
                        if self.frame % 6 == 0:
                            self.spawn_particle("water_drop", SIZE / 2.0, SIZE / 2.0 + 18.0)

            win = self._perch_rect
            if self.state == "window_surf":
                zone = _window_safe_zone(win)
                if zone is None:
                    self._start_window_drop()
                    return
                safe_min_x, safe_max_x = zone
                self._perch_safe_min, self._perch_safe_max = safe_min_x, safe_max_x
                left_px = safe_min_x - SIZE / 2.0
                right_px = safe_max_x - SIZE / 2.0
                surf_py = self._surf_target_py(float(win.top()))
                fcx = self.px + SIZE / 2.0

                if self._surf_drag_ticks > 0:
                    self._surf_drag_ticks -= 1
                else:
                    self._surf_balance_deg *= 0.84

                if self._surf_nip_cd > 0:
                    self._surf_nip_cd -= 1

                # --- Giai đoạn 1: Tiếp cận & Ngoi lên mặt nước mượt mà (Smooth Approach, KHÔNG snap cứng Y) ---
                if self._surf_phase == "approach":
                    tx = max(left_px + 28.0, min(right_px - 28.0, self.target_x))
                    ty = surf_py + 12.0  # Hướng mũi hơi dưới mép cửa sổ để ngoi bật lên mượt mà
                    dx = tx - self.px
                    dy = ty - self.py
                    dist = max(1.0, math.hypot(dx, dy))
                    steer_spd = min(3.6, max(2.2, dist * 0.045))
                    self.vx += ((dx / dist) * steer_spd - self.vx) * 0.11
                    self.vy += ((dy / dist) * steer_spd - self.vy) * 0.11
                    self.px += self.vx
                    self.py += self.vy
                    # Đồng bộ tuyệt đối hướng mặt với dấu vx
                    if abs(self.vx) > 0.20:
                        self._set_direction(1 if self.vx > 0 else -1)
                    vel_deg = max(-35.0, min(35.0, math.degrees(math.atan2(self.vy, max(1.0, abs(self.vx)))) * 0.78))
                    self.pitch_deg = _lerp_angle_deg(self.pitch_deg, vel_deg * self.direction, 0.18)

                    # Đã tiến tới sát điểm bắt đầu trong vùng an toàn -> phóng lên nhịp nhảy đầu tiên!
                    if dist <= 22.0 or (abs(self.py - surf_py) <= 16.0 and (safe_min_x + 20.0) <= (self.px + SIZE / 2.0) <= (safe_max_x - 20.0)):
                        self._launch_porpoise_arc(win)
                    elif self._perch_ticks <= 0:
                        self._clear_click_through()
                        self.state = "swim"
                        self._perch_rect = None
                        self._perch_wid = 0
                    return

                # --- Giai đoạn 2a: Đang bay trên cung nhảy Parabol (Porpoising Arc) ---
                if self._surf_phase == "arc":
                    self._surf_elapsed += 1
                    self.vy += 0.34  # Trọng lực giả lập tạo quỹ đạo parabol mềm mại
                    self.px += self.vx
                    self.py += self.vy

                    # Giữ cá nằm gọn trong Safe Zone, không bay đè lên nút cửa sổ
                    if self.px < left_px:
                        self.px = left_px
                        self.vx = abs(self.vx) * 0.55
                        self._perch_dir = 1
                    elif self.px > right_px:
                        self.px = right_px
                        self.vx = -abs(self.vx) * 0.55
                        self._perch_dir = -1

                    # Đồng bộ tuyệt đối hướng mặt với dấu vx (vx < 0 -> Trái, vx > 0 -> Phải)
                    if abs(self.vx) > 0.20:
                        self._set_direction(1 if self.vx > 0 else -1)

                    # Góc nghiêng thân động bám theo vector vận tốc atan2(vy, abs(vx)) trong [-35°, +35°]
                    vel_deg = max(-35.0, min(35.0, math.degrees(math.atan2(self.vy, max(1.0, abs(self.vx)))) * 0.88))
                    self.pitch_deg = _lerp_angle_deg(
                        self.pitch_deg, vel_deg * self.direction + self._surf_balance_deg, 0.30
                    )

                    if self.frame % 4 == 0:
                        self.spawn_particle("trail_bubble")

                    # Khi lao xuống chạm lại mặt nước cửa sổ (win.top)
                    if self.vy > 0.0 and self.py >= surf_py:
                        self._spawn_surface_splash(float(win.top()), play_sound=True)
                        self.impulse_squash(1.22, 0.80)
                        self._porpoise_arcs_left -= 1
                        if self._porpoise_arcs_left > 0 and self._perch_ticks > 20:
                            # Chìm cong nhẹ dưới mặt nước ~0.2s để lấy đà bật nhịp nhảy kế tiếp
                            self._surf_phase = "dip"
                            self._porpoise_dip_ticks = 12
                            self.vy = min(2.4, self.vy * 0.45)
                        else:
                            # Giai đoạn 3: Kết thúc chuỗi nhảy -> giữ nguyên đà chúi đầu lặn sâu xuống vùng tự do!
                            self._surf_phase = "dive_out"
                            self._porpoise_dive_ticks = 28
                            self.vy = max(3.4, min(5.4, self.vy * 0.82))
                            self.vx *= 0.88
                    return

                # --- Giai đoạn 2b: Lướt cong ngắn dưới mặt nước giữa 2 nhịp nhảy ---
                if self._surf_phase == "dip":
                    self._surf_elapsed += 1
                    self._porpoise_dip_ticks -= 1

                    # Nếu gần sát biên vùng an toàn -> giảm tốc & quay đầu mượt qua Front View!
                    if (fcx <= safe_min_x + 48.0 and self._perch_dir < 0) or (fcx >= safe_max_x - 48.0 and self._perch_dir > 0):
                        self._perch_dir *= -1
                        self.vx = self._perch_dir * max(2.2, abs(self.vx) * 0.75)
                        self._set_direction(self._perch_dir)
                    else:
                        self.vx += (self._perch_dir * 3.8 - self.vx) * 0.14
                        if abs(self.vx) > 0.20:
                            self._set_direction(1 if self.vx > 0 else -1)

                    # Đường cong chữ U dưới mặt nước (lặn xuống nhẹ rồi ngóc mũi hướng lên)
                    self.vy -= 0.42
                    self.px = max(left_px, min(right_px, self.px + self.vx))
                    self.py = max(surf_py - 2.0, min(surf_py + 16.0, self.py + self.vy))

                    vel_deg = max(-30.0, min(30.0, math.degrees(math.atan2(self.vy, max(1.0, abs(self.vx)))) * 0.80))
                    self.pitch_deg = _lerp_angle_deg(
                        self.pitch_deg, vel_deg * self.direction + self._surf_balance_deg, 0.28
                    )
                    if self.frame % 3 == 0:
                        self.spawn_particle("trail_bubble")

                    if self._porpoise_dip_ticks <= 0:
                        self._launch_porpoise_arc(win)
                    return

                # --- Giai đoạn 3: Chúi đầu xuyên qua thanh tiêu đề lặn sâu trở lại FREE_SWIM ---
                self._porpoise_dive_ticks -= 1
                self.vx *= 0.97
                self.vy = self.vy * 0.94 + 0.06  # Trượt lặn êm xuống dưới rồi dịu dần
                self.px += self.vx
                self.py += self.vy
                self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=True)

                # Luôn đồng bộ hướng mặt với dấu vx & chúi mũi theo vector lặn
                if abs(self.vx) > 0.20:
                    self._set_direction(1 if self.vx > 0 else -1)
                vel_deg = max(-35.0, min(35.0, math.degrees(math.atan2(self.vy, max(1.0, abs(self.vx)))) * 0.82))
                self.pitch_deg = _lerp_angle_deg(self.pitch_deg, vel_deg * self.direction, 0.20)

                # Hiệu ứng vệt bong bóng nhỏ dưới nước khi lặn sâu
                if self.frame % 2 == 0:
                    self.spawn_particle("trail_bubble")
                if self.frame % 6 == 0:
                    self.spawn_particle("bubble")

                if self._porpoise_dive_ticks <= 0:
                    self._clear_click_through()
                    self.state = "swim"
                    self._perch_rect = None
                    self._perch_wid = 0
                    self._surf_landed = False
                    self._surf_phase = "approach"
                    self._surf_snap_cooldown = int(4.0 * FPS)
                    self.set_expression("happy", 65)
                    self._pick_new_swim_target(min_y=min_y)
                return

            else:  # window_peek: thò nửa đầu lên trên thanh tiêu đề để ngó
                if self._perch_ticks <= 0:
                    self.state = "swim"
                    self._perch_rect = None
                    self._perch_wid = 0
                    self.facing_front = False
                    return
                dx = self.target_x - self.px
                dy = self.target_y - self.py
                dist = math.hypot(dx, dy)
                if dist > 10.0:
                    self.vx += ((dx / dist) * 2.6 - self.vx) * 0.10
                    self.vy += ((dy / dist) * 2.6 - self.vy) * 0.10
                    self.px += self.vx
                    self.py += self.vy
                    if abs(self.vx) > 0.3:
                        self._set_direction(1 if self.vx > 0 else -1)
                    self.facing_front = False
                else:
                    self.vx *= 0.78
                    self.vy *= 0.78
                    self.facing_front = True
                    self.pitch_deg *= 0.85
                self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=False)
                return

        # --- Biến hình Cá Nóc ---
        if self.state == "puffed":
            self.puff_factor = min(1.0, self.puff_factor + 0.075)
            self.vx *= 0.90
            self.vy *= 0.90
            self.pitch_deg *= 0.85
            self.px = max(min_x, min(max_x, self.px + self.vx))
            self.py = max(min_y, min(max_y, self.py + self.vy))
            self.puff_ticks -= 1
            if self.puff_ticks % 45 == 0:
                self.spawn_particle("anger")
            if self.puff_ticks <= 0:
                self.state = "deflate_zoom"
                self.facing_front = False
                self.deflate_ticks = int(2.6 * FPS)
                ang = random.uniform(0, math.tau)
                self.vx = math.cos(ang) * 14.0
                self.vy = math.sin(ang) * 14.0
                self.sound.play_pop()
            return

        if self.state == "deflate_zoom":
            self.deflate_ticks -= 1
            self.puff_factor = max(0.0, self.puff_factor - 0.018)
            turn = math.sin(self.frame * 0.28) * 0.16 + random.uniform(-0.08, 0.08)
            ang = math.atan2(self.vy, self.vx) + turn
            spd = 13.5 * (0.45 + 0.55 * (self.deflate_ticks / (2.6 * FPS)))
            self.vx = math.cos(ang) * spd
            self.vy = math.sin(ang) * spd
            self.px += self.vx
            self.py += self.vy
            self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=True)
            self.direction = 1 if self.vx >= 0 else -1
            self.pitch_deg = max(-35.0, min(35.0, (self.vy / max(1.0, spd)) * 35.0 * self.direction))
            if self.frame % 2 == 0:
                self.spawn_particle("puff_air")
            if self.deflate_ticks <= 0:
                self.state = "swim"
                self.puff_factor = 0.0
                self.vx *= 0.25
                self.vy *= 0.25
                self.set_expression("dizzy", 80)
            return

        # --- Trạng thái Giả chết (lật ngửa bụng nổi lềnh bềnh lên sát đỉnh màn hình) ---
        if self.state == "play_dead":
            self.puff_factor *= 0.9
            dx = self.target_x - self.px
            dy = self.target_y - self.py
            self.vx = self.vx * 0.95 + max(-0.06, min(0.06, dx * 0.0015))
            self.vy = self.vy * 0.95 + max(-0.12, min(0.06, dy * 0.0028))
            self.px = max(min_x, min(max_x, self.px + self.vx + math.sin(self.frame * 0.025) * 0.25))
            self.py = max(min_y, min(max_y, self.py + self.vy + math.sin(self.frame * 0.032) * 0.28))
            self.pitch_deg = math.sin(self.frame * 0.022) * 6.5
            self.depth_target = 0.78
            # Thỉnh thoảng hé trộm 1 mắt liếc xem bạn có đang nhìn không rồi lại giả chết tiếp!
            if self._dead_peek_ticks > 0:
                self._dead_peek_ticks -= 1
            else:
                self._dead_peek_cd -= 1
                if self._dead_peek_cd <= 0:
                    self._dead_peek_ticks = int(0.65 * FPS)
                    self._dead_peek_cd = random.randint(6 * FPS, 10 * FPS)
            return

        # --- Đang đớp một hạt cám / ký tự ---
        if self.state == "eat":
            self.vx *= 0.80
            self.vy *= 0.80
            self.pitch_deg *= 0.85
            food = self._eating_food
            if food is None or food not in self.foods:
                self._eating_food = None
                self.state = "swim"
                return
            food.bite_progress = min(1.0, food.bite_progress + 1.0 / 26.0)
            food.update()
            if self.frame % 7 == 0:
                self.spawn_particle("bubble")
            if food.bite_progress >= 1.0:
                food.close()
                if food in self.foods:
                    self.foods.remove(food)
                self._eating_food = None
                self.state = "swim"
                self._on_ate_morsel()
                if not self.foods:
                    self.set_expression("love", 105)
            return

        # --- Đứng yên tại chỗ nếu bật hold_still ---
        self.puff_factor *= 0.90
        fcx, fcy = self.center_global()
        if self.hold_still and not self.foods and not self.is_overloaded and (self.pong_bubble is None or not self.pong_bubble.in_rally):
            self.vx *= 0.85
            self.vy *= 0.85
            self.facing_front = False
            gaze_dx = cur.x() - fcx
            gaze_dy = cur.y() - fcy
            if self.cursor_gaze_enabled and math.hypot(gaze_dx, gaze_dy) <= CURSOR_ATTENTION_RADIUS:
                # Lớp 3: Lật hướng có vùng đệm 35px (Hysteresis)
                if gaze_dx > FLIP_HYSTERESIS_PX:
                    self._set_direction(1)
                elif gaze_dx < -FLIP_HYSTERESIS_PX:
                    self._set_direction(-1)
                # Lớp 2: Nghiêng đầu/thân có độ trễ + giới hạn [-35°, +35°] khi lệch > 20°
                raw_deg = math.degrees(math.atan2(gaze_dy, max(1.0, abs(gaze_dx))))
                if abs(raw_deg) > BODY_TILT_THRESHOLD_DEG:
                    blend = min(1.0, (abs(raw_deg) - BODY_TILT_THRESHOLD_DEG) / 8.0)
                    clamped = max(-BODY_TILT_MAX_DEG, min(BODY_TILT_MAX_DEG, raw_deg))
                    self.pitch_deg = _lerp_angle_deg(self.pitch_deg, clamped * self.direction * blend, BODY_TILT_DAMPING)
                else:
                    self.pitch_deg = _lerp_angle_deg(self.pitch_deg, 0.0, BODY_TILT_DAMPING)
            else:
                self.pitch_deg = _lerp_angle_deg(self.pitch_deg, 0.0, BODY_TILT_DAMPING)
            self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=False)
            return

        # --- Bơi lội 360° với lực đẩy Tail-Beat Impulse ---
        max_spd = 2.4
        base_steer = 0.075
        use_tail_impulse = True

        # Kiểm tra Vùng chú ý (Attention Radius ~ 350px) cho hệ thống nhìn theo chuột 3 lớp
        gaze_dx = cur.x() - fcx
        gaze_dy = cur.y() - fcy
        gaze_dist = math.hypot(gaze_dx, gaze_dy)
        gaze_active = (
            self.cursor_gaze_enabled
            and gaze_dist <= CURSOR_ATTENTION_RADIUS
            and not self.is_overloaded
            and not self.foods
            and (self.pong_bubble is None or not self.pong_bubble.in_rally)
        )

        # Ưu tiên 1: Bóng bàn Bong Bóng (đón bóng người chơi vừa hất!)
        if self.pong_bubble is not None and self.pong_bubble.alive and self.pong_bubble.in_rally and self.pong_bubble.last_hitter == "player":
            bcx, bcy = self.pong_bubble.center()
            dx, dy = bcx - fcx, bcy - fcy
            dist = math.hypot(dx, dy)
            if dist < 50.0 and self.pong_bubble.hit_cooldown == 0:
                # Dùng mũi húc bong bóng bay ngược lại phía con trỏ chuột của người chơi!
                tx = cur.x() - bcx + random.uniform(-35, 35)
                ty = cur.y() - bcy + random.uniform(-35, 35)
                tdist = max(1.0, math.hypot(tx, ty))
                spd = 11.5
                self.pong_bubble.launch((tx / tdist) * spd, (ty / tdist) * spd, hitter="fish")
                self.impulse_squash(0.74, 1.30)
                self.sound.play_pop()
                for _ in range(5):
                    self.spawn_particle("star")
                self.set_expression("happy", 55)
            else:
                max_spd = 7.4
                base_steer = 0.22
                use_tail_impulse = False
                self.target_x = bcx - SIZE / 2.0
                self.target_y = max(min_y, min(max_y, bcy - SIZE / 2.0))
                self.facing_front = False

        # Ưu tiên 2: Mưa cám cá / Ký tự rơi từ đỉnh màn hình
        elif self.foods:
            nearest = min(self.foods, key=lambda f: math.hypot(f.center()[0] - fcx, f.center()[1] - fcy))
            tx, ty = nearest.center()
            dist = math.hypot(tx - fcx, ty - fcy)
            if dist < 38.0:
                self._eating_food = nearest
                self.state = "eat"
                self.impulse_squash(1.18, 0.86)
                return
            max_spd = 5.4
            base_steer = 0.16
            self.target_x, self.target_y = tx - SIZE / 2.0, max(min_y, min(max_y, ty - SIZE / 2.0))
            self.facing_front = False

        # Ưu tiên 3: Quá tải CPU/RAM > 85%
        elif self.is_overloaded:
            max_spd = 5.8
            base_steer = 0.18
            self.retarget_ticks -= 2
            if self.retarget_ticks <= 0:
                self._pick_new_swim_target(min_y=min_y, fast=True)
            self.facing_front = False

        # Ưu tiên 4: Chế độ đuổi theo chuột
        elif self.chase_mode:
            dx = cur.x() - fcx
            dy = cur.y() - fcy
            dist = math.hypot(dx, dy)
            if dist > 48.0:
                max_spd = 4.6
                base_steer = 0.13
                self.target_x = cur.x() - SIZE / 2.0
                self.target_y = max(min_y, min(max_y, cur.y() - SIZE / 2.0))
                self.facing_front = False
            else:
                self.vx *= 0.88
                self.vy *= 0.88
                self.facing_front = True
                if self.frame % 90 == 0:
                    self.set_expression("happy", 55)
                self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=False)
                return

        # Ưu tiên 5: Bơi tự do 360°
        else:
            if self.is_night_mode:
                max_spd = 1.1
                base_steer = 0.035
            elif self.water_overlay.active and self.water_overlay.phase == "break":
                max_spd = 2.8
                base_steer = 0.085
            elif self.current_color_score < -0.32 and self.wallpaper_aware:
                max_spd = 3.6
                base_steer = 0.11
                if self.retarget_ticks > 25:
                    self.retarget_ticks = 20

            if gaze_active:
                # Trong vùng chú ý 350px, cá bơi khoan thai hơn để ngoái mắt theo chuột tự nhiên
                max_spd = min(max_spd, 1.55)

            self.retarget_ticks -= 1
            if self.retarget_ticks <= 0 or math.hypot(self.target_x - self.px, self.target_y - self.py) < 30.0:
                self._pick_new_swim_target(min_y=min_y)

        # Lực đẩy theo nhịp vẫy đuôi (Tail-Beat Impulse):
        # tăng tốc nhẹ mỗi cú quẫy đuôi rồi lướt chậm dần bằng lực cản nước!
        dx = self.target_x - self.px
        dy = self.target_y - self.py
        dist = math.hypot(dx, dy)
        if dist > 1.0:
            if use_tail_impulse:
                beat_pulse = abs(math.cos(self.tail_phase)) ** 2.4
                impulse_mult = 0.35 + 1.55 * beat_pulse
                desired_vx = (dx / dist) * max_spd * (0.72 + 0.55 * beat_pulse)
                desired_vy = (dy / dist) * max_spd * (0.72 + 0.55 * beat_pulse)
                self.vx += (desired_vx - self.vx) * (base_steer * impulse_mult)
                self.vy += (desired_vy - self.vy) * (base_steer * impulse_mult)
            else:
                desired_vx = (dx / dist) * max_spd
                desired_vy = (dy / dist) * max_spd
                self.vx += (desired_vx - self.vx) * base_steer
                self.vy += (desired_vy - self.vy) * base_steer

        # Lực cản nước tự nhiên (glide damping giữa các nhịp vẫy đuôi)
        drag = 0.968 if use_tail_impulse else 0.975
        self.vx *= drag
        self.vy *= drag
        self.px += self.vx
        self.py += self.vy
        self._apply_bounds(min_x, max_x, min_y, max_y, bouncy=True)

        # Kiểm tra tự động "tiếp nước" lên thanh tiêu đề cửa sổ khi cá bơi ngang/hạ xuống sát mép trên
        if (
            self.window_perch_enabled
            and self._surf_snap_cooldown == 0
            and not self.is_overloaded
            and not self.foods
            and not self.hold_still
            and not self.chase_mode
            and not self.water_overlay.active
            and not self.is_night_mode
            and self.vy > 0.15
            and self.tracked_windows
        ):
            snapped, tw, s_min, s_max = check_window_surface_snap(
                self.px, self.py, SIZE, SIZE, self.tracked_windows
            )
            if snapped and tw is not None:
                # Tiếp cận mượt & phóng lên chuỗi 2–4 nhịp cá heo nhảy sóng (không snap cứng Y)
                self._enter_window_surf_on(tw, s_min, s_max, already_landed=False)
                return

        spd_now = math.hypot(self.vx, self.vy)
        swim_pitch = 0.0
        if spd_now > 0.35:
            swim_pitch = max(-26.0, min(26.0, math.degrees(math.atan2(self.vy, max(0.8, abs(self.vx)))) * 0.55 * self.direction))

        if gaze_active:
            # Lớp 3: Lật hướng Trái/Phải có vùng đệm 35px (Hysteresis) + chuyển cảnh quay đầu qua Front View
            if gaze_dx > FLIP_HYSTERESIS_PX:
                self._set_direction(1)
            elif gaze_dx < -FLIP_HYSTERESIS_PX:
                self._set_direction(-1)

            # Lớp 2: Xoay góc đầu & thân có độ trễ (damping 0.08) + giới hạn [-35°, +35°] khi góc lệch > 20°
            raw_angle_deg = math.degrees(math.atan2(gaze_dy, max(1.0, abs(gaze_dx))))
            if abs(raw_angle_deg) > BODY_TILT_THRESHOLD_DEG:
                blend = min(1.0, (abs(raw_angle_deg) - BODY_TILT_THRESHOLD_DEG) / 8.0)
                clamped_deg = max(-BODY_TILT_MAX_DEG, min(BODY_TILT_MAX_DEG, raw_angle_deg))
                target_pitch = swim_pitch * (1.0 - blend) + (clamped_deg * self.direction) * blend
            else:
                target_pitch = swim_pitch
            self.pitch_deg = _lerp_angle_deg(self.pitch_deg, target_pitch, BODY_TILT_DAMPING)
        else:
            # Ngoài vùng chú ý 350px -> cá bơi tự do ngắm cảnh, xoay hướng mượt theo vận tốc bơi
            if abs(self.vx) > 0.32:
                self._set_direction(1 if self.vx > 0 else -1)
            self.pitch_deg = _lerp_angle_deg(self.pitch_deg, swim_pitch, 0.12)

    def _apply_bounds(self, min_x: float, max_x: float, min_y: float, max_y: float, bouncy: bool = True):
        if self.px < min_x:
            self.px = min_x
            if bouncy and abs(self.vx) > 1.6:
                self.impulse_squash(0.76, 1.26)
            self.vx = abs(self.vx) * 0.78 + 0.45
        elif self.px > max_x:
            self.px = max_x
            if bouncy and abs(self.vx) > 1.6:
                self.impulse_squash(0.76, 1.26)
            self.vx = -abs(self.vx) * 0.78 - 0.45

        if self.py < min_y:
            self.py = min_y
            if bouncy and abs(self.vy) > 1.6:
                self.impulse_squash(1.26, 0.76)
            self.vy = abs(self.vy) * 0.72 + 0.35
        elif self.py > max_y:
            self.py = max_y
            if bouncy and abs(self.vy) > 1.6:
                self.impulse_squash(1.26, 0.76)
            self.vy = -abs(self.vy) * 0.72 - 0.35

    def _pick_new_swim_target(self, min_y: float | None = None, fast: bool = False):
        # Thỉnh thoảng chủ động lướt hoặc đậu ngó lên mép trên cửa sổ trình duyệt / IDE!
        if (
            not fast
            and self.window_perch_enabled
            and not self.water_overlay.active
            and not self.is_night_mode
            and self.open_windows
            and random.random() < 0.42
        ):
            if self.trigger_window_perch():
                return

        bounds = self.virtual_rect()
        top_lim = bounds.top() + 24.0 if min_y is None else max(bounds.top() + 24.0, min_y + 12.0)
        bot_lim = max(top_lim + 20.0, bounds.bottom() - SIZE - 24.0)
        left_lim = bounds.left() + 24.0
        right_lim = max(left_lim + 20.0, bounds.right() - SIZE - 24.0)

        chosen = None
        if self.wallpaper_aware and not fast and random.random() < 0.55:
            cool = self.wallpaper.pick_cool_target()
            if cool is not None:
                cx, cy = cool
                tx = max(left_lim, min(right_lim, cx - SIZE / 2 + random.uniform(-40, 40)))
                ty = max(top_lim, min(bot_lim, cy - SIZE / 2 + random.uniform(-40, 40)))
                chosen = (tx, ty)

        if chosen is None:
            chosen = (random.uniform(left_lim, right_lim), random.uniform(top_lim, bot_lim))

        self.target_x, self.target_y = chosen
        self.depth_target = random.uniform(0.05, 1.0)
        self.retarget_ticks = random.randint(25, 55) if fast else random.randint(140, 310)
        self.facing_front = (not fast) and (random.random() < 0.14)
        if not fast and self.expression_ticks == 0 and random.random() < 0.22:
            self.set_expression(random.choice(["happy", "shy"]), random.randint(75, 120))

    # ---------- Vẽ khung hình ----------
    def _compute_contact_shadow(self) -> tuple[float, float]:
        """Tính bóng đổ tiếp xúc (0..1) và tọa độ Y bề mặt ngay dưới bụng cá.

        Chỉ hiện khi cá bơi sát đáy màn hình (Taskbar) hoặc đậu/bơi gần mép trên cửa sổ ứng dụng;
        khi bơi lơ lửng giữa màn hình trả về (0.0, 0.0) để ẩn hoàn toàn bóng tròn.
        """
        if self.state in ("play_dead", "dive_hide", "hidden", "window_peek", "caged", "breaking_out"):
            return 0.0, 0.0
        if self.state == "window_surf" and self._surf_landed:
            return 0.0, 0.0
        depth_scale = (0.85 + 0.25 * max(0.0, min(1.0, self.depth))) * max(0.15, self.dive_scale)
        fcx = self.px + SIZE / 2.0
        belly_y = self.py + SIZE / 2.0 + 4.0 + (32.0 + 14.0 * self.puff_factor + 4.0 * self.chubby_factor) * depth_scale
        max_range = 92.0

        best_gap: float | None = None
        best_surf_y: float = 0.0

        # 1. Kiểm tra đáy màn hình (Taskbar / Dock)
        # Bù khoảng đệm trong suốt phía dưới widget (~46px) để khi cá bơi sát mép đáy bóng hiện rõ nét
        bounds = self.virtual_rect()
        floor_y = bounds.bottom() - 42.0
        gap_bot = floor_y - belly_y
        if -24.0 <= gap_bot <= max_range:
            best_gap = gap_bot
            best_surf_y = floor_y + 14.0

        # 2. Kiểm tra mép trên của cửa sổ ứng dụng đang mở (hoặc cửa sổ đang lướt trên đó)
        candidates = list(self.open_windows)
        if self._perch_rect is not None and self._perch_rect not in candidates:
            candidates.append(self._perch_rect)
        for win in candidates:
            if (win.left() - 18) <= fcx <= (win.right() + 18):
                gap_win = win.top() - belly_y
                if -16.0 <= gap_win <= max_range:
                    if best_gap is None or gap_win < best_gap:
                        best_gap = gap_win
                        best_surf_y = float(win.top())

        if best_gap is None:
            return 0.0, 0.0

        prox = max(0.0, min(1.0, 1.0 - max(0.0, best_gap) / max_range))
        return prox, best_surf_y - self.py

    def paintEvent(self, _):
        p = QPainter(self)
        cur = QCursor.pos()
        fcx, fcy = self.center_global()
        dx_c = cur.x() - fcx
        dy_c = cur.y() - fcy
        dist_c = math.hypot(dx_c, dy_c)
        look_dx, look_dy = 0.0, 0.0
        # Khi ở trong lồng, mắt cá luôn liếc theo con trỏ chuột toàn màn hình (Eye Tracking)
        eye_range_ok = (dist_c > 1.0) if self.state == "caged" else (1.0 < dist_c < 380.0)
        if eye_range_ok:
            raw_x = dx_c / dist_c
            raw_y = dy_c / dist_c
            look_dx = -raw_x if self.direction > 0 else raw_x
            look_dy = raw_y

        spd_norm = min(1.0, math.hypot(self.vx, self.vy) / 4.8)
        cage_mode = (
            "caged"
            if self.state == "caged"
            else ("breaking_out" if self.state == "breaking_out" else "none")
        )
        cage_drop_prog = 1.0 - (self.cage_drop_ticks / max(1, self.cage_drop_total))
        cage_opacity = 0.0 if (self.state == "breaking_out" and self.cage_break_released) else 1.0
        turn_prog = (1.0 - self._turn_ticks / max(1, TURN_AROUND_FRAMES)) if self._turn_ticks > 0 else -1.0
        contact_shadow, contact_shadow_y = self._compute_contact_shadow()
        surfing_waterline = (
            self.state == "window_surf"
            and self._surf_phase == "dip"
            and self._perch_rect is not None
        )
        surf_waterline_y = (
            max(48.0, min(SIZE - 12.0, float(self._perch_rect.top()) - self.py))
            if surfing_waterline and self._perch_rect is not None
            else 0.0
        )
        surf_speed = min(1.0, abs(self.vx) / 4.2) if surfing_waterline else 0.0

        st = FishRenderState(
            size=SIZE,
            theme=self.theme,
            t_sec=self.frame / FPS,
            frame=self.frame,
            direction=self.direction,
            pitch_deg=self.pitch_deg,
            spin_deg=self.spin_deg,
            depth=self.depth,
            squash_x=self.squash_x,
            squash_y=self.squash_y,
            puff_factor=self.puff_factor,
            expression=self.active_expression(),
            facing_front=self.facing_front,
            blink=(self.blink_frames > 0),
            look_dx=look_dx,
            look_dy=look_dy,
            swim_speed=spd_norm,
            in_sleep_bubble=False,
            water_helmet=(self.water_overlay.active and self.water_overlay.phase == "break" and cage_mode == "none"),
            seaweed_blanket=(self.is_night_mode and cage_mode == "none"),
            boiling=(self.is_overloaded and cage_mode == "none"),
            vortex_alpha=self.vortex_alpha,
            suction_alpha=self.suction_alpha,
            audio_bands=self.audio_bands,
            audio_level=self.audio_level,
            particles=self.particles,
            mouth_locked=self.mouth_locked,
            eating_file_progress=self.eating_file_progress,
            eating_file_start=self.eating_file_start,
            eating_file_is_dir=self.eating_file_is_dir,
            tail_phase=self.tail_phase,
            bank_deg=self.bank_deg,
            chubby_factor=self.chubby_factor,
            belly_up=(self.state in ("belly_up", "play_dead")),
            peeking_window=(self.state == "window_peek" and self.facing_front),
            dive_scale=self.dive_scale,
            cage_mode=cage_mode,
            cage_drop_progress=cage_drop_prog,
            cage_swing_deg=self.cage_swing_deg,
            cage_pleading=(self.state == "caged" and self.cage_plead_ticks > 0),
            cage_bend_amount=self.cage_bend_amount,
            cage_opacity=cage_opacity,
            muscular_level=self.cage_muscular,
            pupil_x=self.pupil_x,
            pupil_y=self.pupil_y,
            turn_progress=turn_prog,
            turn_from_dir=self._turn_from_dir,
            contact_shadow=contact_shadow,
            contact_shadow_y=contact_shadow_y,
            play_dead_peek=(self.state == "play_dead" and self._dead_peek_ticks > 0),
            surfing_waterline=surfing_waterline,
            surf_waterline_y=surf_waterline_y,
            surf_speed=surf_speed,
        )
        render_fish(p, st)

    # ---------- Tương tác chuột ----------
    def _is_inside_fish_body(self, local_pos: QPoint) -> bool:
        r = 58.0 + 28.0 * self.puff_factor
        return math.hypot(local_pos.x() - SIZE / 2.0, local_pos.y() - SIZE / 2.0) <= r

    def _is_inside_cage(self, local_pos: QPoint) -> bool:
        dx = abs(local_pos.x() - SIZE / 2.0)
        dy = local_pos.y() - (SIZE / 2.0 + 4.0)
        return dx <= 64.0 and -86.0 <= dy <= 70.0

    def mousePressEvent(self, e):
        self._last_user_activity = time.monotonic()
        if e.button() == Qt.MouseButton.LeftButton:
            if self.state == "breaking_out":
                return
            if self.state == "caged":
                if not self._is_inside_cage(e.position().toPoint()):
                    return
                gpos = e.globalPosition().toPoint()
                self._press_global = gpos
                self._drag_offset = gpos - self.frameGeometry().topLeft()
                self._last_drag_global = gpos
                self._drag_vel_x = 0.0
                self._drag_vel_y = 0.0
                self.cage_dragging = False
                return

            if not self._is_inside_fish_body(e.position().toPoint()):
                return
            if self.state == "play_dead":
                self._wake_from_play_dead()
                return

            gpos = e.globalPosition().toPoint()
            self._press_global = gpos
            self._drag_offset = gpos - self.frameGeometry().topLeft()
            self._last_drag_global = gpos
            self._drag_vel_x = 0.0
            self._drag_vel_y = 0.0

            now = time.monotonic()
            self.click_timestamps = [t for t in self.click_timestamps if (now - t) < 1.8]
            self.click_timestamps.append(now)

            if len(self.click_timestamps) >= 4 and self.state not in ("puffed", "deflate_zoom"):
                self.click_timestamps.clear()
                self._press_global = None
                self.trigger_pufferfish()
            else:
                self.impulse_squash(1.16, 0.86)
                self.spawn_particle("bubble")
                if len(self.click_timestamps) >= 2 and self.state == "swim":
                    self.set_expression("grumpy", 45)

        elif e.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        self._last_user_activity = time.monotonic()

        if (e.buttons() & Qt.MouseButton.LeftButton) and self._press_global is not None:
            gpos = e.globalPosition().toPoint()
            # Kéo thả lồng sắt để cố định ở bất kỳ đâu (mép trên cửa sổ, góc màn hình...)
            if self.state == "caged":
                if not self.cage_dragging:
                    if math.hypot(gpos.x() - self._press_global.x(), gpos.y() - self._press_global.y()) > 4.0:
                        self.cage_dragging = True
                if self.cage_dragging and self._drag_offset is not None:
                    if self._last_drag_global is not None:
                        self._drag_vel_x = 0.6 * self._drag_vel_x + 0.4 * (gpos.x() - self._last_drag_global.x())
                        self._drag_vel_y = 0.6 * self._drag_vel_y + 0.4 * (gpos.y() - self._last_drag_global.y())
                    self._last_drag_global = gpos
                    new_tl = gpos - self._drag_offset
                    self.px = float(new_tl.x())
                    self.py = float(new_tl.y())
                    self.cage_swing_deg = max(-10.0, min(10.0, -self._drag_vel_x * 0.65))
                    self.move(int(self.px), int(self.py))
                return

            if self.state != "drag":
                if math.hypot(gpos.x() - self._press_global.x(), gpos.y() - self._press_global.y()) > 6.0:
                    self.state = "drag"
                    self.facing_front = False
                    self.click_timestamps.clear()
            if self.state == "drag" and self._drag_offset is not None:
                if self._last_drag_global is not None:
                    self._drag_vel_x = 0.6 * self._drag_vel_x + 0.4 * (gpos.x() - self._last_drag_global.x())
                    self._drag_vel_y = 0.6 * self._drag_vel_y + 0.4 * (gpos.y() - self._last_drag_global.y())
                self._last_drag_global = gpos
                new_tl = gpos - self._drag_offset
                self.px = float(new_tl.x())
                self.py = float(new_tl.y())
                self.move(int(self.px), int(self.py))
                return

        if self.state == "swim" and self._is_inside_fish_body(pos):
            if self.last_hover_pos is not None:
                dist = math.hypot(pos.x() - self.last_hover_pos.x(), pos.y() - self.last_hover_pos.y())
                if 1.5 < dist < 24.0:
                    self.pet_rub_energy += dist
                    if self.pet_rub_energy > 58.0:
                        self.pet_rub_energy = 20.0
                        self.pet_love_streak += 1
                        self.impulse_squash(1.10, 0.91)
                        if self.pet_love_streak >= 3:
                            self.set_expression("love", 110)
                        else:
                            self.set_expression("happy", 90)
            self.last_hover_pos = pos
        else:
            self.last_hover_pos = None

    def leaveEvent(self, _):
        self.last_hover_pos = None

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.state == "caged":
                if self.cage_dragging:
                    # Ghim cố định tại vị trí thả, không văng đi!
                    self.cage_dragging = False
                    self.vx = 0.0
                    self.vy = 0.0
                    self.cage_swing_vel = max(-2.5, min(2.5, -self._drag_vel_x * 0.14))
                elif self._press_global is not None:
                    # Click nhẹ vào lồng -> rung nhẹ lồng & cá bám thanh sắt van xin đáng thương
                    self.cage_swing_vel += random.choice([-1.6, 1.6])
                    if self.cage_plead_ticks <= 0:
                        self.cage_plead_ticks = int(2.8 * FPS)
                        self.spawn_particle("tear")
            elif self.state == "drag":
                self.state = "swim"
                self.vx = max(-11.0, min(11.0, self._drag_vel_x * 0.45))
                self.vy = max(-11.0, min(11.0, self._drag_vel_y * 0.45))
                self.retarget_ticks = 70
            self._press_global = None
            self._drag_offset = None
            self._last_drag_global = None

    # ---------- Menu chuột phải ----------
    def _show_context_menu(self, global_pos: QPoint):
        menu = QMenu(self)

        # Chế độ Lồng Giam (Cage Mode - Ctrl+Esc)
        cage_label = "💪 Phá lồng thả tự do (Ctrl+Esc)" if self.state == "caged" else "🔒 Giam vào lồng sắt (Ctrl+Esc)"
        act_cage = menu.addAction(cage_label, self.toggle_cage_mode)
        act_cage.setEnabled(self.state != "breaking_out")
        menu.addSeparator()

        # Cho ăn (Cám cá & Ký tự / Từ khóa)
        feed_menu = menu.addMenu("🍤 Cho ăn (Cám & Ký tự)")
        feed_menu.addAction("✨ Thả mưa cám cá (5 hạt)", lambda: self.spawn_food_shower(5))
        feed_menu.addAction("🔤 Thả mưa Ký tự / Code & Emoji", lambda: self.spawn_word_food())
        feed_menu.addAction("✏️ Nhập chữ cho cá ăn...", self.prompt_custom_word_food)

        # Trò chơi nhỏ Bubble Pong
        pong_label = "⏹️ Dừng Bóng bàn Bong Bóng" if (self.pong_bubble and self.pong_bubble.alive) else "🏓 Chơi Bóng bàn Bong Bóng (Bubble Pong)"
        menu.addAction(pong_label, self.toggle_bubble_pong)

        # Kéo thả ăn & xóa file
        eat_file_menu = menu.addMenu("🗑️ Ăn & Xóa file (Kéo vào miệng)")
        act_hold = QAction("🧲 Đứng yên tại chỗ (Dễ kéo file vào miệng)", self, checkable=True)
        act_hold.setChecked(self.hold_still)
        act_hold.triggered.connect(lambda c: setattr(self, "hold_still", c))
        eat_file_menu.addAction(act_hold)
        eat_file_menu.addAction("📂 Chọn file cho cá ăn...", self.pick_files_to_eat)
        eat_file_menu.addSeparator()
        del_group = QActionGroup(self)
        del_group.setExclusive(True)
        for mode_key, label in (
            ("trash", "♻️ Chuyển vào Thùng rác (An toàn)"),
            ("permanent", "🔥 Xóa vĩnh viễn (Hỏi xác nhận)"),
        ):
            act = QAction(label, self, checkable=True)
            act.setChecked(self.delete_mode == mode_key)
            act.triggered.connect(lambda checked, m=mode_key: setattr(self, "delete_mode", m))
            del_group.addAction(act)
            eat_file_menu.addAction(act)

        # Đậu / Lướt thanh tiêu đề cửa sổ
        win_menu = menu.addMenu("🪟 Lướt & Ngó trên cửa sổ")
        act_win_on = QAction("Tự động lướt / ngó trên cửa sổ đang mở", self, checkable=True)
        act_win_on.setChecked(self.window_perch_enabled)
        act_win_on.triggered.connect(lambda c: setattr(self, "window_perch_enabled", c))
        win_menu.addAction(act_win_on)
        win_menu.addAction("🏄 Lướt dọc mép cửa sổ ngay", lambda: self.trigger_window_perch("window_surf"))
        win_menu.addAction("👀 Thò đầu ngó qua thanh tiêu đề ngay", lambda: self.trigger_window_perch("window_peek"))

        act_gaze = QAction("👀 Dõi ánh mắt theo chuột (Vùng 350px)", self, checkable=True)
        act_gaze.setChecked(self.cursor_gaze_enabled)
        act_gaze.triggered.connect(lambda c: setattr(self, "cursor_gaze_enabled", c))
        menu.addAction(act_gaze)

        act_chase = QAction("🖱️ Đuổi theo chuột", self, checkable=True)
        act_chase.setChecked(self.chase_mode)
        act_chase.triggered.connect(lambda c: setattr(self, "chase_mode", c))
        menu.addAction(act_chase)

        menu.addSeparator()

        # Pomodoro Mực Nước
        pomo_menu = menu.addMenu("⏱️ Pomodoro Mực Nước")
        pomo_menu.addAction("🌊 Tập trung 25p / Nghỉ 5p", lambda: self.start_pomodoro(25 * 60, 5 * 60))
        pomo_menu.addAction("⚡ Thử nhanh (1p / 20s)", lambda: self.start_pomodoro(60, 20))
        act_pomo_stop = pomo_menu.addAction("⏹️ Dừng Pomodoro", self.stop_pomodoro)
        act_pomo_stop.setEnabled(self.water_overlay.active)

        # Bong bóng Clipboard
        cb_menu = menu.addMenu("🫧 Bong bóng Clipboard")
        act_cb_toggle = QAction("Tự tạo bong bóng khi Ctrl+C", self, checkable=True)
        act_cb_toggle.setChecked(self.clipboard_bubbles_enabled)
        act_cb_toggle.triggered.connect(lambda c: setattr(self, "clipboard_bubbles_enabled", c))
        cb_menu.addAction(act_cb_toggle)
        cb_menu.addAction("💥 Nổ hết bong bóng", self.clear_clipboard_bubbles)

        # Bắt sóng âm thanh
        audio_menu = menu.addMenu("🎵 Bắt sóng âm thanh")
        audio_group = QActionGroup(self)
        audio_group.setExclusive(True)
        for mode_key, label in (
            ("auto", "Tự động (Âm thanh hệ thống)"),
            ("demo", "Nhịp nhạc Demo (Thử Equalizer & Backflip)"),
            ("off", "Tắt"),
        ):
            act = QAction(label, self, checkable=True)
            act.setChecked(self.audio.mode == mode_key)
            act.triggered.connect(lambda checked, m=mode_key: self.audio.set_mode(m))
            audio_group.addAction(act)
            audio_menu.addAction(act)
        audio_menu.addSeparator()
        audio_menu.addAction("🤸 Nhào lộn Backflip ngay", self.trigger_backflip)

        menu.addSeparator()

        # Biểu cảm & Vi biểu cảm
        expr_menu = menu.addMenu("🎭 Biểu cảm & Vi biểu cảm")
        for key, label in EXPRESSIONS_MENU:
            if key == "puffed":
                expr_menu.addAction(label, self.trigger_pufferfish)
            elif key == "nauseous":
                expr_menu.addAction(label, self.trigger_nauseous_rainbow)
            elif key == "sneeze":
                expr_menu.addAction(label, self.trigger_sneeze)
            elif key == "proud":
                expr_menu.addAction(label, self.trigger_celebrate_figure8)
            else:
                expr_menu.addAction(label, lambda checked=False, k=key: self._trigger_menu_expr(k))
        expr_menu.addSeparator()
        sleep_label = "⚡ Hồi sinh (Hết giả chết)" if self.state == "play_dead" else "💀 Giả chết (Nổi bụng)"
        expr_menu.addAction(
            sleep_label,
            self._wake_from_play_dead if self.state == "play_dead" else self.enter_play_dead,
        )

        # Cảm biến & Ngữ cảnh
        env_menu = menu.addMenu("🌡️ Ngữ cảnh & Cảm biến")
        act_wall = QAction("🎨 Nhận diện màu hình nền (Ưa xanh / Né đỏ)", self, checkable=True)
        act_wall.setChecked(self.wallpaper_aware)
        act_wall.triggered.connect(lambda c: setattr(self, "wallpaper_aware", c))
        env_menu.addAction(act_wall)

        act_boil = QAction(
            f"🔥 Mô phỏng quá tải CPU (Hiện tại: {self.cpu_percent:.0f}% / RAM {self.ram_percent:.0f}%)",
            self,
            checkable=True,
        )
        act_boil.setChecked(self.simulate_overload)
        act_boil.triggered.connect(self._toggle_sim_overload)
        env_menu.addAction(act_boil)

        act_night = QAction("🌙 Chế độ khuya >23:30 (Chăn rong biển)", self, checkable=True)
        act_night.setChecked(self.simulate_late_night)
        act_night.triggered.connect(self._toggle_sim_night)
        env_menu.addAction(act_night)

        # Đổi màu cá
        theme_menu = menu.addMenu("🎨 Đổi màu cá")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for name in FISH_THEMES:
            act = QAction(name, self, checkable=True)
            act.setChecked(name == self.theme_name)
            act.triggered.connect(lambda checked, n=name: self.set_theme(n))
            theme_group.addAction(act)
            theme_menu.addAction(act)

        menu.addSeparator()
        if sys.platform == "darwin":
            act_spaces = QAction("🖥️ Đi theo qua mọi Desktop / Full-Screen", self, checkable=True)
            act_spaces.setChecked(self.all_spaces_enabled)
            act_spaces.triggered.connect(self.set_all_spaces_enabled)
            menu.addAction(act_spaces)
        menu.addAction("🕶️ Lặn sâu ẩn mình (Ctrl+Shift+H)", self.toggle_boss_hide)
        menu.addAction("❌ Thoát", QApplication.quit)
        menu.exec(global_pos)

    def _trigger_menu_expr(self, key: str):
        if self.state in ("caged", "breaking_out"):
            return
        if self.state == "play_dead":
            self._wake_from_play_dead()
        self.set_expression(key, 150)

    def _toggle_sim_overload(self, checked: bool):
        self.simulate_overload = checked
        self._poll_slow_sensors()

    def _toggle_sim_night(self, checked: bool):
        self.simulate_late_night = checked
        self._poll_slow_sensors()

    def set_all_spaces_enabled(self, enabled: bool):
        """Bật/tắt chế độ đi theo qua mọi Desktop (Spaces) & Full-Screen trên macOS."""
        self.all_spaces_enabled = bool(enabled)
        set_widgets_all_spaces(self.all_spaces_enabled)
        apply_macos_all_spaces(self, self.all_spaces_enabled)
        for widget in (self.water_overlay, self.splash_overlay, self.falling_cage_overlay, self.pong_bubble):
            if widget is not None:
                apply_macos_all_spaces(widget, self.all_spaces_enabled)
        for f in self.foods:
            apply_macos_all_spaces(f, self.all_spaces_enabled)
        for b in self.clipboard_bubbles:
            apply_macos_all_spaces(b, self.all_spaces_enabled)

    def showEvent(self, e):
        super().showEvent(e)
        apply_macos_all_spaces(self, self.all_spaces_enabled)

    def closeEvent(self, e):
        self._clear_click_through()
        self.hotkey.stop()
        self.audio.stop()
        self.sound.cleanup()
        self.water_overlay.close()
        self.splash_overlay.close()
        self.falling_cage_overlay.close()
        if self.tray is not None:
            self.tray.hide()
        for f in list(self.foods):
            f.close()
        if self.pong_bubble is not None:
            self.pong_bubble.close()
        for b in list(self.clipboard_bubbles):
            b.close()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # để Boss Key ẩn cá xuống đáy không làm tắt app!
    configure_macos_app_for_spaces()      # cho phép Pet đi theo qua mọi Desktop (Spaces) & Full-Screen trên macOS
    pet = GoldenFishPet()
    pet.show()
    sys.exit(app.exec())
