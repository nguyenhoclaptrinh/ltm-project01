---
id: PRD-001
type: PRD
status: Draft
created: 2026-05-17
---

# Tài Liệu Yêu Cầu Sản Phẩm (PRD) - Hệ Thống Video Streaming RTSP/RTP

## 1. Tổng Quan Dự Án
Dự án này nhằm mục đích xây dựng một ứng dụng truyền tải video (Video Streaming) dựa trên hai giao thức tiêu chuẩn: RTSP (Real-Time Streaming Protocol) để điều khiển và RTP (Real-time Transport Protocol) để truyền tải dữ liệu. Hệ thống bao gồm một Server có khả năng phát video và một Client có giao diện người dùng để tương tác.

### 1.1 Mục tiêu
- Triển khai thành công giao thức điều khiển RTSP phía Client.
- Triển khai đóng gói dữ liệu RTP phía Server.
- Hỗ trợ truyền tải video chất lượng cao (HD) và cơ chế bộ đệm (Caching).
- Tối ưu hóa hiệu năng Server bằng I/O Multiplexing.

### 1.2 Đối tượng sử dụng
- Sinh viên ngành Mạng máy tính/Lập trình mạng.
- Giảng viên đánh giá đồ án.

---

## 2. Phạm Vi Tính Năng

### 2.1 Chức năng điều khiển (RTSP)
- **SETUP**: Thiết lập phiên làm việc, trao đổi thông tin cổng truyền tải RTP.
- **PLAY**: Bắt đầu/Tiếp tục phát video.
- **PAUSE**: Tạm dừng phát video.
- **TEARDOWN**: Kết thúc phiên, giải phóng tài nguyên.
- **CSeq**: Quản lý số thứ tự yêu cầu để đồng bộ hóa.

### 2.2 Chức năng truyền tải (RTP)
- **Đóng gói (Packetization)**: Chuyển đổi các frame video MJPEG thành các gói tin RTP.
- **Hỗ trợ Fragmentation**: Chia nhỏ các frame lớn vượt quá MTU (1500 bytes).
- **Truyền tải linh hoạt**:
    - Sử dụng UDP cho video SD (Standard Definition) để giảm độ trễ.
    - Sử dụng TCP cho video HD (720p/1080p) để đảm bảo độ tin cậy.

### 2.3 Tính năng nâng cao
- **I/O Multiplexing**: Server sử dụng cơ chế phi tuần tự (Non-blocking) để xử lý nhiều kết nối thay vì sử dụng Thread.
- **Client-side Caching**: Lưu trữ tạm thời N frames trước khi hiển thị để giảm hiện tượng giật hình (jitter).
- **HD Video Support**: Khả năng xử lý các file video độ phân giải cao.

---

## 3. Yêu Cầu Kỹ Thuật

### 3.1 Nền tảng & Ngôn ngữ
- **Ngôn ngữ**: Python 3.x.
- **Thư viện**: `socket`, `threading` (hoặc `selectors` cho Multiplexing), `tkinter` (cho UI), `time`.

### 3.2 Giao thức
- **RTSP**: Tuân thủ RFC 2326 (phiên bản rút gọn).
- **RTP**: Tuân thủ RFC 1889.

### 3.3 Hiệu năng & Bảo mật (Mức độ sinh viên)
- Server phải xử lý được các yêu cầu cơ bản một cách ổn định.
- Mã nguồn cần rõ ràng, dễ bảo trì và có comment tiếng Việt đầy đủ.

---

## 4. Kế Hoạch Triển Khai (Dự kiến)
1. **Giai đoạn 1**: Nghiên cứu mã nguồn mẫu (Skeleton code) và thiết lập môi trường.
2. **Giai đoạn 2**: Cài đặt RTSP phía Client (SETUP, PLAY, PAUSE, TEARDOWN).
3. **Giai đoạn 3**: Cài đặt RTP Packetization phía Server.
4. **Giai đoạn 4**: Triển khai I/O Multiplexing và hỗ trợ HD Video (TCP).
5. **Giai đoạn 5**: Triển khai Client-side Caching.
6. **Giai đoạn 6**: Kiểm thử toàn diện và viết báo cáo.

---

## 5. Tiêu Chí Đánh Giá (Success Metrics)
- Video được phát mượt mà trên Client.
- Các lệnh điều khiển phản hồi chính xác.
- Server không bị treo khi có lỗi kết nối.
- Hoàn thành đầy đủ các yêu cầu nâng cao để đạt điểm tối đa (10/10).
