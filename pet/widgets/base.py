"""Widget nền hỗ trợ macOS All-Spaces & Full-Screen Auxiliary cho các overlay vệ tinh."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from pet.platform.os_window import apply_macos_all_spaces

_MACOS_ALL_SPACES_ENABLED = True


def set_widgets_all_spaces(enabled: bool) -> None:
    """Bật/tắt chế độ đi theo qua mọi Desktop (Spaces) cho toàn bộ widget vệ tinh mới tạo."""
    global _MACOS_ALL_SPACES_ENABLED
    _MACOS_ALL_SPACES_ENABLED = bool(enabled)


class _AllSpacesWidget(QWidget):
    """QWidget cơ sở tự động áp dụng macOS CanJoinAllSpaces + FullScreenAuxiliary khi hiển thị."""

    def showEvent(self, e):
        super().showEvent(e)
        apply_macos_all_spaces(self, _MACOS_ALL_SPACES_ENABLED)

