# 🐠 Golden Fish Desktop Pet (Cá Vàng Màn Hình)

Linh vật desktop 2D vẽ bằng vector mượt mà ở **60 FPS** viết bằng **Python + PySide6**, hoạt động trong môi trường bể cá ảo không trọng lực 360° trên màn hình.

## Tính năng chính

### 1. Bể cá ảo 360° & Vật lý 2D
- **Bể cá ảo 360° & Dõi ánh mắt theo chuột 3 lớp**: Trong vùng chú ý `350px`, con ngươi liếc độc lập mượt mà (`2–3.2px`, lerp `0.30`), thân nghiêng theo độ trễ (damping `0.08`, giới hạn `±35°` khi lệch `> 20°`), và lật hướng trái/phải có vùng đệm `35px` kèm chuyển cảnh quay đầu qua chính diện (`~150ms`). Ngoài `350px`, cá tự do bơi lội ngắm cảnh.
- **Lực đẩy theo nhịp vẫy đuôi (Tail-Beat Impulse)**, quán tính nghiêng thân (**Banking**) và co giãn đàn hồi (**Squash & Stretch**) khi cua hoặc bật mép màn hình.
- **Chiều sâu 3D** (`0.85x` ↔ `1.10x` kèm bóng đổ động), **ánh sáng khúc xạ (Caustics)** và **đuôi bong bóng (Bubble Trail)** khi bơi nhanh.
- **Cursor Wake**: Vung chuột nhanh ngang qua cá tạo xoáy nước làm cá chóng mặt; vung 3 lần trong 5 giây cá sẽ tái mặt, ợ bong bóng cầu vồng rồi lật ngửa bụng 3 giây.
- **Giả chết nổi bụng (Idle State)**: Sau 5 phút không tương tác (hoặc kích hoạt trong menu), cá tự lật ngửa bụng nổi lềnh bềnh lên sát đỉnh màn hình với mắt `X X`, lè lưỡi, vòng hào quang thiên thần & linh hồn nhỏ bay lên — thỉnh thoảng còn hé trộm một mắt liếc xem bạn có đang nhìn không! Chạm chuột vào cá sẽ giật mình hồi sinh đỏ mặt ngại ngùng.

### 2. Tương tác & Vi biểu cảm
- **Biến hình Cá Nóc**: Click chuột trái liên tiếp 4 lần → phồng tròn nổi gai 3 giây → xì hơi bay vèo khắp màn hình.
- **Kéo file vào miệng cá để ăn & xóa**: Kéo file/thư mục từ trình quản lý file vào miệng cá để cá hút vào miệng, nhai vụn giấy và chuyển vào Thùng rác hệ thống (hoặc tùy chọn xóa vĩnh viễn có xác nhận).
- **Hệ thống Độ Đói & Sinh Tồn (Hunger & Starvation)**:
  - Lưu bền vững chỉ số `hunger` (`0%–100%`, mặc định `80%`) vào `~/.config/golden_fish_pet/pet_state.json`, giảm chậm `0.04%/phút` khi hoạt động (không trừ lúc máy nghỉ/IDLE).
  - **Khẩu phần 3 file = No căng**: Mỗi file rác hồi **`+34%`** độ no (kéo text hồi `+15%`). Khi **`>= 95%` (No căng)**, cá lắc đầu từ chối (`SHAKE_HEAD_FULL`), chặn xóa và trả file an toàn về thư mục gốc.
  - **Đói (`15–39%`) & Sắp chết đói (`1–14%`)**: Cá bơi chậm lại (`0.5x` / `0.2x`), chìm gần đáy màn hình, định kỳ 6–10s giơ vây chỉ vào miệng đòi ăn (`POINT_TO_MOUTH`) kèm bong bóng thoại / icon thùng rác và lập tức sáng mắt lao tới khi đánh hơi thấy bạn kéo file.
  - **Chết đói (`0%`) & Hồi sinh**: Cá lật ngửa bụng mắt `X X` trôi nổi sát đỉnh màn hình; thả 1 file (hoặc chọn `Cho ăn khẩn cấp` trong menu chuột phải) sẽ giúp cá **Hồi sinh** (`50%` độ no).
- **Bong bóng Clipboard**: Tự thổi bong bóng khi bấm `Ctrl + C`; click làm nổ *"bụp"* để mở link hoặc dán nhanh, sau đó cá ăn mừng lượn hình số 8 (`∞`).
- **Vi biểu cảm tự nhiên**: Hắt xì ngẫu nhiên giật lùi, vuốt ve hiện mắt trái tim.

