# Báo Cáo Đồ Án: Video Streaming with RTSP and RTP

## Thông Tin Nhóm

| MSSV | Họ và Tên |
|:---|:---|
| ___________ | ___________ |
| ___________ | ___________ |
| ___________ | ___________ |

**Môn học**: Lập Trình Mạng  
**Giảng viên**: ___________  
**Ngày nộp**: ___________

---

## 1. Mô Tả Dự Án

### 1.1 Tổng quan
Dự án xây dựng hệ thống truyền tải video (Video Streaming) sử dụng hai giao thức tiêu chuẩn:
- **RTSP (Real-Time Streaming Protocol)**: Kênh điều khiển qua TCP, xử lý các lệnh SETUP, PLAY, PAUSE, TEARDOWN.
- **RTP (Real-time Transport Protocol)**: Kênh truyền tải media qua UDP (SD) hoặc TCP Interleaved (HD).

### 1.2 Mục tiêu đạt được
1. Triển khai đầy đủ giao thức RTSP phía Client (4 lệnh điều khiển).
2. Triển khai đóng gói RTP phía Server theo RFC 1889.
3. Hỗ trợ Fragmentation cho frame lớn vượt MTU (1400 bytes).
4. Server sử dụng I/O Multiplexing (selectors) thay vì thread-per-client.
5. Hỗ trợ HD Video Streaming qua TCP Interleaved (RFC 2326 §10.12).
6. Client-side Caching với pre-buffer và chuyển đổi SD/HD tự động.

---

## 2. Kiến Trúc Hệ Thống

### 2.1 Sơ đồ thành phần

```
┌─────────────────────────────┐      ┌─────────────────────────────┐
│         CLIENT SIDE         │      │         SERVER SIDE         │
│                             │      │                             │
│  ClientLauncher.py          │      │  Server.py                  │
│    └── Client.py            │      │    └── selectors (I/O Mux)  │
│         ├── RtpPacket.py    │ TCP  │         └── ServerWorker.py │
│         │   (decode)        │◄────►│              ├── RtpPacket  │
│         ├── Frame Buffer    │      │              │   (encode)   │
│         │   (queue.Queue)   │ UDP/ │              ├── VideoStream│
│         └── Tkinter GUI     │ TCP  │              └── HDVideo-   │
│                             │◄─ ─ ─│                  Stream     │
└─────────────────────────────┘      └─────────────────────────────┘
```

### 2.2 Luồng hoạt động

1. **Client** kết nối TCP đến Server (RTSP control channel).
2. Client gửi **SETUP** → Server tạo session, phản hồi 200 OK.
3. Client gửi **PLAY** → Server bắt đầu đọc video, đóng gói RTP, gửi qua UDP/TCP.
4. Client nhận RTP packets → ghép mảnh (fragment reassembly) → đưa vào frame buffer.
5. Khi buffer đủ N frames (pre-buffer) → bắt đầu hiển thị video trên GUI.
6. Client có thể **PAUSE** (tạm dừng) hoặc **TEARDOWN** (kết thúc) bất cứ lúc nào.

### 2.3 State Machine (Máy trạng thái)

```
             SETUP (200 OK)           PLAY (200 OK)
  [INIT] ──────────────────► [READY] ──────────────────► [PLAYING]
    ▲                           │  ▲                        │
    │                           │  │    PAUSE (200 OK)      │
    │         TEARDOWN          │  └────────────────────────┘
    └───────────────────────────┘
              TEARDOWN
    [PLAYING] ────────────────────► [INIT]
```

---

## 3. Chi Tiết Triển Khai

### 3.1 RTP Packetization (Server)

**File**: `RtpPacket.py`

Header RTP 12 bytes tuân thủ RFC 1889:

| Byte | Nội dung |
|:---|:---|
| 0 | V=2 (2 bit), P=0 (1 bit), X=0 (1 bit), CC=0 (4 bit) |
| 1 | M (1 bit, marker cho fragment cuối), PT=26 (7 bit, MJPEG) |
| 2-3 | Sequence Number (16-bit big-endian) |
| 4-7 | Timestamp (32-bit big-endian) |
| 8-11 | SSRC (32-bit big-endian) |

