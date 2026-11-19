# 🐠 Golden Fish Desktop Pet (Cá Vàng Màn Hình)

Linh vật desktop 2D vẽ bằng vector mượt mà ở **60 FPS** viết bằng **Python + PySide6**, hoạt động trong môi trường bể cá ảo không trọng lực 360° trên màn hình.

## Tính năng chính

### 1. Bể cá ảo 360° & Vật lý 2D
- **Lực đẩy theo nhịp vẫy đuôi (Tail-Beat Impulse)**, quán tính nghiêng thân (**Banking**) và co giãn đàn hồi (**Squash & Stretch**) khi cua hoặc bật mép màn hình.
- **Chiều sâu 3D** (`0.85x` ↔ `1.10x` kèm bóng đổ động), **ánh sáng khúc xạ (Caustics)** và **đuôi bong bóng (Bubble Trail)** khi bơi nhanh.
- **Cursor Wake**: Vung chuột nhanh ngang qua cá tạo xoáy nước làm cá chóng mặt; vung 3 lần trong 5 giây cá sẽ tái mặt, ợ bong bóng cầu vồng rồi lật ngửa bụng 3 giây.
- **Ngủ bong bóng khổng lồ**: Tự thổi bong bóng lớn bọc quanh thân và ngủ ở góc màn hình sau 5 phút không tương tác.

### 2. Tương tác & Vi biểu cảm
- **Biến hình Cá Nóc**: Click chuột trái liên tiếp 4 lần → phồng tròn nổi gai 3 giây → xì hơi bay vèo khắp màn hình.
- **Kéo file vào miệng cá để ăn & xóa**: Kéo file/thư mục từ trình quản lý file vào miệng cá để cá hút vào miệng, nhai vụn giấy và chuyển vào Thùng rác hệ thống (hoặc tùy chọn xóa vĩnh viễn có xác nhận).
- **Bong bóng Clipboard**: Tự thổi bong bóng khi bấm `Ctrl + C`; click làm nổ *"bụp"* để mở link hoặc dán nhanh, sau đó cá ăn mừng lượn hình số 8 (`∞`).
- **Vi biểu cảm tự nhiên**: Tò mò soi con trỏ chuột (khi chuột đứng yên 10–15s), hắt xì ngẫu nhiên giật lùi, vuốt ve hiện mắt trái tim.

### 3. Hỗ trợ làm việc & Trò chơi
- **Đậu & Lướt trên thanh tiêu đề cửa sổ**: Tự nhận diện cửa sổ đang mở để lướt dọc mép trên hoặc thò nửa đầu ngó xuống.
- **Pomodoro "Mực Nước Dâng"**: Nước trong suốt xuyên chuột dâng dần khi tập trung và rút cạn khi nghỉ (cá đội mũ bong bóng nước bay tự do).
- **Cho ăn Cám cá & Ký tự/Từ khóa**: Thả mưa hạt cám hoặc ký tự/emoji rơi từ đỉnh màn hình; ăn đủ no cá sẽ béo tròn thêm trong vài phút.
- **Bóng bàn Bong Bóng (Bubble Pong)**: Tâng bong bóng qua lại giữa con trỏ chuột và mũi cá.
- **Boss Key (`Ctrl + Shift + H`)**: Cá giật mình lặn tòm xuống đáy kèm gợn sóng, ẩn sạch màn hình để chia sẻ/họp; bấm lại để ngoi lên.
- **Phản ứng ngữ cảnh**: Nước sôi cảnh báo khi CPU/RAM > 85%, bọt trắng nảy Equalizer + backflip theo nhạc, nhận diện màu hình nền (ưa xanh dương / né đỏ cam) và đắp chăn rong biển sau 23:30.

## Cài đặt & Chạy

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python desktop_pet.py
```

> **Lưu ý trên Linux (Ubuntu/Debian X11):** Nếu Qt báo thiếu plugin `xcb`, hãy cài thêm:
> ```bash
> sudo apt install libxcb-cursor0
> ```
