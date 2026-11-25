"""Lớp điều phối chính GoldenFishPet(QWidget) kết nối vòng lặp 60 FPS, sự kiện Qt và các bộ điều khiển."""
from __future__ import annotations

import math
import os
import random
import time

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QCursor,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QWidget,
)

from pet.config import (
    CPU_PANIC_THRESHOLD,
    CURSOR_ATTENTION_RADIUS,
    DEFAULT_WORD_TOKENS,
    EYE_LERP_ALPHA,
    EYE_MAX_OFFSET_X,
    EYE_MAX_OFFSET_Y,
    FISH_THEMES,
    FPS,
    HUNGER_FILE_GAIN,
    HUNGER_REVIVE_LEVEL,
    HUNGER_TEXT_GAIN,
    HUNGER_WORD_GAIN,
    IDLE_SLEEP_SECS,
    MAX_CLIPBOARD_BUBBLES,
    SIZE,
    TURN_AROUND_FRAMES,
    URL_RE,
    HungerState,
    PetStateStore,
)
from pet.core.behaviors import dispatch_movement
from pet.core.hunger import HungerController
from pet.core.math_utils import angle_diff
from pet.core.particles import ParticleSystem
from pet.core.surfing import WindowSurfController
from pet.models import FishRenderState, Particle, TrackedWindow
from pet.platform import (
    GlobalHotkeyListener,
    WindowTracker,
    apply_macos_all_spaces,
    extract_dropped_paths,
    has_droppable_data,
    move_path_to_trash,
    permanently_delete_path,
)
from pet.rendering import render_fish
from pet.sensors import (
    AudioSpectrumMonitor,
    SoundPlayer,
    SystemPressureMonitor,
    WallpaperColorAnalyzer,
    is_late_night,
)
from pet.ui import create_tray_icon, show_context_menu
from pet.widgets import (
    ClipboardBubble,
    FallingCageOverlay,
    FishFood,
    ParticleFieldOverlay,
    SplashRippleOverlay,
    ThoughtBubbleOverlay,
    WaterOverlay,
    paste_or_open_clipboard_payload,
    set_widgets_all_spaces,
)


