# Video Streaming with RTSP and RTP

Ứng dụng demo streaming video bằng **RTSP** cho kênh điều khiển và **RTP** cho dữ liệu media. Dự án được xây dựng cho môn **Lập Trình Mạng**, tập trung vào RTSP client state machine, RTP packetization, fragmentation, I/O multiplexing, TCP interleaved streaming và client-side buffering.

## Độc Giả Mục Tiêu

README này viết cho:

- **Giảng viên/người chấm bài**: cần chạy nhanh demo, đối chiếu chức năng với rubric và xem điểm kỹ thuật chính.
- **Thành viên nhóm phát triển**: cần biết cấu trúc thư mục, lệnh chạy, test và cách demo ổn định.
- **Người đọc GitHub**: cần hiểu dự án làm gì, chạy thế nào và giới hạn hiện tại.

## Tính Năng Chính

- RTSP client với các lệnh `SETUP`, `PLAY`, `PAUSE`, `TEARDOWN`.
- RTP packetization phía server với header 12 bytes, `V=2`, `PT=26` cho MJPEG.
- Fragmentation cho frame vượt MTU, marker bit đánh dấu mảnh cuối.
- SD mode: RTP truyền qua UDP.
- HD mode: RTP truyền qua TCP interleaved trên RTSP socket.
- Client-side buffering bằng `queue.Queue`, pre-buffer 10 frames.
- GUI Tkinter/ttk có trạng thái `INIT`, `READY`, `PLAYING`, mode `SD/UDP` và `HD/TCP`.
- Server dùng `selectors.DefaultSelector()` để xử lý RTSP sockets bằng I/O multiplexing.

## Cấu Trúc Dự Án

```text
.
├── docs/                         # Tài liệu yêu cầu, kiến trúc, kế hoạch, báo cáo
├── Project_01/                   # Tài liệu đề bài và video demo gốc
├── src/python_rtp/
│   ├── Client.py                 # GUI client, RTSP requests, RTP receive/buffer
│   ├── ClientLauncher.py         # Entry point cho client
│   ├── Server.py                 # RTSP server dùng selectors
│   ├── ServerWorker.py           # Xử lý RTSP session và gửi RTP
│   ├── RtpPacket.py              # Encode/decode RTP packet
│   ├── VideoStream.py            # Đọc MJPEG skeleton/standard MJPEG
│   ├── movie.Mjpeg               # Video mẫu
│   ├── requirements.txt          # Dependencies
│   └── test_rtp.py               # Unit tests
└── README.md
```

## Yêu Cầu Môi Trường

- Python 3.10+ khuyến nghị.
- Windows/Linux/macOS đều có thể chạy, miễn là Python có Tkinter.
- Dependency Python:

```bash
pip install -r src/python_rtp/requirements.txt
```

## Cách Chạy Demo

Mở terminal tại thư mục source:

```bash
cd src/python_rtp
```

Chạy server:

```bash
python Server.py 8554
```

Mở terminal khác và chạy client:

```bash
python ClientLauncher.py localhost 8554 26000 movie.Mjpeg
```

Thao tác trên GUI:

1. Chọn `SD / UDP` hoặc `HD / TCP`.
2. Bấm `Setup`.
3. Bấm `Play`.
4. Có thể bấm `Pause`, sau đó `Play` để tiếp tục.
5. Bấm `Teardown` để kết thúc session và dọn cache frame.

## SD/UDP Và HD/TCP Khác Nhau Thế Nào?

| Mode | Transport | Cách hoạt động |
|---|---|---|
| `SD / UDP` | RTP over UDP | Client gửi `Transport: RTP/UDP; client_port=...`, server gửi RTP qua UDP socket. |
| `HD / TCP` | RTP over TCP interleaved | Client gửi `Transport: RTP/TCP`, server gửi RTP qua chính RTSP TCP socket với frame `$ | channel | length | RTP data`. |

Lưu ý: nếu cả hai mode cùng dùng `movie.Mjpeg`, chất lượng hình ảnh nhìn thấy có thể giống nhau. Khác biệt chính trong phiên bản hiện tại là **cơ chế truyền tải**. Muốn demo khác biệt chất lượng thật sự cần chuẩn bị file video HD riêng.

## Kiểm Thử

Chạy unit tests:

```bash
cd src/python_rtp
python test_rtp.py
```

Kiểm tra cú pháp:

```bash
python -m py_compile Client.py Server.py ServerWorker.py RtpPacket.py VideoStream.py ClientLauncher.py test_rtp.py
```

Kết quả mong đợi:

- `test_rtp.py`: pass toàn bộ 9 tests.
- `py_compile`: không in lỗi.

## Mapping Với Rubric

| Yêu cầu | Vị trí chính |
|---|---|
| RTSP client + RTP packetization + UDP + fragmentation | `Client.py`, `ServerWorker.py`, `RtpPacket.py` |
| I/O multiplexing | `Server.py` |
| HD streaming with TCP | `Client.py`, `ServerWorker.py`, `VideoStream.py` |
| Client-side caching + switch SD/HD | `Client.py` |
| Report | `docs/Report.md` |

## Ghi Chú Khi Demo

- Server console có log mode transport khi `SETUP` và `PLAY`.
- Client console có log request RTSP, `CSeq`, `Session` và mode hiện tại.
- GUI status bar thể hiện `State`, `Transport`, `Session`, `Buffer`.
- File cache frame có dạng `cache-*.jpg` là runtime artifact và được ignore trong Git.
