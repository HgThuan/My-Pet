"""Xây dựng System Tray Icon và Menu chuột phải cho Golden Fish Pet."""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from pet.config import EXPRESSIONS_MENU, FISH_THEMES, HungerState

if TYPE_CHECKING:
    from pet.core.pet import GoldenFishPet


def create_tray_icon(pet: GoldenFishPet) -> QSystemTrayIcon | None:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
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

    tray = QSystemTrayIcon(QIcon(pm), pet)
    tray.setToolTip("Cá Vàng Desktop Pet (Ctrl+Esc: Lồng giam | Ctrl+Shift+H: Ẩn/Hiện)")
    tmenu = QMenu()
    tmenu.addAction("🔒 Lồng giam / Phá lồng (Ctrl+Esc)", pet.toggle_cage_mode)
    tmenu.addAction("🕶️ Lặn / Ngoi lên (Ctrl+Shift+H)", pet.toggle_boss_hide)
    tmenu.addAction("🔤 Thả mưa Ký tự cho cá ăn", lambda: pet.spawn_word_food())
    tmenu.addSeparator()
    tmenu.addAction("❌ Thoát", QApplication.quit)
    tray.setContextMenu(tmenu)
    tray.activated.connect(
        lambda reason: pet.toggle_boss_hide()
        if reason == QSystemTrayIcon.ActivationReason.Trigger
        else None
    )
    tray.show()
    return tray


