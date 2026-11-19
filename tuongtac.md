# Tài Liệu Thiết Kế Tương Tác: Desktop Pet - Cá Vàng (Golden Fish)

Tài liệu này mô tả hệ thống cơ chế vật lý, hành vi tự động và các tương tác nâng cao dành cho linh vật màn hình (Desktop Pet) hình chú cá vàng tròn trĩnh, nhằm tạo ra trải nghiệm sống động, vui nhộn và hỗ trợ người dùng trong quá trình làm việc.

---

## 1. Hệ Thống Vật Lý & Môi Trường "Bể Cá Ảo"

Khác với các linh vật đi bộ trên thanh Taskbar, chú cá vàng hoạt động trong môi trường **không trọng lực (bơi lội tự do 360°)** trên toàn bộ không gian màn hình.

* **Giả lập chiều sâu 3D (Depth & Shadow):**
  * **Nổi lên sát mặt kính:** Kích thước nhân vật phóng to nhẹ (`1.1x`), hiệu ứng bóng đổ bên dưới bụng mờ dần đi.
  * **Lặn sâu vào trong:** Kích thước thu nhỏ nhẹ (`0.85x`), bóng đổ đậm và sắc nét hơn khi bơi ngang qua các cửa sổ ứng dụng hoặc thanh công cụ.
* **Tương tác dòng chảy bằng con trỏ chuột (Cursor Wake):**
  * Di chuyển chuột bình thường: Cá bơi tò mò đi theo hoặc giữ khoảng cách an toàn.
  * Vung chuột nhanh qua người cá: Tạo ra một luồng xoáy nước vô hình khiến cá bị cuốn xoay vòng tròn, mắt hoa lên (`dizzy` state) trong 1–2 giây trước khi lấy lại thăng bằng.
* **Ngủ trong bong bóng khổng lồ (Idle State):**
  * Sau 5–10 phút không có thao tác chuột/bàn phím, cá thổi ra một quả bong bóng lớn bao bọc lấy toàn thân, trôi lềnh bềnh ở một góc màn hình và chuyển sang trạng thái ngủ gật (`zZ`).

---

## 2. Tương Tác Trực Tiếp & Phá Cách (Direct & Fourth-Wall Interactions)

### 2.1. Biến Hình Cá Nóc (Chọc Ghẹo)
* **Điều kiện kích hoạt:** Nhấn chuột trái liên tục (Spam Click) vào người cá trong thời gian ngắn.
* **Phản ứng:** Cá hít một hơi thật sâu, thân hình tròn phình to gấp đôi như một con cá nóc, hai má đỏ ửng lên tỏ vẻ dỗi hờn. Sau 3 giây, cá xì hơi và bay vèo đi khắp màn hình như một quả bóng bay mất kiểm soát.

### 2.2. Bong Bóng Chứa Dữ Liệu (Bubble Clipboard & Notes)
* **Cơ chế:** Tận dụng hiệu ứng các hạt bong bóng xung quanh cá để lưu trữ tạm thời thông tin.
* **Hành vi:** Khi người dùng sao chép (`Ctrl + C`) một đoạn văn bản hoặc đường link, cá sẽ thổi ra một quả bong bóng lớn mang theo biểu tượng nội dung đó bay lơ lửng.
* **Tương tác:** Người dùng chỉ cần click chuột để làm "nổ" bong bóng (kèm hiệu ứng âm thanh *bụp* vui tai) để dán nhanh nội dung vào vị trí đang trỏ chuột hoặc mở nhanh liên kết.

### 2.3. Nuốt Rác & Dọn Dẹp Màn Hình (Recycle Bin Sống)
* **Điều kiện kích hoạt:** Kéo thả một tệp tin (file) bất kỳ hoặc bôi đen một đoạn văn bản kéo thả trực tiếp vào miệng cá.
* **Phản ứng:** Cá há to miệng hút chùn chụt cả khối dữ liệu vào bụng, ợ ra một tràng bong bóng nhỏ, đồng thời chuyển tệp tin đó vào thùng rác hệ thống (Recycle Bin / Trash).