Ví dụ bit manipulation cho Byte 0:
```python
header[0] = (version << 6) | (padding << 5) | (extension << 4) | cc
# V=2: 10|0|0|0000 = 0x80 = 128
```

### 3.2 Fragmentation (MTU-safe)

**File**: `ServerWorker.py`

Khi frame video > 1400 bytes (MTU Ethernet = 1500, trừ overhead):
- Chia frame thành các chunk ≤ 1400 bytes.
- Tất cả chunks cùng một frame có **cùng Sequence Number**.
- Chunk cuối cùng được đánh dấu **Marker bit = 1**.

```python
chunks = [data[i:i + MAX_PAYLOAD] for i in range(0, len(data), MAX_PAYLOAD)]
for i, chunk in enumerate(chunks):
    marker = 1 if i == len(chunks) - 1 else 0
    rtp_data = self.makeRtp(chunk, frameNumber, marker)
```

Phía Client ghép lại bằng cách tích lũy payload cho đến khi nhận được packet có Marker=1.

### 3.3 I/O Multiplexing (Server)

**File**: `Server.py`

Sử dụng `selectors.DefaultSelector()` thay vì tạo thread cho mỗi client:

```python
sel = selectors.DefaultSelector()
rtspSocket.setblocking(False)
sel.register(rtspSocket, selectors.EVENT_READ, data=None)

while True:
    events = sel.select(timeout=None)
    for key, mask in events:
        if key.data is None:
            # Accept new client
            conn, addr = rtspSocket.accept()
            conn.setblocking(False)
            worker = ServerWorker(clientInfo)
            sel.register(conn, selectors.EVENT_READ, data=worker)
        else:
            # Process RTSP request from existing client
            worker = key.data
            data = conn.recv(256)
            worker.processRtspRequest(data.decode('utf-8'))
```

**Ưu điểm**: Xử lý nhiều client đồng thời trên một luồng duy nhất, tiết kiệm tài nguyên.

### 3.4 HD Video Streaming (TCP)

**File**: `ServerWorker.py`, `Client.py`

Khi Client chọn HD mode:
- SETUP request gửi `Transport: RTP/TCP`
- Server dùng **TCP Interleaved** (RFC 2326 §10.12) để gửi RTP qua chính kênh RTSP:

```
Frame format: $ (1 byte) | Channel (1 byte) | Length (2 bytes big-endian) | RTP data
```

- Server sử dụng `HDVideoStream` để đọc file MJPEG chuẩn (scan SOI `\xff\xd8` → EOI `\xff\xd9`).
- Client dùng `_recvRtpTcp()` để đọc interleaved frame từ TCP socket.

### 3.5 Client-Side Caching

**File**: `Client.py`

- Sử dụng `queue.Queue` (thread-safe) làm frame buffer.
- Khi PLAY, Client bắt đầu nhận RTP trên worker thread.
- Frames được ghi vào buffer, không hiển thị ngay.
- Khi buffer đạt **PREBUFFER_SIZE = 10 frames**, bắt đầu phát.
- Main thread drain buffer qua `tkinter.after()` (thread-safe UI update).

```python
# Worker thread: nhận RTP → ghi vào buffer
self.frameBuffer.put(imageFile)

# Main thread: drain buffer → hiển thị
if self.bufferReady and not self.frameBuffer.empty():
    imageFile = self.frameBuffer.get_nowait()
    self.updateMovie(imageFile)
```

### 3.6 Chuyển đổi SD/HD

- GUI có checkbox "HD (TCP)".
- Khi toggle trong trạng thái READY hoặc PLAYING:
  1. Tự động gửi TEARDOWN kết thúc session hiện tại.
  2. Đợi 300ms → reconnect → gửi SETUP mới với transport tương ứng.
  3. Client reset toàn bộ state (sessionId, frameNbr, buffer).

---

## 4. Cấu Trúc File

