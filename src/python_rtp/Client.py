"""
@file Client.py
@description RTSP Client với:
             - Fragment reassembly (ghép lại các gói RTP phân mảnh)
             - Client-side Caching (queue.Queue + pre-buffer N frames chống jitter)
             - Hỗ trợ HD Video qua TCP Interleaved (RFC 2326 §10.12)
             - Thread-safe UI update qua tkinter.after()
"""

from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, os, queue

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT  = ".jpg"
PREBUFFER_SIZE  = 10   # số frame tích lũy trước khi bắt đầu phát (chống jitter)


class Client:
    INIT    = 0
    READY   = 1
    PLAYING = 2
    state   = INIT

    SETUP    = 0
    PLAY     = 1
    PAUSE    = 2
    TEARDOWN = 3

    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master      = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.serverAddr  = serveraddr
        self.serverPort  = int(serverport)
        self.rtpPort     = int(rtpport)
        self.fileName    = filename
        self.rtspSeq     = 0
        self.sessionId   = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.frameNbr    = 0
        self.isHD        = False        # False = SD/UDP, True = HD/TCP

        # Frame buffer cho caching — thread-safe
        self.frameBuffer    = queue.Queue()
        self.bufferReady    = False     # True khi đủ PREBUFFER_SIZE frames
        self.fragmentBuf    = b''       # buffer ghép mảnh RTP
        self.currentFragSeq = -1        # seqnum của frame đang ghép

        self.createWidgets()
        self.connectToServer()

    def createWidgets(self):
        """Build GUI."""
        # Nút điều khiển
        self.setup = Button(self.master, width=20, padx=3, pady=3,
                            text="Setup", command=self.setupMovie)
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        self.start = Button(self.master, width=20, padx=3, pady=3,
                            text="Play", command=self.playMovie)
        self.start.grid(row=1, column=1, padx=2, pady=2)

        self.pause = Button(self.master, width=20, padx=3, pady=3,
                            text="Pause", command=self.pauseMovie)
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        self.teardown = Button(self.master, width=20, padx=3, pady=3,
                               text="Teardown", command=self.exitClient)
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        # Checkbox chuyển đổi SD/HD
        self.hdVar = IntVar()
        self.hdCheck = Checkbutton(self.master, text="HD (TCP)",
                                   variable=self.hdVar,
                                   command=self._onHdToggle)
        self.hdCheck.grid(row=2, column=0, columnspan=2, pady=2)

        # Nhãn hiển thị trạng thái buffer
        self.statusLabel = Label(self.master, text="Sẵn sàng", fg="gray")
        self.statusLabel.grid(row=2, column=2, columnspan=2, pady=2)

        # Label hiển thị video
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4,
                        sticky=W+E+N+S, padx=5, pady=5)

    # ── Button Handlers ────────────────────────────────────────────────────

    def _onHdToggle(self):
        self.isHD = bool(self.hdVar.get())
        mode = "HD/TCP" if self.isHD else "SD/UDP"
        self.statusLabel.config(text=f"Chế độ: {mode}")

    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        if os.path.exists(cachename):
            try:
                os.remove(cachename)
            except Exception:
                pass

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)

    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.bufferReady = False
            self.statusLabel.config(text=f"Đang buffer... (0/{PREBUFFER_SIZE})")
            threading.Thread(target=self.listenRtp, daemon=True).start()
            self.sendRtspRequest(self.PLAY)
            # Bắt đầu vòng lặp drain buffer trên main thread
            self.master.after(33, self._drainFrameBuffer)

    # ── RTP Listening & Fragment Reassembly ────────────────────────────────

    def listenRtp(self):
        """Lắng nghe RTP packets, ghép mảnh và đưa vào frame buffer."""
        while True:
            try:
                if self.isHD:
                    data = self._recvRtpTcp()
                else:
                    data = self.rtpSocket.recv(20480)

                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)

                    seqNum = rtpPacket.seqNum()
                    marker = (rtpPacket.header[1] >> 7) & 1   # bit 8

                    # Ghép mảnh: cùng seqNum → cùng frame
                    if seqNum != self.currentFragSeq:
                        self.fragmentBuf    = rtpPacket.getPayload()
                        self.currentFragSeq = seqNum
                    else:
                        self.fragmentBuf += rtpPacket.getPayload()

                    # Marker=1 → chunk cuối → frame hoàn chỉnh
                    if marker == 1:
                        if seqNum > self.frameNbr:
                            self.frameNbr = seqNum
                            imageFile = self.writeFrame(self.fragmentBuf)
                            self.frameBuffer.put(imageFile)
                        self.fragmentBuf = b''

            except Exception:
                if self.playEvent.isSet():
                    break
                if self.teardownAcked == 1:
                    if not self.isHD:
                        try:
                            self.rtpSocket.shutdown(socket.SHUT_RDWR)
                            self.rtpSocket.close()
                        except Exception:
                            pass
                    break

    def _recvRtpTcp(self):
        """Nhận một gói RTP qua TCP Interleaved (RFC 2326 §10.12).

        Format: $ (1B) | channel (1B) | length big-endian (2B) | RTP data
        """
        # Đọc 4-byte interleaved header
        header = b''
        while len(header) < 4:
            chunk = self.rtspSocket.recv(4 - len(header))
            if not chunk:
                return None
            header += chunk

        if header[0] != 0x24:   # bỏ qua nếu không phải '$'
            return None

        length = (header[2] << 8) | header[3]

        # Đọc đúng length bytes RTP data
        rtp_data = b''
        while len(rtp_data) < length:
            chunk = self.rtspSocket.recv(length - len(rtp_data))
            if not chunk:
                return None
            rtp_data += chunk

        return rtp_data

    def _drainFrameBuffer(self):
        """Drain frame buffer trên main thread — an toàn với Tkinter."""
        bufSize = self.frameBuffer.qsize()

        if not self.bufferReady:
            self.statusLabel.config(
                text=f"Buffering... ({min(bufSize, PREBUFFER_SIZE)}/{PREBUFFER_SIZE})")
            if bufSize >= PREBUFFER_SIZE:
                self.bufferReady = True
                self.statusLabel.config(text="Dang phat...")

        if self.bufferReady and not self.frameBuffer.empty():
            try:
                imageFile = self.frameBuffer.get_nowait()
                self.updateMovie(imageFile)
            except queue.Empty:
                pass

        if self.state == self.PLAYING:
            self.master.after(33, self._drainFrameBuffer)   # ~30 fps

    # ── File & UI Helpers ──────────────────────────────────────────────────

    def writeFrame(self, data):
        """Ghi frame ra file tạm. Trả về tên file."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        with open(cachename, "wb") as f:
            f.write(data)
        return cachename

    def updateMovie(self, imageFile):
        """Cập nhật frame lên GUI (gọi từ main thread)."""
        try:
            photo = ImageTk.PhotoImage(Image.open(imageFile))
            self.label.configure(image=photo, height=288)
            self.label.image = photo
        except Exception:
            pass

    # ── RTSP Protocol ──────────────────────────────────────────────────────

    def connectToServer(self):
        """Kết nối TCP đến Server (RTSP control channel)."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except Exception:
            tkinter.messagebox.showwarning(
                'Connection Failed',
                'Connection to \'%s\' failed.' % self.serverAddr)

    def sendRtspRequest(self, requestCode):
        """Gửi RTSP request đến server."""

        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply, daemon=True).start()
            self.rtspSeq += 1
            transport = ('RTP/TCP' if self.isHD
                         else f'RTP/UDP; client_port={self.rtpPort}')
            request = (f'SETUP {self.fileName} RTSP/1.0\n'
                       f'CSeq: {self.rtspSeq}\n'
                       f'Transport: {transport}\n\n')
            self.requestSent = self.SETUP

        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            self.rtspSeq += 1
            request = (f'PLAY {self.fileName} RTSP/1.0\n'
                       f'CSeq: {self.rtspSeq}\n'
                       f'Session: {self.sessionId}\n\n')
            self.requestSent = self.PLAY

        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            self.rtspSeq += 1
            request = (f'PAUSE {self.fileName} RTSP/1.0\n'
                       f'CSeq: {self.rtspSeq}\n'
                       f'Session: {self.sessionId}\n\n')
            self.requestSent = self.PAUSE

        # Teardown request
        elif requestCode == self.TEARDOWN and self.state != self.INIT:
            self.rtspSeq += 1
            request = (f'TEARDOWN {self.fileName} RTSP/1.0\n'
                       f'CSeq: {self.rtspSeq}\n'
                       f'Session: {self.sessionId}\n\n')
            self.requestSent = self.TEARDOWN
        else:
            return

        self.rtspSocket.send(request.encode())
        print('\nData sent:\n' + request)

    def recvRtspReply(self):
        """Nhận RTSP reply từ server (chạy trên thread riêng)."""
        while True:
            reply = self.rtspSocket.recv(1024)
            if reply:
                self.parseRtspReply(reply.decode("utf-8"))
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break

    def parseRtspReply(self, data):
        """Phân tích RTSP reply và cập nhật trạng thái Client."""
        lines  = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])

        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            if self.sessionId == 0:
                self.sessionId = session

            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200:
                    if self.requestSent == self.SETUP:
                        self.state = self.READY
                        self.openRtpPort()
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY
                        self.playEvent.set()
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT
                        self.teardownAcked = 1

    def openRtpPort(self):
        """Mở UDP socket nhận RTP (chỉ dùng khi transport = UDP)."""
        if self.isHD:
            return  # TCP mode: dùng lại rtspSocket
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.settimeout(0.5)
        try:
            self.rtpSocket.bind(('', self.rtpPort))
        except Exception:
            tkinter.messagebox.showwarning(
                'Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

    def handler(self):
        """Handler khi người dùng đóng cửa sổ."""
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:
            self.playMovie()