---

## 3. Tính Năng Hỗ Trợ Làm Việc (Productivity Companion)

### 3.1. Đồng Hồ Tập Trung "Mực Nước Dâng" (Pomodoro Timer)
* **Giai đoạn tập trung (Focus):** Khi bật bộ đếm giờ, một lớp hiệu ứng mặt nước trong suốt (gợn sóng nhẹ) sẽ dâng dần từ đáy màn hình lên tới đỉnh khi hết giờ. Chú cá chỉ có thể bơi lội bên trong vùng có nước.
* **Giai đoạn nghỉ ngơi (Break):** Khi hết giờ, mực nước rút cạn dần; chú cá sẽ đội thêm một chiếc "mũ bong bóng nước" trên đầu để tiếp tục bay lơ lửng và nhắc nhở người dùng đứng dậy vươn vai, uống nước.

### 3.2. Cảm Biến "Áp Suất" Hệ Thống (CPU / Tab Overload Warning)
* **Điều kiện kích hoạt:** Người dùng mở quá nhiều tab trình duyệt hoặc mức sử dụng CPU/RAM vượt ngưỡng cao (ví dụ $> 85\%$).
* **Phản ứng:** Vùng không gian xung quanh cá bắt đầu sủi bọt khí sôi sùng sục như nước đun sôi. Chú cá bơi cuống cuồng với biểu cảm hốt hoảng, phát tín hiệu nhắc người dùng tắt bớt ứng dụng để máy tính "hạ nhiệt".

---

## 4. Phản Ứng Ngữ Cảnh Thông Minh (Context-Aware)

* **Bắt sóng âm thanh (Audio Visualizer):**
  * Khi hệ thống phát nhạc hoặc video, các hạt bong bóng trắng xung quanh cá tự động nảy lên theo tần số âm thanh (Equalizer).
  * Gặp đoạn nhạc có tiết tấu nhanh/mạnh (bass drop), cá thực hiện động tác nhào lộn (`backflip`) liên tục.
* **Nhận diện màu sắc hình nền (Wallpaper Awareness):**
  * Cá có xu hướng ưu tiên bơi lội, ẩn nấp ở các khu vực có tông màu xanh dương/lạnh trên hình nền desktop và tỏ ra dè chừng khi bơi qua các vùng có màu đỏ/cam rực.
* **Đồng bộ thời gian thực:**
  * Sau 23:30 đêm, nếu máy tính vẫn hoạt động, cá sẽ liên tục ngáp ngắn ngáp dài, bơi chậm chạp và kéo một chiếc chăn rong biển ra đắp để nhắc người dùng đi ngủ.

---

## 5. Danh Sách Bộ Chuyển Động Cần Thiết (Sprite Animation Checklist)

Để hiện thực hóa các tương tác trên, bộ tài nguyên hình ảnh (Sprite Sheet) cần bao gồm các trạng thái cơ bản sau:

1. **Idle / Swim (Bơi cơ bản):** Bơi ngang (trái/phải), bơi hướng lên, bơi hướng xuống, nhìn thẳng chính diện.
2. **Happy (Vui vẻ):** Mắt híp cười, vẫy đuôi nhanh, tỏa nhiều bong bóng nhỏ.
3. **Puffed (Phồng mang):** Thân hình phình tròn to, má đỏ, biểu cảm tức giận/dỗi.
4. **Dizzy (Chóng mặt):** Mắt xoay vòng tròn khi bị chuột vung trúng.
5. **Eat / Swallow (Há miệng ăn):** Há miệng to hút đồ vật/file.
6. **Panic (Hốt hoảng):** Mắt mở to, vây vẫy loạn xạ (dùng khi CPU cao hoặc bị kéo thả).
7. **Sleep (Ngủ):** Nhắm mắt, nằm gọn bên trong một quả bong bóng lớn.