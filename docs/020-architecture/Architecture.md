# [DRAFT] Kiến trúc Hệ thống RTSP/RTP (Awaiting Approval)

Tài liệu này mô tả cấu trúc các lớp, luồng dữ liệu và máy trạng thái của hệ thống.

## 1. Sơ đồ Trình tự (Sequence Diagram)

```mermaid
sequence diagram
    participant C as Client
    participant S as Server
    
    Note over C,S: Giai đoạn Điều khiển (RTSP over TCP)
    C->>S: SETUP movie.Mjpeg (CSeq: 1, Transport: RTP/UDP)
    S-->>C: 200 OK (Session ID: 123456)
    
    Note over C,S: Giai đoạn Truyền tải (RTP over UDP/TCP)
    C->>S: PLAY (CSeq: 2, Session: 123456)
    S-->>C: 200 OK
    loop Mỗi 50ms
        S->>C: RTP Packet (Header + Video Frame)
    end
    
    C->>S: PAUSE (CSeq: 3, Session: 123456)
    S-->>C: 200 OK
    Note right of S: Dừng gửi RTP
    
    C->>S: TEARDOWN (CSeq: 4, Session: 123456)
    S-->>C: 200 OK
    Note over C,S: Đóng kết nối Socket
```

## 2. Thành phần Hệ thống

### 2.1. Client Side (Python)
- **ClientLauncher**: Khởi chạy GUI và Client.
- **Client**: Xử lý tương tác RTSP.
- **RtpPacket**: Giải mã RTP.

### 2.2. Server Side (Python)
- **ServerWorker**: Quản lý session và luồng gửi RTP.
- **VideoStream**: Đọc file MJPEG.
- **RtpPacket**: Đóng gói RTP (Hàm `encode`).

## 3. Quản lý Trạng thái (State Machine)

| Trạng thái Hiện tại | Sự kiện (Lệnh) | Trạng thái Tiếp theo | Hành động |
| :--- | :--- | :--- | :--- |
| INIT | SETUP | READY | Tạo socket RTP, gửi SETUP |
| READY | PLAY | PLAYING | Bắt đầu nhận/hiển thị luồng RTP |
| PLAYING | PAUSE | READY | Tạm dừng hiển thị, server ngừng gửi |
| ANY | TEARDOWN | INIT | Giải phóng tài nguyên, đóng socket |

## 4. Thiết kế Đóng gói RTP (RtpPacket.encode)

Cấu trúc header 12 bytes cần tuân thủ Network Byte Order:
1. **Byte 0**: `10000000` (V=2)
2. **Byte 1**: `00011010` (PT=26)
3. **Bytes 2-3**: Sequence Number (16-bit)
4. **Bytes 4-7**: Timestamp (32-bit)
5. **Bytes 8-11**: SSRC (32-bit)