class GoldenFishPet(QWidget):
    """Linh vật Cá Vàng 2D điều phối các bộ điều khiển vật lý, độ đói, lướt cửa sổ và hiệu ứng."""

    def __init__(self, state_store: PetStateStore | None = None):
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

        # Hệ lò xo co giãn đàn hồi (Squash & Stretch)
        self.squash_x = 1.0
        self.squash_y = 1.0
        self._squash_vx = 0.0
        self._squash_vy = 0.0

        # Chiều sâu 3D
        self.depth = 0.65
        self.depth_target = 0.65
        self.dive_scale = 1.0

        # Trạng thái chính & biểu cảm
        self.state = "swim"
        self.target_x = self.px
        self.target_y = self.py
        self.retarget_ticks = 90
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

        # Nhảy sóng Porpoising & ngó trên thanh tiêu đề cửa sổ
        self.window_perch_enabled = True
        self._perch_wid: int = 0
        self._perch_rect: QRect | None = None
        self._perch_safe_min: float = 0.0
        self._perch_safe_max: float = 0.0
        self._perch_ticks = 0
        self._perch_dir = 1
        self._surf_phase = "approach"
        self._porpoise_arcs_left = 0
        self._porpoise_dip_ticks = 0
        self._porpoise_dive_ticks = 0
        self._surf_landed = False
        self._surf_balance_deg = 0.0
        self._surf_drag_ticks = 0
        self._surf_snap_cooldown = 0
        self._window_drop_ticks = 0
        self._click_through_active = False

        # Độ no / béo tròn & Bộ đếm biểu cảm đói/no/hồi sinh
        self.fullness = 0.0
        self.chubby_factor = 0.0
        self._chubby_ticks = 0
        self.full_shake_ticks = 0
        self.full_shake_total = int(1.5 * FPS)
        self.point_mouth_ticks = 0
        self.point_mouth_total = int(2.6 * FPS)
        self._point_mouth_cd = random.randint(6 * FPS, 10 * FPS)
        self._hover_beg_cd = 0
        self.revive_ticks = 0
        self.revive_total = int(1.5 * FPS)
        self._was_starved_dead_before_drag = False

        # Boss Key (Lặn sâu ẩn mình)
        self.boss_hidden = False
        self._saved_surface_y = self.py

        # Chế độ Lồng Giam (Cage Mode)
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
        self._bubble_cd = random.randint(60, 120)
        self._music_bubble_cd = 0
        self._dead_peek_cd = random.randint(5 * FPS, 9 * FPS)
        self._dead_peek_ticks = 0

        # Vuốt ve, spam click & kéo thả chuột trái
        self.pet_rub_energy = 0.0
        self.pet_love_streak = 0
        self.last_hover_pos: QPoint | None = None
        self.click_timestamps: list[float] = []
        self._press_global: QPoint | None = None
        self._drag_offset: QPoint | None = None
        self._last_drag_global: QPoint | None = None
        self._drag_vel_x = 0.0
        self._drag_vel_y = 0.0

        # Theo dõi chuột & nhìn 3 lớp
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
        self.particle_overlay = ParticleFieldOverlay()
        self.thought_bubble = ThoughtBubbleOverlay()

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
        self.clipboard_bubbles: list[ClipboardBubble] = []
        self.particles: list[Particle] = []

        # Các bộ điều khiển chuyên biệt (Domain Controllers)
        self.particle_sys = ParticleSystem(self)
        self.surfing = WindowSurfController(self)
        self.hunger_ctrl = HungerController(self, store=state_store)

        # Clipboard listener & Phím tắt toàn cục / System Tray
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)
        self.hotkey = GlobalHotkeyListener()
        self.hotkey.triggered.connect(self.toggle_boss_hide)
        self.hotkey.cage_triggered.connect(self.toggle_cage_mode)
        self._local_boss_shortcut = QShortcut(QKeySequence("Ctrl+Shift+H"), self)
        self._local_boss_shortcut.activated.connect(self.toggle_boss_hide)
        self._local_cage_shortcut = QShortcut(QKeySequence("Ctrl+Esc"), self)
        self._local_cage_shortcut.activated.connect(self.toggle_cage_mode)
        self.tray = create_tray_icon(self)

        self.move(int(self.px), int(self.py))
        self._pick_new_swim_target()

        # Vòng lặp chính 60 FPS & bộ đếm cảm biến định kỳ
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000 // FPS)

        self.sensor_timer = QTimer(self)
        self.sensor_timer.timeout.connect(self._poll_slow_sensors)
        self.sensor_timer.start(1800)

        self.wallpaper_timer = QTimer(self)
        self.wallpaper_timer.timeout.connect(self._poll_wallpaper)
        self.wallpaper_timer.start(3200)
        QTimer.singleShot(700, self._poll_wallpaper)
        QTimer.singleShot(500, self._poll_slow_sensors)

        if self.hunger <= 0.0:
            self.enter_starved_dead()
        else:
            self.set_expression("happy", 90)
            for _ in range(4):
                self.spawn_particle("bubble")

    # ---------- Thuộc tính & Ủy quyền bộ điều khiển ----------
    @property
    def hunger(self) -> float:
        return self.hunger_ctrl.value

    @hunger.setter
    def hunger(self, value: float) -> None:
        self.hunger_ctrl.value = max(0.0, min(100.0, float(value)))

    @property
    def hunger_state(self) -> HungerState:
        return self.hunger_ctrl.state

    @property
    def is_full(self) -> bool:
        return self.hunger_ctrl.is_full

    def set_hunger_preset(self, value: float) -> None:
        self.hunger_ctrl.set_preset(value)

    def enter_starved_dead(self) -> None:
        self.hunger_ctrl.enter_starved_dead()

    def trigger_shake_head_full(self) -> None:
        self.hunger_ctrl.trigger_shake_head_full()

    def trigger_point_to_mouth(self) -> None:
        self.hunger_ctrl.trigger_point_to_mouth()

    def emergency_feed(self) -> None:
        self.hunger_ctrl.emergency_feed()

    def trigger_window_perch(self, mode: str | None = None) -> bool:
        return self.surfing.trigger_perch(mode)

    def spawn_particle(self, kind: str, x: float | None = None, y: float | None = None) -> None:
        self.particle_sys.spawn(kind, x, y)

    # ---------- Hình học & Tiện ích ----------
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

    def impulse_squash(self, target_sx: float, target_sy: float) -> None:
        self.squash_x = target_sx
        self.squash_y = target_sy
        self._squash_vx = (target_sx - 1.0) * 0.22
        self._squash_vy = (target_sy - 1.0) * 0.22

    def _set_direction(self, new_dir: int, smooth: bool = True) -> None:
        if new_dir not in (-1, 1) or new_dir == self.direction:
            return
        if smooth and self.state not in ("caged", "breaking_out", "puffed", "play_dead", "dive_hide", "hidden"):
            self._turn_from_dir = self.direction
            self._turn_ticks = TURN_AROUND_FRAMES
        self.direction = new_dir

    def _update_cursor_eye_tracking(self, cur: QPoint) -> None:
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
            norm_e = math.hypot(target_px / EYE_MAX_OFFSET_X, target_py / EYE_MAX_OFFSET_Y)
            if norm_e > 1.0:
                target_px /= norm_e
                target_py /= norm_e
            self.pupil_x += (target_px - self.pupil_x) * EYE_LERP_ALPHA
            self.pupil_y += (target_py - self.pupil_y) * EYE_LERP_ALPHA
        else:
            self.pupil_x *= 0.85
            self.pupil_y *= 0.85
            if abs(self.pupil_x) < 0.03:
                self.pupil_x = 0.0
            if abs(self.pupil_y) < 0.03:
                self.pupil_y = 0.0

    # ---------- Biểu cảm ----------
    def set_expression(self, expr: str, duration_ticks: int = 120) -> None:
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
            for _ in range(4):
                self.spawn_particle("dizzy_star")

    def active_expression(self) -> str:
        st = self.state
        if st == "starved_dead":
            return "starved_dead"
        if st == "revive":
            return "happy" if self.revive_ticks > 35 else "love"
        if st == "shake_head_full":
            return "full_shake"
        if st == "point_to_mouth":
            return "hungry_beg"
        if st == "caged":
            return "pleading" if self.cage_plead_ticks > 0 else "caged_sad"
        if st == "breaking_out":
            return "proud" if self.cage_break_released else "muscle_strain"
        if st in ("play_dead", "puffed", "belly_up", "sneeze_windup", "sneeze_burst"):
            return st
        if st in ("deflate_zoom", "dive_hide", "drag"):
            return "panic"
        if st == "surface_show":
            return "excited"
        if st in ("swallow_ready", "swallow_gulp"):
            return "swallow"
        if st in ("eat", "eat_file"):
            return "eat"
        if st == "nauseous_vomit":
            return "nauseous"
        if st == "celebrate_fig8":
            return "proud"
        if st == "window_peek":
            return "peeking"
        if st == "window_surf":
            if self._surf_drag_ticks > 0:
                return "surprised"
            if self._surf_phase == "arc":
                return "happy"
        if st == "window_drop":
            return "surprised"
        if self.is_overloaded:
            return "panic"
        if self.foods:
            return "excited"
        if self.expression_ticks > 0:
            return self.expression
        if self.is_night_mode:
            return "sleepy"
        if self.current_color_score < -0.32 and self.wallpaper_aware:
            return "cautious"
        return "normal"

    # ---------- Cảm biến định kỳ ----------
    def _poll_slow_sensors(self) -> None:
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

    def _poll_wallpaper(self) -> None:
        if not self.wallpaper_aware or self.boss_hidden:
            return
        self.wallpaper.sample(exclude_rect=QRect(int(self.px), int(self.py), SIZE, SIZE))

    # ---------- Hành động & Vi biểu cảm ----------
    def trigger_pufferfish(self) -> None:
        if self.state in ("caged", "breaking_out", "starved_dead") or self.hunger_state == HungerState.DEAD:
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

    def trigger_nauseous_rainbow(self) -> None:
        if self.state in ("caged", "breaking_out", "starved_dead") or self.hunger_state == HungerState.DEAD:
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
        for _ in range(4):
            self.spawn_particle("rainbow_bubble")

    def trigger_sneeze(self) -> None:
        if (
            self.state
            in (
                "drag", "puffed", "deflate_zoom", "dive_hide", "hidden",
                "swallow_ready", "swallow_gulp", "caged", "breaking_out",
                "starved_dead", "shake_head_full", "revive",
            )
            or self.hunger_state == HungerState.DEAD
        ):
            return
        if self.state == "play_dead":
            self._wake_from_play_dead()
        self.state = "sneeze_windup"
        self.sneeze_ticks = 38
        self.facing_front = False
        self.vx *= 0.15
        self.vy *= 0.15

    def trigger_celebrate_figure8(self) -> None:
        if (
            self.state in ("drag", "dive_hide", "hidden", "puffed", "caged", "breaking_out", "starved_dead", "revive")
            or self.hunger_state == HungerState.DEAD
        ):
            return
        self.state = "celebrate_fig8"
        self.fig8_total = int(3.0 * FPS)
        self.fig8_ticks = self.fig8_total
        self.fig8_origin = (self.px, self.py)
        self.facing_front = False
        for _ in range(5):
            self.spawn_particle("star")

    def trigger_backflip(self) -> None:
        if (
            self.state
            in (
                "puffed", "play_dead", "drag", "dive_hide", "hidden",
                "caged", "breaking_out", "starved_dead", "shake_head_full", "revive",
            )
            or self.hunger_state == HungerState.DEAD
        ):
            return
        if self.backflip_remaining <= 10.0:
            self.backflip_remaining = 360.0
            self.impulse_squash(0.84, 1.20)
            for _ in range(3):
                self.spawn_particle("star")

    def enter_play_dead(self) -> None:
        if self.state in ("caged", "breaking_out", "starved_dead") or self.hunger_state == HungerState.DEAD:
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
        self.target_x = max(screen.left() + 26.0, min(screen.right() - SIZE - 26.0, self.px))
        self.target_y = float(screen.top() + 26)
        self._dead_peek_cd = random.randint(5 * FPS, 9 * FPS)
        self._dead_peek_ticks = 0
        self.sound.play_pop()
        self.spawn_particle("ghost")
        for _ in range(3):
            self.spawn_particle("bubble")

    def _wake_from_play_dead(self) -> None:
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

    # ---------- Lồng Giam (Cage Mode) & Boss Key ----------
    def toggle_cage_mode(self) -> None:
        if self.boss_hidden or self.state in ("dive_hide", "hidden", "surface_show", "breaking_out", "starved_dead", "revive"):
            return
        if self.state == "caged":
            self.start_cage_breakout()
        else:
            self.enter_cage_mode()

    def enter_cage_mode(self) -> None:
        self._last_user_activity = time.monotonic()
        self.surfing.clear_click_through()
        self.falling_cage_overlay.stop()
        self.state = "caged"
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

    def start_cage_breakout(self) -> None:
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

    def toggle_boss_hide(self) -> None:
        if self.state in ("dive_hide", "surface_show"):
            return
        if not self.boss_hidden:
            self.surfing.clear_click_through()
            self.boss_hidden = True
            self._saved_surface_y = self.py
            self.state = "dive_hide"
            self.cage_dragging = False
            self.cage_plead_ticks = 0
            self.cage_bend_amount = 0.0
            self.cage_muscular = 0.0
            self.falling_cage_overlay.stop()
            self.particle_overlay.clear_all()
            self.thought_bubble.dismiss()
            self.facing_front = False
            self.puff_factor = 0.0
            self.vx = 0.0
            self.vy = 14.0
            self.spawn_particle("excl")
            self.impulse_squash(0.76, 1.32)
            if self.water_overlay.active:
                self.water_overlay.hide()
            for b in self.clipboard_bubbles:
                b.hide()
            for f in self.foods:
                f.hide()
        else:
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

    # ---------- Ký tự, Pomodoro, Giao diện, Clipboard ----------
    def spawn_word_food(self, words: list[str] | None = None) -> None:
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

    def prompt_custom_word_food(self) -> None:
        text, ok = QInputDialog.getText(
            self,
            "Cho Cá Vàng ăn chữ",
            "Nhập các từ khóa / ký tự cách nhau bằng dấu cách:",
            text="Cá Vàng 2026 OK",
        )
        if ok and text.strip():
            words = [w for w in text.strip().split() if w][:10]
            if words:
                self.spawn_word_food(words)

    def _on_ate_morsel(self) -> None:
        self.fullness = min(10.0, self.fullness + 1.0)
        if self.fullness >= 4.0:
            self._chubby_ticks = 120 * FPS
        if self.hunger_state != HungerState.DEAD:
            self.hunger_ctrl.apply_delta(HUNGER_WORD_GAIN, save_now=True)
        self.impulse_squash(1.20, 0.85)
        self.sound.play_pop()
        for _ in range(4):
            self.spawn_particle("bubble")

    def start_pomodoro(self, focus_secs: int, break_secs: int) -> None:
        if self.boss_hidden:
            self.toggle_boss_hide()
        if self.state == "play_dead":
            self._wake_from_play_dead()
        self.water_overlay.start_pomodoro(focus_secs, break_secs)
        self.set_expression("excited", 80)

    def stop_pomodoro(self) -> None:
        self.water_overlay.stop_pomodoro()

    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.theme = FISH_THEMES[name]
        self.set_expression("happy", 70)
        for _ in range(4):
            self.spawn_particle("star")
        self.update()

    def _on_clipboard_changed(self) -> None:
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
        bubble = ClipboardBubble(
            kind=kind,
            payload=payload,
            start_x=cx + self.direction * 36 - ClipboardBubble.BUBBLE_SIZE / 2,
            start_y=cy - 28,
            on_activate=self._on_bubble_activate,
            on_closed=self._on_bubble_closed,
        )
        self.clipboard_bubbles.append(bubble)
        while len(self.clipboard_bubbles) > MAX_CLIPBOARD_BUBBLES:
            self.clipboard_bubbles.pop(0).trigger_pop(activate=False)

        self.impulse_squash(1.14, 0.88)
        self.spawn_particle("bubble")
        if self.state == "swim":
            self.set_expression("happy", 55)

    def _on_bubble_activate(self, bubble: ClipboardBubble) -> None:
        self.sound.play_pop()
        self._ignore_clipboard_until = time.monotonic() + 0.6
        paste_or_open_clipboard_payload(bubble.kind, bubble.payload)
        self.trigger_celebrate_figure8()

    def _on_bubble_closed(self, bubble: ClipboardBubble) -> None:
        if bubble in self.clipboard_bubbles:
            self.clipboard_bubbles.remove(bubble)

    def clear_clipboard_bubbles(self) -> None:
        for b in list(self.clipboard_bubbles):
            b.trigger_pop(activate=False)

    # ---------- Kéo file vào miệng cá (Living Recycle Bin) ----------
    @staticmethod
    def _accept_drag_action(e) -> None:
        if e.possibleActions() & Qt.DropAction.CopyAction:
            e.setDropAction(Qt.DropAction.CopyAction)
            e.accept()
        else:
            e.acceptProposedAction()

    def _move_to_trash(self, path: str) -> bool:
        return move_path_to_trash(path)

    def _delete_permanently(self, path: str) -> bool:
        return permanently_delete_path(path)

    def _aim_mouth_at(self, local_pos: QPoint) -> None:
        self.facing_front = False
        dx = local_pos.x() - SIZE / 2.0
        dy = local_pos.y() - (SIZE / 2.0 + 4.0)
        if abs(dx) > 6.0:
            self.direction = 1 if dx > 0 else -1
        self.pitch_deg = max(-24.0, min(24.0, (dy / 70.0) * 20.0 * self.direction))
        mx, my = self._mouth_local_pos()
        self.mouth_locked = math.hypot(local_pos.x() - mx, local_pos.y() - my) <= 68.0

    def dragEnterEvent(self, e) -> None:
        if self.state in ("caged", "breaking_out"):
            e.ignore()
            return
        md = e.mimeData()
        if not has_droppable_data(md):
            e.ignore()
            return

        self._last_user_activity = time.monotonic()
        if self.is_full and self.hunger_state != HungerState.DEAD:
            e.ignore()
            if self.state != "shake_head_full":
                self.trigger_shake_head_full()
            return

        self._accept_drag_action(e)
        self._drag_leave_grace = 0
        self.thought_bubble.dismiss()
        if self.state == "play_dead":
            self._wake_from_play_dead()
        was_hungry = self.hunger_state in (HungerState.HUNGRY, HungerState.STARVING)
        self._was_starved_dead_before_drag = (
            self.state == "starved_dead" or self.hunger_state == HungerState.DEAD
        )
        self.state = "swallow_ready"
        self.vx = 0.0
        self.vy = 0.0
        self._aim_mouth_at(e.position().toPoint())
        self.suction_alpha = 1.0
        if was_hungry:
            self.impulse_squash(1.16, 0.86)
            self.spawn_particle("excl")
            self.spawn_particle("star")
        self.update()

    def dragMoveEvent(self, e) -> None:
        if not has_droppable_data(e.mimeData()):
            e.ignore()
            return
        if self.is_full and self.hunger_state != HungerState.DEAD:
            e.ignore()
            if self.state != "shake_head_full":
                self.trigger_shake_head_full()
            return
        self._drag_leave_grace = 0
        self.state = "swallow_ready"
        self._aim_mouth_at(e.position().toPoint())
        if self.hunger_state in (HungerState.HUNGRY, HungerState.STARVING):
            gpos = e.globalPosition().toPoint()
            fcx, fcy = self.center_global()
            dx, dy = gpos.x() - fcx, gpos.y() - fcy
            if math.hypot(dx, dy) > 26.0:
                bounds = self.virtual_rect()
                self.px = max(bounds.left() + 6.0, min(bounds.right() - SIZE - 6.0, self.px + dx * 0.08))
                self.py = max(bounds.top() + 8.0, min(bounds.bottom() - SIZE - 4.0, self.py + dy * 0.08))
                self.move(int(self.px), int(self.py))
        self.suction_alpha = 1.0
        self._accept_drag_action(e)
        self.update()

    def dragLeaveEvent(self, _) -> None:
        if self.state == "swallow_ready":
            self._drag_leave_grace = 18
            self.mouth_locked = False

    def dropEvent(self, e) -> None:
        md = e.mimeData()
        drop_pos = e.position().toPoint()
        self._drag_leave_grace = 0
        self.mouth_locked = False

        if self.is_full and self.hunger_state != HungerState.DEAD:
            e.ignore()
            self.suction_alpha = 0.0
            self.trigger_shake_head_full()
            return

        paths = extract_dropped_paths(md)
        if paths:
            self._accept_drag_action(e)
            self._eat_paths(paths, (float(drop_pos.x()), float(drop_pos.y())))
            return

        if md.hasText() and md.text().strip():
            self._accept_drag_action(e)
            was_dead = (self.hunger_state == HungerState.DEAD) or self._was_starved_dead_before_drag
            self._was_starved_dead_before_drag = False
            if was_dead:
                self.hunger_ctrl.revive(HUNGER_REVIVE_LEVEL)
            else:
                self.hunger_ctrl.apply_delta(HUNGER_TEXT_GAIN, save_now=True)
                self._start_eat_animation((float(drop_pos.x()), float(drop_pos.y())), is_dir=False)
            return

        e.ignore()
        if self.hunger_state == HungerState.DEAD:
            self.enter_starved_dead()
        else:
            self.state = "swim"
        self.suction_alpha = 0.0

    def _eat_paths(self, paths: list[str], drop_pos: tuple[float, float]) -> None:
        if not paths:
            self.state = "starved_dead" if self.hunger_state == HungerState.DEAD else "swim"
            self.suction_alpha = 0.0
            return

        if self.is_full and self.hunger_state != HungerState.DEAD:
            self.suction_alpha = 0.0
            self.trigger_shake_head_full()
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
                self.state = "starved_dead" if self.hunger_state == HungerState.DEAD else "swim"
                self.suction_alpha = 0.0
                return

        deleted: list[str] = []
        failed: list[str] = []
        first_is_dir = os.path.isdir(paths[0])
        was_dead = (self.hunger_state == HungerState.DEAD) or self._was_starved_dead_before_drag
        self._was_starved_dead_before_drag = False

        for path in paths:
            ok = self._delete_permanently(path) if self.delete_mode == "permanent" else self._move_to_trash(path)
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
                    if self._delete_permanently(path):
                        deleted.append(path)
                        print(f"[Cá Vàng] Đã ăn & xóa vĩnh viễn: {path}", flush=True)

        if deleted:
            if was_dead:
                self.hunger_ctrl.revive(HUNGER_REVIVE_LEVEL)
            else:
                self.hunger_ctrl.apply_delta(HUNGER_FILE_GAIN * len(deleted), save_now=True)
                if self.is_full:
                    self.chubby_factor = max(self.chubby_factor, 0.55)
                    self._chubby_ticks = max(self._chubby_ticks, 90 * FPS)
                self._start_eat_animation(drop_pos, is_dir=first_is_dir)
        else:
            self.state = "starved_dead" if was_dead else "swim"
            self.suction_alpha = 0.0
            if not was_dead:
                self.set_expression("grumpy", 60)

    def _start_eat_animation(self, start_pos: tuple[float, float], is_dir: bool = False) -> None:
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

    def pick_files_to_eat(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn file cho Cá Vàng ăn",
            os.path.expanduser("~"),
        )
        if files:
            mx, my = self._mouth_local_pos()
            self._eat_paths(files, (mx + self.direction * 46.0, my - 10.0))

    # ---------- Vòng lặp chính 60 FPS ----------
    def tick(self) -> None:
        if self.state == "hidden":
            return

        self.frame += 1
        dt = 1.0 / FPS
        now = time.monotonic()
        bounds = self.virtual_rect()

        # 1. Pomodoro Mực Nước
        if self.water_overlay.active and not self.boss_hidden:
            transition = self.water_overlay.step(dt)
            if transition == "enter_break":
                self.set_expression("happy", 140)
                for _ in range(8):
                    self.spawn_particle("bubble")
            elif transition == "enter_focus":
                self.set_expression("excited", 90)

        # 2. Âm thanh (Equalizer + Bass Drop Backflip)
        self.audio_level, self.audio_bands, bass_drop = self.audio.poll()
        if bass_drop and not self.boss_hidden:
            self.trigger_backflip()

        # 3. Chuột, Idle, Độ Đói, Cursor Wake & Hắt xì
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

        if (
            self.state == "swim"
            and self.hunger_state != HungerState.DEAD
            and not self.hold_still
            and not self.is_overloaded
            and not self.water_overlay.active
            and (now - self._last_user_activity) >= IDLE_SLEEP_SECS
        ):
            self.enter_play_dead()

        self.hunger_ctrl.tick(now, cur, cursor_speed)

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
                self._wake_cooldown = 44
                self._vortex_timestamps = [t for t in self._vortex_timestamps if (now - t) <= 5.0]
                self._vortex_timestamps.append(now)
                if len(self._vortex_timestamps) >= 3:
                    self._vortex_timestamps.clear()
                    self.trigger_nauseous_rainbow()
                else:
                    self.state = "swim"
                    self.vortex_alpha = 1.0
                    self.spin_vel = 22.0 if cdx >= 0 else -22.0
                    self.vx += max(-7.0, min(7.0, cdx * 0.12))
                    self.vy += max(-7.0, min(7.0, cdy * 0.12))
                    self.impulse_squash(0.84, 1.18)
                    self.set_expression("dizzy", 105)
                    for _ in range(7):
                        self.spawn_particle("dizzy_bubble")

        if self.state == "swim" and not self.is_overloaded and not self.foods and not self.hold_still:
            self._sneeze_cd -= 1
            if self._sneeze_cd <= 0:
                self._sneeze_cd = random.randint(30 * FPS, 55 * FPS)
                self.trigger_sneeze()

        # 4. Thức ăn ký tự, bong bóng Clipboard & độ béo tròn
        alive_foods: list[FishFood] = []
        for f in self.foods:
            if f is self._eating_food or f.step():
                alive_foods.append(f)
            else:
                f.close()
        self.foods = alive_foods

        for b in list(self.clipboard_bubbles):
            b.step(bounds)

        if self._chubby_ticks > 0:
            self._chubby_ticks -= 1
            target_chubby = min(1.0, (self.fullness - 3.0) / 5.0)
            self.chubby_factor += (target_chubby - self.chubby_factor) * 0.03
            if self._chubby_ticks == 0:
                self.fullness = 0.0
        else:
            self.chubby_factor = max(0.0, self.chubby_factor - 0.005)

        # 5. Điều phối chuyển động theo trạng thái (State Dispatch Table)
        dispatch_movement(self, bounds, cur)

        # 6. Ánh mắt 3 lớp, quay đầu & click-through thanh tiêu đề
        self._update_cursor_eye_tracking(cur)
        if self._turn_ticks > 0:
            self._turn_ticks -= 1
        if self._surf_snap_cooldown > 0:
            self._surf_snap_cooldown -= 1
        self.surfing.update_click_through(cur)

        # 7. Banking, Squash-Stretch & nhịp vẫy đuôi
        spd_now = math.hypot(self.vx, self.vy)
        if spd_now > 0.6 and self.state in ("swim", "celebrate_fig8", "deflate_zoom", "window_surf"):
            heading = math.atan2(self.vy, self.vx)
            turn_rate = angle_diff(self._prev_heading, heading)
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

        tail_rate = 0.09 + min(1.0, spd_now / 5.5) * 0.24
        if self.hunger_state == HungerState.HUNGRY:
            tail_rate *= 0.55
        elif self.hunger_state == HungerState.STARVING:
            tail_rate *= 0.30
        elif self.hunger_state == HungerState.DEAD:
            tail_rate *= 0.15
        self.tail_phase += tail_rate

        if spd_now > 3.5 and self.frame % 3 == 0 and self.state not in ("drag", "dive_hide"):
            self.spawn_particle("trail_bubble")

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

        if self.backflip_remaining > 0.0:
            step_rot = min(self.backflip_remaining, 18.0)
            self.backflip_remaining -= step_rot
            self.spin_deg += step_rot * (-self.direction)
            if self.backflip_remaining <= 0.0:
                self.spin_deg = 0.0
        elif self.state != "revive":
            self.spin_deg += self.spin_vel
            self.spin_vel *= 0.92
            if abs(self.spin_vel) < 0.4:
                self.spin_vel = 0.0
                norm = ((self.spin_deg + 180.0) % 360.0) - 180.0
                self.spin_deg = norm * 0.85
                if abs(self.spin_deg) < 0.5:
                    self.spin_deg = 0.0

        self.depth += (self.depth_target - self.depth) * 0.016

        # 8. Cập nhật hạt hiệu ứng & bong bóng tự nhiên
        self.particle_sys.update()

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

        if self.state not in ("dive_hide", "hidden"):
            self._bubble_cd -= 1
            if self._bubble_cd <= 0:
                if expr in ("sleepy", "caged_sad") and random.random() < 0.45:
                    mx, my = self._mouth_local_pos()
                    for _ in range(random.randint(2, 3)):
                        self.spawn_particle("bubble", mx + random.uniform(-4, 4), my + random.uniform(-3, 3))
                else:
                    self.spawn_particle("bubble")
                self._bubble_cd = random.randint(28, 52) if spd_now > 2.6 else random.randint(60, 120)

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
        if not self.boss_hidden:
            self.thought_bubble.follow(self.px + SIZE / 2.0, self.py + 28.0)
        self.update()

    # ---------- Giới hạn biên & Chọn điểm bơi ----------
    def _apply_bounds(self, min_x: float, max_x: float, min_y: float, max_y: float, bouncy: bool = True) -> None:
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

    def _pick_new_swim_target(self, min_y: float | None = None, fast: bool = False) -> None:
        if (
            not fast
            and self.window_perch_enabled
            and not self.water_overlay.active
            and not self.is_night_mode
            and self.open_windows
            and random.random() < 0.28
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
        if self.state in ("play_dead", "dive_hide", "hidden", "window_peek", "caged", "breaking_out"):
            return 0.0, 0.0
        if self.state == "window_surf" and self._surf_landed:
            return 0.0, 0.0
        depth_scale = (0.85 + 0.25 * max(0.0, min(1.0, self.depth))) * max(0.15, self.dive_scale)
        fcx = self.px + SIZE / 2.0
        belly_y = self.py + SIZE / 2.0 + 4.0 + (32.0 + 14.0 * self.puff_factor + 4.0 * self.chubby_factor) * depth_scale
        max_range = 92.0

        best_gap: float | None = None
        best_surf_y = 0.0
        bounds = self.virtual_rect()
        floor_y = bounds.bottom() - 42.0
        gap_bot = floor_y - belly_y
        if -24.0 <= gap_bot <= max_range:
            best_gap = gap_bot
            best_surf_y = floor_y + 14.0

        candidates = list(self.open_windows)
        if self._perch_rect is not None and self._perch_rect not in candidates:
            candidates.append(self._perch_rect)
        for win in candidates:
            if (win.left() - 18) <= fcx <= (win.right() + 18):
                gap_win = win.top() - belly_y
                if -16.0 <= gap_win <= max_range and (best_gap is None or gap_win < best_gap):
                    best_gap = gap_win
                    best_surf_y = float(win.top())

        if best_gap is None:
            return 0.0, 0.0
        prox = max(0.0, min(1.0, 1.0 - max(0.0, best_gap) / max_range))
        return prox, best_surf_y - self.py

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        cur = QCursor.pos()
        fcx, fcy = self.center_global()
        dx_c = cur.x() - fcx
        dy_c = cur.y() - fcy
        dist_c = math.hypot(dx_c, dy_c)
        look_dx, look_dy = 0.0, 0.0
        eye_range_ok = (dist_c > 1.0) if self.state == "caged" else (1.0 < dist_c < 380.0)
        if eye_range_ok:
            raw_x = dx_c / dist_c
            raw_y = dy_c / dist_c
            look_dx = -raw_x if self.direction > 0 else raw_x
            look_dy = raw_y

        spd_norm = min(1.0, math.hypot(self.vx, self.vy) / 4.8)
        cage_mode = (
            "caged" if self.state == "caged"
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
            full_shake_t=((self.full_shake_total - self.full_shake_ticks) / FPS) if self.state == "shake_head_full" else -1.0,
            point_to_mouth=(min(1.0, self.point_mouth_ticks / 12.0) if self.state == "point_to_mouth" else 0.0),
            starved_dead=(self.state == "starved_dead"),
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

    def mousePressEvent(self, e) -> None:
        self._last_user_activity = time.monotonic()
        if e.button() == Qt.MouseButton.LeftButton:
            if self.state in ("breaking_out", "starved_dead", "revive"):
                if self.state == "starved_dead":
                    self.thought_bubble.show_trash_icon(110)
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
            show_context_menu(self, e.globalPosition().toPoint())

    def mouseMoveEvent(self, e) -> None:
        pos = e.position().toPoint()
        self._last_user_activity = time.monotonic()

        if (e.buttons() & Qt.MouseButton.LeftButton) and self._press_global is not None:
            gpos = e.globalPosition().toPoint()
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

    def leaveEvent(self, _) -> None:
        self.last_hover_pos = None

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            if self.state == "caged":
                if self.cage_dragging:
                    self.cage_dragging = False
                    self.vx = 0.0
                    self.vy = 0.0
                    self.cage_swing_vel = max(-2.5, min(2.5, -self._drag_vel_x * 0.14))
                elif self._press_global is not None:
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

    # ---------- Hỗ trợ menu & vòng đời cửa sổ ----------
    def _trigger_menu_expr(self, key: str) -> None:
        if self.state in ("caged", "breaking_out"):
            return
        if self.state == "play_dead":
            self._wake_from_play_dead()
        self.set_expression(key, 150)

    def _toggle_sim_overload(self, checked: bool) -> None:
        self.simulate_overload = checked
        self._poll_slow_sensors()

    def _toggle_sim_night(self, checked: bool) -> None:
        self.simulate_late_night = checked
        self._poll_slow_sensors()

    def set_all_spaces_enabled(self, enabled: bool) -> None:
        self.all_spaces_enabled = bool(enabled)
        set_widgets_all_spaces(self.all_spaces_enabled)
        apply_macos_all_spaces(self, self.all_spaces_enabled)
        for widget in (
            self.water_overlay,
            self.splash_overlay,
            self.falling_cage_overlay,
            self.particle_overlay,
            self.thought_bubble,
        ):
            if widget is not None:
                apply_macos_all_spaces(widget, self.all_spaces_enabled)
        for f in self.foods:
            apply_macos_all_spaces(f, self.all_spaces_enabled)
        for b in self.clipboard_bubbles:
            apply_macos_all_spaces(b, self.all_spaces_enabled)

    def showEvent(self, e) -> None:
        super().showEvent(e)
        apply_macos_all_spaces(self, self.all_spaces_enabled)

    def closeEvent(self, e) -> None:
        self.hunger_ctrl.save()
        self.surfing.clear_click_through()
        self.hotkey.stop()
        self.audio.stop()
        self.sound.cleanup()
        self.water_overlay.close()
        self.splash_overlay.close()
        self.falling_cage_overlay.close()
        self.particle_overlay.close()
        self.thought_bubble.close()
        if self.tray is not None:
            self.tray.hide()
        for f in list(self.foods):
            f.close()
        for b in list(self.clipboard_bubbles):
            b.close()
        super().closeEvent(e)
