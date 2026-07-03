# Video Streaming with RTSP and RTP

Demo Python truyền video MJPEG với **RTSP** làm giao thức điều khiển và **RTP** làm giao thức truyền dữ liệu media. Dự án triển khai state machine RTSP phía client, đóng gói RTP phía server, phân mảnh frame, chuyển đổi SD/HD theo transport, buffering phía client và giao diện Tkinter để điều khiển phát video.

## Tính Năng

- Lệnh RTSP: `SETUP`, `PLAY`, `PAUSE`, `TEARDOWN`.
- Đóng gói RTP với header 12 bytes, RTP version `2` và MJPEG payload type `26`.
- Phân mảnh frame khi payload lớn hơn kích thước an toàn theo MTU.
- RTP over UDP cho mode `SD / UDP`.
- RTP over TCP interleaved cho mode `HD / TCP`.
- Pre-buffer phía client bằng `queue.Queue`.
- Giao diện Tkinter/ttk hiển thị RTSP state, transport mode, session id và trạng thái buffer.
- Server xử lý RTSP socket bằng `selectors.DefaultSelector()`.

## Cấu Trúc Dự Án

```text
.
├── docs/                         # Yêu cầu, ghi chú kiến trúc, kế hoạch triển khai, báo cáo
├── Project_01/                   # Tài nguyên đề bài gốc
├── src/python_rtp/
│   ├── Client.py                 # GUI client, RTSP requests, logic nhận/buffer RTP
│   ├── ClientLauncher.py         # Entry point của client
│   ├── Server.py                 # RTSP server dùng selectors
│   ├── ServerWorker.py           # Xử lý RTSP session và stream RTP
│   ├── RtpPacket.py              # Encode/decode RTP
│   ├── VideoStream.py            # Đọc frame MJPEG
│   ├── movie.Mjpeg               # Video mẫu
│   ├── requirements.txt          # Python dependencies
│   └── test_rtp.py               # Unit tests
└── README.md
```

## Cài Đặt Và Chạy

Cài dependencies:

```bash
pip install -r src/python_rtp/requirements.txt
```

Chạy server:

```bash
cd src/python_rtp
python Server.py 8554
```

Mở terminal khác và chạy client:

```bash
cd src/python_rtp
python ClientLauncher.py localhost 8554 26000 movie.Mjpeg

python ClientLauncher.py localhost 8554 26000 AVATAR3_SD.Mjpeg
python ClientLauncher.py localhost 8554 26002 AVATAR3_HD.Mjpeg
python ClientLauncher.py localhost 8554 26004 AVATAR3_FHD.Mjpeg
```

## Cách Sử Dụng

1. Chọn `SD / UDP` hoặc `HD / TCP`.
2. Bấm `Setup`.
3. Bấm `Play`.
4. Dùng `Pause` và `Play` để tạm dừng/tiếp tục.
5. Bấm `Teardown` để đóng RTSP session và dọn cache frame tạm.

Thanh trạng thái trên GUI hiển thị RTSP state hiện tại, transport mode, session id và mức buffer.

## Streaming Modes

| Mode | Transport | Mô tả |
|---|---|---|
| `SD / UDP` | RTP over UDP | Client gửi `Transport: RTP/UDP; client_port=...`; server gửi RTP packets đến UDP port đã chọn. |
| `HD / TCP` | RTP over TCP interleaved | Client gửi `Transport: RTP/TCP`; server gửi RTP frames qua RTSP TCP socket với định dạng `$ | channel | length | RTP data`. |

Hai mode có thể dùng cùng file video mẫu, nên chất lượng hình ảnh có thể trông giống nhau nếu chưa cung cấp file HD riêng. Trong phiên bản này, khác biệt chính là cơ chế truyền tải.

## Kiểm Thử

Chạy unit tests:

```bash
cd src/python_rtp
python test_rtp.py
```

Kiểm tra cú pháp Python:

```bash
python -m py_compile Client.py Server.py ServerWorker.py RtpPacket.py VideoStream.py ClientLauncher.py test_rtp.py
```

Kết quả mong đợi:

- Toàn bộ 9 tests trong `test_rtp.py` pass.
- `py_compile` kết thúc không có lỗi.

## Mapping Với Yêu Cầu Bài Tập

| Yêu cầu | File chính |
|---|---|
| RTSP client, RTP packetization, UDP, fragmentation | `Client.py`, `ServerWorker.py`, `RtpPacket.py` |
| I/O multiplexing | `Server.py` |
| HD streaming with TCP | `Client.py`, `ServerWorker.py`, `VideoStream.py` |
| Client-side caching và chuyển đổi SD/HD | `Client.py` |
| Báo cáo | `docs/Report.md` |

## Tài Liệu

- Đề bài: `Project Socket Programming.md`
- Báo cáo kỹ thuật: `docs/Report.md`
- Ghi chú kiến trúc: `docs/020-architecture/`
- Ghi chú triển khai: `docs/040-implementation/`

## Ghi Chú

- File cache frame khi chạy có dạng `cache-*.jpg` và đã được ignore khỏi Git.
- Console của server và client in RTSP requests, session và transport mode để hỗ trợ demo/debug.