def show_context_menu(pet: GoldenFishPet, global_pos: QPoint) -> None:
    menu = QMenu(pet)

    # Thanh hiển thị Độ no & Cho ăn khẩn cấp
    h_val = int(round(pet.hunger))
    filled = max(0, min(10, int(round(pet.hunger / 10.0))))
    bar = "█" * filled + "░" * (10 - filled)
    hs = pet.hunger_state
    if hs == HungerState.DEAD:
        status_txt = "Chết đói 💀"
    elif hs == HungerState.STARVING:
        status_txt = "Rất đói!"
    elif hs == HungerState.HUNGRY:
        status_txt = "Đói bụng"
    elif pet.is_full:
        status_txt = "No căng!"
    else:
        status_txt = "Bình thường"

    act_hunger_info = menu.addAction(f"🍖 Độ no: {h_val}% [{bar}] ({status_txt})")
    act_hunger_info.setEnabled(False)

    em_label = "💖 Hồi sinh cá (Cho ăn khẩn cấp)" if hs == HungerState.DEAD else "🍖 Cho ăn khẩn cấp (+34%)"
    menu.addAction(em_label, pet.emergency_feed)

    hunger_test = menu.addMenu("🧪 Thử mức độ đói")
    hunger_test.addAction("100% — No căng (Lắc đầu từ chối)", lambda: pet.set_hunger_preset(100.0))
    hunger_test.addAction("80% — Bình thường", lambda: pet.set_hunger_preset(80.0))
    hunger_test.addAction("30% — Đói bụng (Chỉ miệng đòi ăn)", lambda: pet.set_hunger_preset(30.0))
    hunger_test.addAction("10% — Rất đói (Chìm đáy + nghĩ thùng rác)", lambda: pet.set_hunger_preset(10.0))
    hunger_test.addAction("0% — Chết đói (Ngửa bụng nổi đỉnh)", lambda: pet.set_hunger_preset(0.0))
    menu.addSeparator()

    # Chế độ Lồng Giam (Cage Mode - Ctrl+Esc)
    cage_label = "💪 Phá lồng thả tự do (Ctrl+Esc)" if pet.state == "caged" else "🔒 Giam vào lồng sắt (Ctrl+Esc)"
    act_cage = menu.addAction(cage_label, pet.toggle_cage_mode)
    act_cage.setEnabled(pet.state not in ("breaking_out", "starved_dead"))
    menu.addSeparator()

    # Cho ăn (Ký tự / Từ khóa)
    feed_menu = menu.addMenu("🔤 Cho ăn Ký tự")
    feed_menu.addAction("🔤 Thả mưa Ký tự / Code & Emoji", lambda: pet.spawn_word_food())
    feed_menu.addAction("✏️ Nhập chữ cho cá ăn...", pet.prompt_custom_word_food)

    # Kéo thả ăn & xóa file
    eat_file_menu = menu.addMenu("🗑️ Ăn & Xóa file (Kéo vào miệng)")
    act_hold = QAction("🧲 Đứng yên tại chỗ (Dễ kéo file vào miệng)", pet, checkable=True)
    act_hold.setChecked(pet.hold_still)
    act_hold.triggered.connect(lambda c: setattr(pet, "hold_still", c))
    eat_file_menu.addAction(act_hold)
    eat_file_menu.addAction("📂 Chọn file cho cá ăn...", pet.pick_files_to_eat)
    eat_file_menu.addSeparator()
    del_group = QActionGroup(pet)
    del_group.setExclusive(True)
    for mode_key, label in (
        ("trash", "♻️ Chuyển vào Thùng rác (An toàn)"),
        ("permanent", "🔥 Xóa vĩnh viễn (Hỏi xác nhận)"),
    ):
        act = QAction(label, pet, checkable=True)
        act.setChecked(pet.delete_mode == mode_key)
        act.triggered.connect(lambda checked, m=mode_key: setattr(pet, "delete_mode", m))
        del_group.addAction(act)
        eat_file_menu.addAction(act)

    # Đậu / Lướt thanh tiêu đề cửa sổ
    win_menu = menu.addMenu("🪟 Lướt & Ngó trên cửa sổ")
    act_win_on = QAction("Tự động lướt / ngó trên cửa sổ đang mở", pet, checkable=True)
    act_win_on.setChecked(pet.window_perch_enabled)
    act_win_on.triggered.connect(lambda c: setattr(pet, "window_perch_enabled", c))
    win_menu.addAction(act_win_on)
    win_menu.addAction("🏄 Lướt dọc mép cửa sổ ngay", lambda: pet.trigger_window_perch("window_surf"))
    win_menu.addAction("👀 Thò đầu ngó qua thanh tiêu đề ngay", lambda: pet.trigger_window_perch("window_peek"))

    act_gaze = QAction("👀 Dõi ánh mắt theo chuột (Vùng 350px)", pet, checkable=True)
    act_gaze.setChecked(pet.cursor_gaze_enabled)
    act_gaze.triggered.connect(lambda c: setattr(pet, "cursor_gaze_enabled", c))
    menu.addAction(act_gaze)

    act_chase = QAction("🖱️ Đuổi theo chuột", pet, checkable=True)
    act_chase.setChecked(pet.chase_mode)
    act_chase.triggered.connect(lambda c: setattr(pet, "chase_mode", c))
    menu.addAction(act_chase)

    menu.addSeparator()

    # Pomodoro Mực Nước
    pomo_menu = menu.addMenu("⏱️ Pomodoro Mực Nước")
    pomo_menu.addAction("🌊 Tập trung 25p / Nghỉ 5p", lambda: pet.start_pomodoro(25 * 60, 5 * 60))
    pomo_menu.addAction("⚡ Thử nhanh (1p / 20s)", lambda: pet.start_pomodoro(60, 20))
    act_pomo_stop = pomo_menu.addAction("⏹️ Dừng Pomodoro", pet.stop_pomodoro)
    act_pomo_stop.setEnabled(pet.water_overlay.active)

    # Bong bóng Clipboard
    cb_menu = menu.addMenu("🫧 Bong bóng Clipboard")
    act_cb_toggle = QAction("Tự tạo bong bóng khi Ctrl+C", pet, checkable=True)
    act_cb_toggle.setChecked(pet.clipboard_bubbles_enabled)
    act_cb_toggle.triggered.connect(lambda c: setattr(pet, "clipboard_bubbles_enabled", c))
    cb_menu.addAction(act_cb_toggle)
    cb_menu.addAction("💥 Nổ hết bong bóng", pet.clear_clipboard_bubbles)

    # Bắt sóng âm thanh
    audio_menu = menu.addMenu("🎵 Bắt sóng âm thanh")
    audio_group = QActionGroup(pet)
    audio_group.setExclusive(True)
    for mode_key, label in (
        ("auto", "Tự động (Âm thanh hệ thống)"),
        ("demo", "Nhịp nhạc Demo (Thử Equalizer & Backflip)"),
        ("off", "Tắt"),
    ):
        act = QAction(label, pet, checkable=True)
        act.setChecked(pet.audio.mode == mode_key)
        act.triggered.connect(lambda checked, m=mode_key: pet.audio.set_mode(m))
        audio_group.addAction(act)
        audio_menu.addAction(act)
    audio_menu.addSeparator()
    audio_menu.addAction("🤸 Nhào lộn Backflip ngay", pet.trigger_backflip)

    menu.addSeparator()

    # Biểu cảm & Vi biểu cảm
    expr_menu = menu.addMenu("🎭 Biểu cảm & Vi biểu cảm")
    for key, label in EXPRESSIONS_MENU:
        if key == "puffed":
            expr_menu.addAction(label, pet.trigger_pufferfish)
        elif key == "nauseous":
            expr_menu.addAction(label, pet.trigger_nauseous_rainbow)
        elif key == "sneeze":
            expr_menu.addAction(label, pet.trigger_sneeze)
        elif key == "proud":
            expr_menu.addAction(label, pet.trigger_celebrate_figure8)
        else:
            expr_menu.addAction(label, lambda checked=False, k=key: pet._trigger_menu_expr(k))
    expr_menu.addSeparator()
    sleep_label = "⚡ Hồi sinh (Hết giả chết)" if pet.state == "play_dead" else "💀 Giả chết (Nổi bụng)"
    expr_menu.addAction(
        sleep_label,
        pet._wake_from_play_dead if pet.state == "play_dead" else pet.enter_play_dead,
    )

    # Cảm biến & Ngữ cảnh
    env_menu = menu.addMenu("🌡️ Ngữ cảnh & Cảm biến")
    act_wall = QAction("🎨 Nhận diện màu hình nền (Ưa xanh / Né đỏ)", pet, checkable=True)
    act_wall.setChecked(pet.wallpaper_aware)
    act_wall.triggered.connect(lambda c: setattr(pet, "wallpaper_aware", c))
    env_menu.addAction(act_wall)

    act_boil = QAction(
        f"🔥 Mô phỏng quá tải CPU (Hiện tại: {pet.cpu_percent:.0f}% / RAM {pet.ram_percent:.0f}%)",
        pet,
        checkable=True,
    )
    act_boil.setChecked(pet.simulate_overload)
    act_boil.triggered.connect(pet._toggle_sim_overload)
    env_menu.addAction(act_boil)

    act_night = QAction("🌙 Chế độ khuya >23:30 (Chăn rong biển)", pet, checkable=True)
    act_night.setChecked(pet.simulate_late_night)
    act_night.triggered.connect(pet._toggle_sim_night)
    env_menu.addAction(act_night)

    # Đổi màu cá
    theme_menu = menu.addMenu("🎨 Đổi màu cá")
    theme_group = QActionGroup(pet)
    theme_group.setExclusive(True)
    for name in FISH_THEMES:
        act = QAction(name, pet, checkable=True)
        act.setChecked(name == pet.theme_name)
        act.triggered.connect(lambda checked, n=name: pet.set_theme(n))
        theme_group.addAction(act)
        theme_menu.addAction(act)

    menu.addSeparator()
    if sys.platform == "darwin":
        act_spaces = QAction("🖥️ Đi theo qua mọi Desktop / Full-Screen", pet, checkable=True)
        act_spaces.setChecked(pet.all_spaces_enabled)
        act_spaces.triggered.connect(pet.set_all_spaces_enabled)
        menu.addAction(act_spaces)
    menu.addAction("🕶️ Lặn sâu ẩn mình (Ctrl+Shift+H)", pet.toggle_boss_hide)
    menu.addAction("❌ Thoát", QApplication.quit)
    menu.exec(global_pos)
