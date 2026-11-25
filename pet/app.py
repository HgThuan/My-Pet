"""Điểm khởi chạy ứng dụng Golden Fish Desktop Pet."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from pet.core.pet import GoldenFishPet
from pet.platform.os_window import configure_macos_app_for_spaces


def main(argv: list[str] | None = None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    app.setQuitOnLastWindowClosed(False)
    configure_macos_app_for_spaces()
    pet = GoldenFishPet()
    pet.show()
    return app.exec()