```
src/python_rtp/
├── Server.py           # RTSP Server - I/O Multiplexing (selectors)
├── ServerWorker.py     # Xử lý phiên RTSP/RTP cho mỗi client
├── Client.py           # RTSP Client + GUI + Caching
├── ClientLauncher.py   # Entry point cho Client
├── RtpPacket.py        # Encode/Decode RTP packets (RFC 1889)
├── VideoStream.py      # Đọc video SD (skeleton format) + HD (MJPEG chuẩn)
├── test_rtp.py         # Unit tests (9 test cases)
├── movie.Mjpeg         # File video mẫu
└── requirements.txt    # Dependencies (Pillow)
```

---

## 5. Hướng Dẫn Chạy

### 5.1 Cài đặt
```bash
pip install -r requirements.txt
```

### 5.2 Khởi chạy Server
```bash
python Server.py 8554
```

### 5.3 Khởi chạy Client
```bash
python ClientLauncher.py localhost 8554 25000 movie.Mjpeg
```

### 5.4 Sử dụng
1. Click **Setup** → Thiết lập phiên.
2. Click **Play** → Bắt đầu phát video (đợi buffer đầy).
3. Click **Pause** → Tạm dừng.
4. Tick **HD (TCP)** → Tự động chuyển sang chế độ HD.
5. Click **Teardown** → Kết thúc phiên.

### 5.5 Chạy Tests
```bash
python test_rtp.py
```

---

## 6. Kết Quả Kiểm Thử

### 6.1 Unit Tests

| # | Test Case | Kết Quả |
|:---|:---|:---|
| 1 | encode/decode roundtrip | ✅ PASS |
| 2 | RTP version field = 2 | ✅ PASS |
| 3 | Payload type MJPEG = 26 | ✅ PASS |
| 4 | Sequence number boundaries (0, 255, 256, 65535) | ✅ PASS |
| 5 | Empty payload handling | ✅ PASS |
| 6 | Header byte 0 format (V=2) | ✅ PASS |
| 7 | Marker bit encoding | ✅ PASS |
| 8 | HDVideoStream single frame | ✅ PASS |
| 9 | HDVideoStream multiple frames | ✅ PASS |

### 6.2 End-to-End Tests

| # | Kịch bản | Kết Quả |
|:---|:---|:---|
| 1 | Server khởi động trên port 8554 | ✅ Thành công |
| 2 | Client kết nối TCP → Server | ✅ Thành công |
| 3 | SETUP → PLAY → Phát video SD | ✅ Thành công |
| 4 | PAUSE → PLAY → Tiếp tục phát | ✅ Thành công |
| 5 | TEARDOWN → Kết thúc phiên | ✅ Thành công |
| 6 | Toggle HD/SD → Auto re-SETUP | ✅ Thành công |
| 7 | Server không crash Unicode (Windows) | ✅ Đã fix |

---

## 7. Tự Đánh Giá Theo Rubric

| No. | Yêu Cầu | Điểm Tối Đa | Tự Đánh Giá |
|:---|:---|:---|:---|
| 1 | RTSP Client + RTP Packetization + Fragmentation MTU | 4 pt | 4 pt |
| 2 | I/O Multiplexing | 1 pt | 1 pt |
| 3 | HD Video Streaming with TCP | 2 pt | 2 pt |
| 4 | Client-Side Caching + switch SD/HD | 2.5 pt | 2.5 pt |
| 5 | Report | 0.5 pt | 0.5 pt |
| | **Tổng** | **10 pt** | **10 pt** |

---

## 8. Phân Công Công Việc

| Thành Viên | Công Việc | Tỷ Lệ |
|:---|:---|:---|
| ___________ | ___________ | ___% |
| ___________ | ___________ | ___% |
| ___________ | ___________ | ___% |

---

## 9. Tham Khảo

1. RFC 2326 — Real Time Streaming Protocol (RTSP)
2. RFC 1889 — RTP: A Transport Protocol for Real-Time Applications
3. Python Documentation — `selectors` module
4. Python Documentation — `socket` module
5. Pillow Documentation — Image processing
