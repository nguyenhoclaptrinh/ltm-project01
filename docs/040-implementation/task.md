# Danh Sách Công Việc (Task List) - Project Socket Programming

## 1. Thiết Lập & Chuẩn Bị
- [x] Phân tích yêu cầu và tài liệu hóa (PRD, Spec)
- [x] Giải nén và thiết lập môi trường mã nguồn mẫu
- [x] Khởi tạo Git repository

## 1.5. Architecture Doctor (Giai đoạn 0 — Vá Khẩn Cấp)
- [x] **[BL5-FIX]** Di chuyển `state` từ class-level → instance attr trong `ServerWorker.__init__`
- [x] **[BL2-FIX]** Sửa `tkMessageBox` Python 2 → `tkinter.messagebox`
- [x] **[BL2-FIX]** Thay thế bare `except:` → `except Exception`

## 2. Phát Triển Cơ Bản (4/10 điểm)
- [x] **Safety Net**: Viết `test_rtp.py` (6 unit tests, độc lập không cần GUI)
- [x] `RtpPacket.encode()` — 12-byte header RFC 1889 (4/4 tests PASS)
- [x] `Client.sendRtspRequest()` — SETUP, PLAY, PAUSE, TEARDOWN
- [x] `Client.parseRtspReply()` — state machine INIT→READY→PLAYING
- [x] `Client.openRtpPort()` — UDP socket với timeout 0.5s
- [x] Kiểm thử end-to-end: Server + Client → SETUP→PLAY→PAUSE→TEARDOWN

## 3. Tính Năng Nâng Cao (6/10 điểm còn lại)
- [x] **Fragmentation** (`ServerWorker.sendRtp`): chia frame > 1400 bytes thành nhiều gói RTP, marker=1 trên chunk cuối
- [x] **Fragment Reassembly** (`Client.listenRtp`): ghép các chunk theo seqNum và marker bit
- [x] **I/O Multiplexing** (`Server.py`): dùng `selectors.DefaultSelector`, xử lý N clients trên 1 thread
- [x] **HD Video & TCP**:
    - [x] Client gửi `Transport: RTP/TCP` khi bật HD mode
    - [x] Server gửi RTP qua TCP Interleaved (`_sendRtpInterleaved`)
    - [x] Client nhận qua `_recvRtpTcp()` (parse header `$ | ch | len | data`)
- [x] **Client-Side Caching**:
    - [x] `queue.Queue` thread-safe frame buffer
    - [x] Pre-buffer 10 frames trước khi phát (chống jitter)
    - [x] `tkinter.after(33ms)` drain buffer trên main thread (thread-safe UI)
    - [x] Nút checkbox SD/HD chuyển đổi transport mode
- [x] Cleanup file cache an toàn (`with open` + `os.remove` trong `finally`-like)

## 4. Hoàn Thiện & Báo Cáo
- [x] Viết báo cáo cuối kỳ (Report)
- [x] Kiểm tra code style / syntax cơ bản (`py_compile`)
- [ ] Đóng gói sản phẩm (`MSSV1_MSSV2_MSSV3.zip`)
