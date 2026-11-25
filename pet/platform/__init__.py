"""Tầng tích hợp hệ điều hành (X11 / Windows / macOS) và thao tác tệp."""
from pet.platform.file_ops import (
    extract_dropped_paths,
    has_droppable_data,
    move_path_to_trash,
    parse_uri_to_local_path,
    permanently_delete_path,
)
from pet.platform.hotkeys import GlobalHotkeyListener
from pet.platform.os_window import (
    apply_macos_all_spaces,
    bring_window_to_front_no_activate,
    configure_macos_app_for_spaces,
    configure_non_activating_window,
    configure_overlay_window,
    set_window_click_through,
)
from pet.platform.window_tracker import WindowTracker

__all__ = [
    "GlobalHotkeyListener",
    "WindowTracker",
    "apply_macos_all_spaces",
    "bring_window_to_front_no_activate",
    "configure_macos_app_for_spaces",
    "configure_non_activating_window",
    "configure_overlay_window",
    "extract_dropped_paths",
    "has_droppable_data",
    "move_path_to_trash",
    "parse_uri_to_local_path",
    "permanently_delete_path",
    "set_window_click_through",
]
