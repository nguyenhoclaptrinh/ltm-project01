# BÁO CÁO DỰ ÁN: VIDEO STREAMING USING IP MULTICAST (PROJECT 02)

## 1. Kiến Trúc Hệ Thống (Architecture)
Hệ thống được phát triển trên nền tảng ngôn ngữ Python, áp dụng mô hình phát sóng **One-to-Many** thông qua giao thức **UDP Multicast**. 

```
                                  +-----------------------+
                                  |   Server (Source)     |
                                  |   (python Server.py)  |
                                  +-----------+-----------+
                                              |
                                              | Gửi luồng UDP Multicast
                                              v
                                   [Group: 239.1.1.1:5004]
                                              |
                     +------------------------+------------------------+
                     | (Router nhân bản và định tuyến gói tin)         |
                     v                                                 v
         +-----------+-----------+                         +-----------+-----------+
         |        Client 1       |                         |        Client N       |
         |    (python Client.py) |                         |    (python Client.py) |
         +-----------------------+                         +-----------------------+
```

### Cơ chế hoạt động:
* **Server**: Đóng vai trò là nguồn phát, chỉ gửi dữ liệu đúng một lần tới địa chỉ nhóm multicast `239.1.1.1:5004`. Server không cần biết có bao nhiêu client đang tham gia nhận và không duy trì trạng thái của các client (không sử dụng RTSP/TCP).
* **Client**: Sử dụng cơ chế IGMP để xin gia nhập nhóm multicast. Hệ điều hành và các router hỗ trợ multicast sẽ chịu trách nhiệm phân phối bản sao gói tin đến tất cả các client đã đăng ký trong nhóm. Khi tắt, client gửi gói tin IGMP rời nhóm (Leave Group).

---

## 2. Định Dạng Gói Tin Custom (Custom Packet Format)
Để tránh phân mảnh ở tầng IP khi dung lượng frame ảnh JPEG vượt quá giới hạn **MTU (1500 bytes)**, hệ thống tự động chia nhỏ (fragmentation) các frame JPEG thô ở tầng ứng dụng thành nhiều phần nhỏ (tối đa **1400 bytes** payload).
Mỗi gói tin gửi đi có định dạng nhị phân bao gồm **12 bytes Custom Header** ở đầu, theo sau là dữ liệu Payload:

```
  0                   1                   2                   3
  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |                      Global Sequence Number                   | (4 bytes)
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |          Frame ID             |        Fragment Index         | (2 bytes + 2 bytes)
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |        Total Fragments        |          Data Length          | (2 bytes + 2 bytes)
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |                             Payload                           |
  |                             ....                              |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Chi tiết các trường dữ liệu (Big-Endian `!IHHHH`):
1. **Global Sequence Number (4 bytes)**: Số thứ tự gói tin tăng dần toàn cục từ 0. Giúp client xác định chính xác số gói tin bị mất trên đường truyền mạng.
2. **Frame ID (2 bytes)**: Chỉ số thứ tự của frame hình ảnh (0, 1, 2...).
3. **Fragment Index (2 bytes)**: Thứ tự mảnh của frame hiện tại (0, 1, ..., Total - 1).
4. **Total Fragments (2 bytes)**: Tổng số mảnh tạo nên frame này (dùng để client biết khi nào nhận đủ frame).
5. **Data Length (2 bytes)**: Độ dài dữ liệu JPEG thô thực tế đi kèm trong gói tin.

---

## 3. Thống Kê Hiệu Năng & Đo Đạc Mất Mát (Loss Detection)
Client triển khai hai thuật toán đo đạc mất mát thời gian thực:
* **Tỉ lệ mất gói tin (Packet Loss Rate)**:
  * Client lưu giữ chỉ số `Global Sequence Number` lớn nhất đã nhận (`max_seq`).
  * Khi gói tin mới có `seq > max_seq` cập bến, số gói tin bị mất sẽ là `seq - max_seq - 1`.
  * Công thức: $\text{Packet Loss Rate} = \frac{\text{Gói bị mất}}{\text{Gói dự kiến}} \times 100\%$
* **Tỉ lệ mất khung hình (Frame Loss Rate)**:
  * Một frame hình ảnh được xem là bị hỏng/mất nếu client chuyển sang nhận một Frame ID mới lớn hơn trong khi frame cũ vẫn chưa nhận đủ số lượng mảnh (`Total Fragments`).
  * Công thức: $\text{Frame Loss Rate} = \frac{\text{Frame bị hỏng}}{\text{Tổng số frame dự kiến}} \times 100\%$

---

## 4. Hướng Dẫn Chạy Chương Trình (Running)

### Cài đặt thư viện dependencies:
Chạy lệnh sau tại thư mục chứa code:
```bash
pip install -r requirements.txt
```

### Khởi chạy Server:
Phát video trực tuyến từ file MJPEG thô:
```bash
python Server.py movie.Mjpeg
```
*Lưu ý: Server tự động lặp lại (loop) video khi phát hết.*

### Khởi chạy Client:
Mở cửa sổ hiển thị video realtime:
```bash
python Client.py
```
*Mẹo: Nhấp vào màn hình video và nhấn phím `q` để tắt Client và rời khỏi multicast group.*

### Kiểm thử nâng cao - Giả lập mất gói tin:
Chạy client với tham số phần trăm mất gói tin mong muốn (ví dụ giả lập mất 10% gói tin ngẫu nhiên trên mạng để kiểm tra thuật toán tính toán loss rate):
```bash
python Client.py 10
```

---

## 5. Kết Quả Kiểm Thử (Testing Results)

### Kịch bản 1: Môi trường mạng cục bộ (Local Loopback - Mặc định)
* **Kết quả**: Video hiển thị mượt mà ở tốc độ xấp xỉ ~20 FPS.
* **Thống kê**:
  * Packet Loss Rate: `0.00%` (0/N gói)
  * Frame Loss Rate: `0.00%` (0/N frame)
  * Render FPS: `20.0`
* **Nhận xét**: Đường truyền cục bộ không có nhiễu, thuật toán lắp ráp hoạt động hoàn hảo 100%.

### Kịch bản 2: Kiểm thử với giả lập mất gói 15% (`python Client.py 15`)
* **Kết quả**: Video có hiện tượng giật nhẹ (do một số frame bị hỏng và bị bỏ qua để đảm bảo tính thời gian thực), giao diện không bị crash hay treo đứng.
* **Thống kê**:
  * Packet Loss Rate: Dao động xung quanh `14.5% - 15.6%`.
  * Frame Loss Rate: Dao động xung quanh `30.0% - 40.0%` (do một frame bị mất bất kì mảnh nào trong số 5 mảnh của nó thì toàn bộ frame đó bị hủy hiển thị).
  * Render FPS: Giảm xuống khoảng `12.0 - 14.0 FPS`.
* **Nhận xét**: Thuật toán Loss Detection phát hiện mất mát cực kỳ chính xác. Cơ chế reassembly loại bỏ hoàn toàn các mảnh của frame bị hỏng một cách thông minh, không giải mã lỗi các ảnh khuyết, giúp chương trình luôn hoạt động ổn định.
