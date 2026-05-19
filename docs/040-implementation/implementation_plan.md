# Kế Hoạch Triển Khai - Dự Án Video Streaming RTSP/RTP

Dự án này thực hiện hệ thống truyền tải video MJPEG qua giao thức RTSP và RTP bằng ngôn ngữ Python. Kế hoạch bao gồm việc hoàn thiện mã nguồn mẫu và triển khai các tính năng nâng cao theo yêu cầu đồ án sinh viên.

## Phân Tích Rủi Ro & Tác Động (Impact Analysis)
- **Rủi ro**: Việc chuyển đổi sang I/O Multiplexing có thể gây xung đột với luồng xử lý `threading` hiện tại nếu không quản lý tốt trạng thái socket.
- **Tác động**: Thay đổi cơ chế truyền tải sang TCP cho HD video yêu cầu sửa đổi cả Client và Server để hỗ trợ đóng gói Interleaved hoặc tạo kết nối TCP mới.

---

## Các Thay Đổi Đề Xuất

### 1. Thành Phần Client ([Client.py](file:///d:/2026DaiHoc/LapTrinhMang/Project01/src/python_rtp/Client.py))
Hoàn thiện các phương thức điều khiển RTSP và cơ chế nhận dữ liệu RTP.

- **[MODIFY] sendRtspRequest**: Xây dựng chuỗi yêu cầu RTSP đúng định dạng (CSeq, Session, Transport).
- **[MODIFY] parseRtspReply**: Xử lý phản hồi từ Server, cập nhật trạng thái Client (READY, PLAYING, v.v.).
- **[MODIFY] openRtpPort**: Thiết lập socket UDP để nhận dữ liệu RTP.
- **[NEW] Cơ chế Caching**: Thêm hàng đợi (queue) để lưu trữ frame trước khi hiển thị.

### 2. Thành Phần RTP Packet ([RtpPacket.py](file:///d:/2026DaiHoc/LapTrinhMang/Project01/src/python_rtp/RtpPacket.py))
Triển khai logic đóng gói frame video thành gói tin RTP tiêu chuẩn.

- **[MODIFY] encode**: 
    - Tính toán Timestamp.
    - Thiết lập các bit trong Header (Version, PT=26, SeqNum, SSRC).
    - Hỗ trợ Fragmentation nếu payload vượt quá kích thước gói cho phép.

### 3. Thành Phần Server ([Server.py](file:///d:/2026DaiHoc/LapTrinhMang/Project01/src/python_rtp/Server.py) & [ServerWorker.py](file:///d:/2026DaiHoc/LapTrinhMang/Project01/src/python_rtp/ServerWorker.py))
Tối ưu hóa khả năng xử lý và hỗ trợ truyền tải HD.

- **[MODIFY] Server.py**: Thay đổi vòng lặp lắng nghe sang sử dụng `selectors` (I/O Multiplexing).
- **[MODIFY] ServerWorker.py**: 
    - Xử lý yêu cầu truyền tải qua TCP khi Client yêu cầu HD.
    - Quản lý việc gửi các gói tin RTP đã chia nhỏ (fragments).

---

## Kế Hoạch Xác Minh (Verification Plan)

### Kiểm Thử Tự Động/Thủ Công
1. **Kiểm thử RTSP**: 
   - Chạy Server và Client.
   - Kiểm tra các nút Setup, Play, Pause, Teardown có hoạt động đúng trình tự không.
   - Kiểm tra file log/console để xác nhận định dạng request/reply.
2. **Kiểm thử RTP**:
   - Xác nhận hình ảnh video hiển thị trên Client.
   - Kiểm tra tính toàn vẹn của frame khi sử dụng Fragmentation.
3. **Kiểm thử Nâng Cao**:
   - Thử nghiệm với file video HD.
   - Kiểm tra độ mượt của video khi bật/tắt cơ chế Caching.
   - Kết nối nhiều Client cùng lúc để kiểm tra I/O Multiplexing.

### Bằng Chứng Xác Minh (Evidence)
- Ảnh chụp màn hình Client đang phát video.
- Log console của Server hiển thị các kết nối đang được Multiplex.