### 3. Hỗ trợ làm việc & Trò chơi
- **Cá heo nhảy sóng trên thanh tiêu đề cửa sổ (Porpoising)**: Tự nhận diện cửa sổ đủ rộng (vùng an toàn `>= 310px` tránh 3 nút đèn giao thông macOS / cụm nút Windows-Linux) và đo chính xác khoảng trống tới trần màn hình để thực hiện **1–3 nhịp nhảy vồng cung parabol** mềm mại không chạm đỉnh, đồng bộ hướng mặt với vận tốc ngang, té nước & vòng gợn sóng tại mỗi điểm xuyên mặt nước, rồi chúi đầu lặn sâu kèm vệt bong bóng trở về bơi tự do; đồng thời xuyên chuột vùng rìa trên macOS, Windows và Linux X11 (`ShapeInput`) để không cản bấm tab.
- **Pomodoro "Mực Nước Dâng"**: Nước trong suốt xuyên chuột dâng dần khi tập trung và rút cạn khi nghỉ (cá đội mũ bong bóng nước bay tự do).
- **Cho ăn Ký tự/Từ khóa**: Thả mưa ký tự/emoji rơi từ đỉnh màn hình; ăn đủ no cá sẽ béo tròn thêm trong vài phút.
- **Boss Key (`Ctrl + Shift + H`)**: Cá giật mình lặn tòm xuống đáy kèm gợn sóng, ẩn sạch màn hình để chia sẻ/họp; bấm lại để ngoi lên.
- **Chế độ Lồng Giam (`Ctrl + Esc`)**: Giam cá vào lồng sắt 2D có thể kéo thả cố định ở bất kỳ đâu (góc màn hình, thanh tiêu đề cửa sổ) để tập trung làm việc; cá buồn bã liếc theo chuột và thỉnh thoảng bám thanh sắt van xin (`±3°`). Nhấn `Ctrl + Esc` lần 2 để cá hóa lực sĩ bẻ cong 2 thanh sắt giữa lồng kèm tia lửa, khói bụi và âm thanh kim loại, bật nhảy ra ngoài đầy tự hào.
- **Hỗ trợ đa Desktop (Spaces) & Full-Screen trên macOS**: Tự động cấu hình `NSWindowCollectionBehavior` (`CanJoinAllSpaces | FullScreenAuxiliary`) để cá và mọi bong bóng/hiệu ứng đi theo bạn qua tất cả các Desktop và màn hình toàn màn hình (có thể bật/tắt trong menu chuột phải).
- **Phản ứng ngữ cảnh**: Nước sôi cảnh báo khi CPU/RAM > 85%, bọt trắng nảy Equalizer + backflip theo nhạc, nhận diện màu hình nền (ưa xanh dương / né đỏ cam) và đắp chăn rong biển sau 23:30.

## Kiến trúc mã nguồn

Dự án được tổ chức theo gói phân tầng `pet/` với luồng phụ thuộc một chiều (không vòng lặp import), tách biệt rõ ràng giữa cấu hình, nền tảng OS, cảm biến, đồ họa vector, widget vệ tinh, bộ điều khiển nghiệp vụ và giao diện menu:

```text
PET/
├── desktop_pet.py              # Điểm khởi chạy (python desktop_pet.py)
├── pet/
│   ├── app.py                  # Khởi tạo QApplication & GoldenFishPet
│   ├── config.py               # Hằng số, bảng màu, HungerState & PetStateStore (JSON)
│   ├── models.py               # Dataclass: FishRenderState, Particle, TrackedWindow
│   ├── platform/               # Tích hợp OS (X11/macOS/Windows) & thao tác tệp
│   │   ├── os_window.py        # macOS All-Spaces, Linux XShape click-through, X11 bindings
│   │   ├── window_tracker.py   # Theo dõi cửa sổ đang mở
│   │   ├── hotkeys.py          # Phím tắt toàn cục Ctrl+Shift+H & Ctrl+Esc
│   │   └── file_ops.py         # Tách URI kéo-thả, chuyển Thùng rác & xóa an toàn
│   ├── sensors/                # Cảm biến hệ thống & âm thanh
│   │   ├── monitors.py         # CPU/RAM, màu hình nền, giờ khuya
│   │   └── audio.py            # Equalizer/Bass Drop & tổng hợp âm thanh
│   ├── rendering/              # Vẽ vector 2D thuần QPainter
│   │   ├── fish.py             # Hàm render_fish chính & phụ kiện ngữ cảnh
│   │   ├── face.py             # Biểu cảm mắt/miệng & cử chỉ chỉ vây đòi ăn
│   │   ├── cage.py             # Lồng sắt 2D, vây van xin & cánh tay lực sĩ
│   │   └── primitives.py       # Hạt, sao, tim, bóng ma, vệt sóng, icon file
│   ├── widgets/                # Các overlay QWidget độc lập
│   │   ├── base.py             # _AllSpacesWidget
│   │   ├── clipboard_bubble.py # Bong bóng Clipboard
│   │   ├── effects.py          # Sóng té nước, hạt cầu vồng/chóng mặt, bong bóng suy nghĩ
│   │   └── gameplay.py         # Pomodoro mực nước, thức ăn ký tự, lồng sắt rơi
│   ├── core/                   # Lõi điều phối & bảng trạng thái hành vi
│   │   ├── pet.py              # GoldenFishPet(QWidget) điều phối gọn nhẹ
│   │   ├── behaviors.py        # Bảng STATE_HANDLERS tách từng trạng thái độc lập
│   │   ├── hunger.py           # HungerController (độ đói, 3 file = no, hồi sinh)
│   │   ├── surfing.py          # WindowSurfController (nhảy sóng Porpoising)
│   │   ├── particles.py        # ParticleSystem (sinh & cập nhật hạt)
│   │   └── math_utils.py       # Hàm góc, vùng an toàn cửa sổ & snap mặt nước
│   └── ui/
│       └── menu.py             # Menu chuột phải & System Tray Icon
└── tests/                      # Bộ kiểm thử tự động (unittest + Qt offscreen)
```

## Cài đặt & Chạy

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python desktop_pet.py
```

Chạy bộ kiểm thử tự động:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

> **Lưu ý trên Linux (Ubuntu/Debian X11):** Nếu Qt báo thiếu plugin `xcb`, hãy cài thêm:
> ```bash
> sudo apt install libxcb-cursor0
> ```
