"""Widget nền hỗ trợ Non-Activating (không cướp focus), macOS All-Spaces & khóa xuyên chuột native."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from pet.platform.os_window import (
    bring_window_to_front_no_activate,
    configure_overlay_window,
)

_MACOS_ALL_SPACES_ENABLED = True


def set_widgets_all_spaces(enabled: bool) -> None:
    """Bật/tắt chế độ đi theo qua mọi Desktop (Spaces) cho toàn bộ widget vệ tinh mới tạo."""
    global _MACOS_ALL_SPACES_ENABLED
    _MACOS_ALL_SPACES_ENABLED = bool(enabled)


class _AllSpacesWidget(QWidget):
    """QWidget cơ sở tự động cấu hình không cướp focus, All-Spaces và xuyên chuột native cho overlay."""

    _PASSIVE_CLICK_THROUGH: bool = False

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def raise_no_activate(self) -> None:
        """Đưa overlay lên lớp trên cùng mà tuyệt đối không kích hoạt ứng dụng hay cướp bàn phím."""
        bring_window_to_front_no_activate(self)

    def showEvent(self, e):
        super().showEvent(e)
        configure_overlay_window(
            self,
            all_spaces=_MACOS_ALL_SPACES_ENABLED,
            click_through=True if self._PASSIVE_CLICK_THROUGH else None,
        )
