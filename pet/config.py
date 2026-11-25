"""Cấu hình trung tâm, hằng số, bảng màu & lưu trữ trạng thái cho Golden Fish Pet."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from enum import Enum

from PySide6.QtGui import QColor

# Kích thước cửa sổ Pet & tốc độ khung hình
SIZE = 188
FPS = 60
IDLE_SLEEP_SECS = 5 * 60
CPU_PANIC_THRESHOLD = 85.0
MAX_CLIPBOARD_BUBBLES = 5

# Hệ thống Độ Đói & Sinh Tồn (Hunger & Starvation System)
PET_STATE_FILE = os.path.expanduser("~/.config/golden_fish_pet/pet_state.json")
HUNGER_DEFAULT = 80.0
HUNGER_DECAY_PER_MIN = 0.04        # -0.04% mỗi phút khi người dùng hoạt động (~2.4%/giờ)
HUNGER_FILE_GAIN = 34.0            # +34% mỗi file rác (3 file = No căng >= 100%)
HUNGER_TEXT_GAIN = 15.0            # +15% mỗi đoạn text kéo thả vào miệng
HUNGER_WORD_GAIN = 8.0             # +8% mỗi ký tự/từ khóa ăn được
HUNGER_FULL_THRESHOLD = 95.0       # >= 95%: No căng -> từ chối ăn & không xóa file
HUNGER_REVIVE_LEVEL = 50.0         # Hồi sinh từ DEAD đặt độ no = 50%

HUNGRY_BEG_LINES = (
    "Đói quá...",
    "Cho xin 1 file rác đi...",
)
FULL_REFUSE_LINES = (
    "No rồi, không ăn nổi nữa!",
    "No căng bụng rồi~",
)


class HungerState(Enum):
    NORMAL = "normal"       # >= 40
    HUNGRY = "hungry"       # 15 - 39
    STARVING = "starving"   # 1 - 14
    DEAD = "dead"           # <= 0


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

# Nhảy sóng trên thanh tiêu đề cửa sổ (Porpoising)
FISH_SURF_BODY_W = 100.0
PORPOISE_MIN_SAFE_W = 310.0      # Đủ rộng cho ít nhất 2 bước nhảy parabol liên tiếp (~150px/nhịp)

# Bảng màu giao diện cá
FISH_THEMES: dict[str, dict[str, str]] = {
    "Cá Vàng 🐠": {
        "body": "#ffd93b",
        "highlight": "#fff4a3",
        "shade": "#f59b25",
        "ventral": "#ffa82e",
        "outline": "#3b182c",
        "blush": "#f66e5e",
        "spike": "#ffb732",
    },
    "Cá Koi Đỏ 🎏": {
        "body": "#fff8f0",
        "highlight": "#ffffff",
        "shade": "#f26a3d",
        "ventral": "#ff7a45",
        "outline": "#3a1d26",
        "blush": "#ff6b81",
        "spike": "#ff7a45",
    },
    "Cá Xanh Ngọc 🐟": {
        "body": "#63d2ff",
        "highlight": "#ccf2ff",
        "shade": "#2b9cd8",
        "ventral": "#42b5eb",
        "outline": "#1d2d44",
        "blush": "#ff7aa2",
        "spike": "#48bfe3",
    },
    "Cá Hồng Sakura 🌸": {
        "body": "#ffb3c6",
        "highlight": "#ffe5ec",
        "shade": "#fb6f92",
        "ventral": "#ff8fab",
        "outline": "#421d2d",
        "blush": "#ff4d6d",
        "spike": "#ff8fab",
    },
    "Cá Đêm Huyền Bí 🌙": {
        "body": "#5e60ce",
        "highlight": "#a5a8f5",
        "shade": "#3a3ca8",
        "ventral": "#7476e0",
        "outline": "#1a1830",
        "blush": "#ff70a6",
        "spike": "#7b7ee6",
    },
}

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

URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)

WORD_FOOD_COLORS = [
    ("#ffe066", "#3b182c"),
    ("#74c0fc", "#183153"),
    ("#ffa8a8", "#4a192c"),
    ("#8ce99a", "#1b4332"),
    ("#d0bfff", "#2b1d4c"),
    ("#ffc078", "#4a2511"),
]

DEFAULT_WORD_TOKENS = [
    "def", "λ", "{ }", "git", "BUG", "404", "OK", "01", "✨", "⚡", "♥", "★", "API", "SQL",
]


class PetStateStore:
    """Đọc / ghi trạng thái bền vững của thú cưng vào file JSON."""

    def __init__(self, path: str | None = None):
        self.path = path

    def _resolve_path(self) -> str:
        return self.path if self.path is not None else PET_STATE_FILE

    def load_hunger(self) -> float:
        target = self._resolve_path()
        try:
            if os.path.exists(target):
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                val = float(data.get("hunger", HUNGER_DEFAULT))
                return max(0.0, min(100.0, val))
        except Exception:
            pass
        return HUNGER_DEFAULT

    def save_hunger(self, hunger: float) -> None:
        target = self._resolve_path()
        try:
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "hunger": round(float(hunger), 2),
                        "updated_at": datetime.now().isoformat(timespec="seconds"),
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass
