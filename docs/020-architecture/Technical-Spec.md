---
id: SPEC-001
type: Technical Spec
status: Draft
created: 2026-05-17
---

# Tài Liệu Đặc Tả Kỹ Thuật (Technical Specification)

## 1. Kiến Trúc Hệ Thống
Hệ thống tuân theo mô hình Client-Server truyền thống:
- **RTSP Control Channel**: Kết nối TCP bền vững (Persistent) để gửi lệnh điều khiển.
- **RTP Data Channel**: Kết nối UDP (mặc định) hoặc TCP (cho HD) để truyền các gói tin media.

## 2. Giao Thức RTSP (Real-Time Streaming Protocol)

### 2.1 Các Trạng Thái Của Client (State Machine)
- **INIT**: Trạng thái ban đầu, chưa có session.
- **READY**: Đã SETUP thành công, sẵn sàng PLAY.
- **PLAYING**: Đang nhận dữ liệu RTP và hiển thị video.

### 2.2 Luồng Hoạt Động (Sequence Diagram)
```mermaid
sequenceDiagram
    participant Client
    participant Server
    Client->>Server: SETUP movie.Mjpeg RTSP/1.0 (CSeq: 1, Transport: RTP/UDP; client_port=...)
    Server-->>Client: 200 OK (CSeq: 1, Session: 123456)
    Client->>Server: PLAY movie.Mjpeg RTSP/1.0 (CSeq: 2, Session: 123456)
    Server-->>Client: 200 OK (CSeq: 2, Session: 123456)
    loop RTP Streaming
        Server->>Client: RTP Packet (UDP/TCP)
    end
    Client->>Server: PAUSE movie.Mjpeg RTSP/1.0 (CSeq: 3, Session: 123456)
    Server-->>Client: 200 OK (CSeq: 3, Session: 123456)
    Client->>Server: TEARDOWN movie.Mjpeg RTSP/1.0 (CSeq: 4, Session: 123456)
    Server-->>Client: 200 OK (CSeq: 4, Session: 123456)
```

## 3. Giao Thức RTP (Real-time Transport Protocol)

### 3.1 Cấu Trúc Header (12 Bytes)
| Byte | Bit 0-1 | Bit 2 | Bit 3 | Bit 4-7 | Bit 8 | Bit 9-15 | Bit 16-31 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0-3 | V=2 | P=0 | X=0 | CC=0 | M=0 | PT=26 | Sequence Number |
| 4-7 | Timestamp (32 bits) | | | | | | |
| 8-11| SSRC (32 bits) | | | | | | |

### 3.2 Cơ Chế Đóng Gói (Packetization)
- **MJPEG**: Mỗi frame video được đọc từ file `.Mjpeg`.
- **Fragmentation**: Nếu kích thước frame > 1400 bytes (để an toàn trong MTU 1500), Server phải chia frame thành nhiều gói RTP.
    - Lưu ý: Trong phạm vi bài tập cơ bản, có thể giả định 1 gói/1 frame nếu frame nhỏ. Tuy nhiên, yêu cầu nâng cao bắt buộc có fragmentation.

## 4. Tính Năng Nâng Cao

### 4.1 I/O Multiplexing (Server)
Sử dụng thư viện `selectors` của Python để quản lý đồng thời:
- RTSP Listening Socket.
- Các RTSP Client Sockets hiện có.
- (Tùy chọn) RTP Sockets nếu dùng TCP.

### 4.2 HD Video & TCP Transport
- Khi phát video HD, Client sẽ yêu cầu `Transport: RTP/TCP` trong lệnh SETUP.
- Dữ liệu RTP sẽ được gửi qua chính socket TCP của RTSP (Interleaved) hoặc một socket TCP mới. Theo tiêu chuẩn RTSP, thường dùng Interleaving (RFC 2326 Section 10.12).

### 4.3 Client-Side Caching
- Duy trì một `queue` (hàng đợi) các frame đã de-packetized.
- Khi nhấn PLAY, Client sẽ đợi cho đến khi buffer đạt N frame (ví dụ: 10 frames) trước khi bắt đầu lấy từ queue để hiển thị lên UI.
