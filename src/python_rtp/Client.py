"""
@file Client.py
@description RTSP Client với:
             - Fragment reassembly (ghép lại các gói RTP phân mảnh)
             - Client-side Caching (queue.Queue + pre-buffer N frames chống jitter)
             - Hỗ trợ HD Video qua TCP Interleaved (RFC 2326 §10.12)
             - Thread-safe UI update qua tkinter.after()
"""

from tkinter import *
from tkinter import ttk
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, os, queue, glob

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT  = ".jpg"
PREBUFFER_SIZE  = 10   # số frame tích lũy trước khi bắt đầu phát (chống jitter)


class Client:
    INIT    = 0
    READY   = 1
    PLAYING = 2

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
        self.state       = self.INIT   # instance attribute — tránh shared state
        self.isHD        = False        # False = SD/UDP, True = HD/TCP
        self.statusText  = "Ready"

        # Frame buffer cho caching — thread-safe
        self.frameBuffer    = queue.Queue()
        self.bufferReady    = False     # True khi đủ PREBUFFER_SIZE frames
        self.fragmentBuf    = b''       # buffer ghép mảnh RTP
        self.currentFragSeq = -1        # seqnum của frame đang ghép
        self.cacheFiles     = set()      # Track cache files for cleanup

        self._cleanupCache(all_sessions=True)
        self.createWidgets()
        self.connectToServer()

    def createWidgets(self):
        """Build GUI."""
        self.master.geometry("800x520")
        self.master.minsize(760, 500)
        self.master.configure(bg="#f4f6f8")
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)

        style = ttk.Style(self.master)
        style.configure("App.TFrame", background="#f4f6f8")
        style.configure("Toolbar.TFrame", background="#f4f6f8")
        style.configure("Status.TFrame", background="#eef2f6")
        style.configure("StatusLabel.TLabel", background="#eef2f6", foreground="#5f6b7a")
        style.configure("StatusValue.TLabel", background="#eef2f6", foreground="#17202a")
        style.configure("Mode.TLabelframe", background="#f4f6f8")
        style.configure("Mode.TLabelframe.Label", background="#f4f6f8", foreground="#3b4652")

        videoFrame = ttk.Frame(self.master, style="App.TFrame", padding=(12, 12, 12, 8))
        videoFrame.grid(row=0, column=0, sticky=N+S+E+W)
        videoFrame.rowconfigure(0, weight=1)
        videoFrame.columnconfigure(0, weight=1)

        self.label = Label(videoFrame, text="No video - click Setup then Play",
                           bg="#111827", fg="#d1d5db", anchor=CENTER,
                           font=("Segoe UI", 13))
        self.label.grid(row=0, column=0, sticky=N+S+E+W)

        controlFrame = ttk.Frame(self.master, style="Toolbar.TFrame", padding=(12, 0, 12, 8))
        controlFrame.grid(row=1, column=0, sticky=E+W)
        for col in range(4):
            controlFrame.columnconfigure(col, weight=1, uniform="actions")

        self.setup = ttk.Button(controlFrame, text="Setup", command=self.setupMovie)
        self.setup.grid(row=0, column=0, sticky=E+W, padx=(0, 6), ipady=5)

        self.start = ttk.Button(controlFrame, text="Play", command=self.playMovie)
        self.start.grid(row=0, column=1, sticky=E+W, padx=6, ipady=5)

        self.pause = ttk.Button(controlFrame, text="Pause", command=self.pauseMovie)
        self.pause.grid(row=0, column=2, sticky=E+W, padx=6, ipady=5)

        self.teardown = ttk.Button(controlFrame, text="Teardown", command=self.exitClient)
        self.teardown.grid(row=0, column=3, sticky=E+W, padx=(6, 0), ipady=5)

        modeFrame = ttk.LabelFrame(controlFrame, text="Transport Mode",
                                   style="Mode.TLabelframe", padding=(10, 4, 10, 6))
        modeFrame.grid(row=1, column=0, columnspan=4, sticky=W, pady=(8, 0))

        self.modeVar = StringVar(value="HD" if self.isHD else "SD")
        self.sdRadio = ttk.Radiobutton(modeFrame, text="SD / UDP",
                                       variable=self.modeVar, value="SD",
                                       command=self._onModeChange)
        self.sdRadio.grid(row=0, column=0, sticky=W, padx=(0, 18))

        self.hdRadio = ttk.Radiobutton(modeFrame, text="HD / TCP",
                                       variable=self.modeVar, value="HD",
                                       command=self._onModeChange)
        self.hdRadio.grid(row=0, column=1, sticky=W)

        statusFrame = ttk.Frame(self.master, style="Status.TFrame", padding=(12, 6, 12, 8))
        statusFrame.grid(row=2, column=0, sticky=E+W)
        statusFrame.columnconfigure(8, weight=1)

        ttk.Label(statusFrame, text="State:", style="StatusLabel.TLabel").grid(row=0, column=0, sticky=W)
        self.stateValue = ttk.Label(statusFrame, style="StatusValue.TLabel")
        self.stateValue.grid(row=0, column=1, sticky=W, padx=(4, 18))

        ttk.Label(statusFrame, text="Transport:", style="StatusLabel.TLabel").grid(row=0, column=2, sticky=W)
        self.transportValue = ttk.Label(statusFrame, style="StatusValue.TLabel")
        self.transportValue.grid(row=0, column=3, sticky=W, padx=(4, 18))

        ttk.Label(statusFrame, text="Session:", style="StatusLabel.TLabel").grid(row=0, column=4, sticky=W)
        self.sessionValue = ttk.Label(statusFrame, style="StatusValue.TLabel")
        self.sessionValue.grid(row=0, column=5, sticky=W, padx=(4, 18))

        ttk.Label(statusFrame, text="Buffer:", style="StatusLabel.TLabel").grid(row=0, column=6, sticky=W)
        self.bufferValue = ttk.Label(statusFrame, style="StatusValue.TLabel")
        self.bufferValue.grid(row=0, column=7, sticky=W, padx=(4, 18))

        self.statusLabel = ttk.Label(statusFrame, text=self.statusText,
                                     style="StatusLabel.TLabel", anchor=E)
        self.statusLabel.grid(row=0, column=8, sticky=E+W)

        self._updateUiState()

    # ── Button Handlers ────────────────────────────────────────────────────

    def _stateName(self):
        """Return current RTSP state as display text."""
        if self.state == self.READY:
            return "READY"
        if self.state == self.PLAYING:
            return "PLAYING"
        return "INIT"

    def _transportName(self):
        """Return selected transport mode as display text."""
        return "HD/TCP" if self.isHD else "SD/UDP"

    def _scheduleUiState(self):
        """Safely refresh UI state from worker threads."""
        try:
            self.master.after(0, self._updateUiState)
        except Exception:
            pass

    def _setStatus(self, text):
        """Set bottom status text and schedule a safe UI refresh."""
        self.statusText = text
        self._scheduleUiState()

    def _updateUiState(self):
        """Synchronize buttons, status bar, and selected transport mode."""
        if not hasattr(self, 'stateValue'):
            return

        self.modeVar.set("HD" if self.isHD else "SD")
        session = str(self.sessionId) if self.sessionId else "-"
        bufferSize = self.frameBuffer.qsize() if hasattr(self, 'frameBuffer') else 0

        self.stateValue.config(text=self._stateName())
        self.transportValue.config(text=self._transportName())
        self.sessionValue.config(text=session)
        self.bufferValue.config(text=f"{min(bufferSize, PREBUFFER_SIZE)}/{PREBUFFER_SIZE}")
        self.statusLabel.config(text=self.statusText)

        self.setup.config(state=NORMAL if self.state == self.INIT else DISABLED)
        self.start.config(state=NORMAL if self.state == self.READY else DISABLED)
        self.pause.config(state=NORMAL if self.state == self.PLAYING else DISABLED)
        self.teardown.config(state=NORMAL if self.state != self.INIT else DISABLED)

    def _showVideoPlaceholder(self):
        """Reset the video area to its empty-state message."""
        if hasattr(self, 'label'):
            self.label.configure(image='', text="No video - click Setup then Play",
                                 bg="#111827", fg="#d1d5db")
            self.label.image = None

    def _onModeChange(self):
        """Handle SD/HD radio changes. Auto re-SETUP if session is active."""
        newHD = self.modeVar.get() == "HD"
        if newHD == self.isHD:
            return
        self.isHD = newHD
        self._setStatus(f"Mode selected: {self._transportName()}")
        print(f"[Client] mode={self._transportName()}")

        # Auto re-SETUP if already in READY or PLAYING state
        if self.state in (self.READY, self.PLAYING):
            # Teardown current session
            self.sendRtspRequest(self.TEARDOWN)
            # Wait briefly for teardown to process, then reconnect and setup
            self.master.after(300, self._reconnectAndSetup)
        else:
            self._updateUiState()

    def _onHdToggle(self):
        """Backward-compatible alias for the old HD checkbox handler."""
        self._onModeChange()

    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)
        if hasattr(self, 'playEvent'):
            self.playEvent.set()
        # Cho receiver thread một nhịp dừng trước khi dọn file tạm.
        self.master.after(200, self._destroyAfterCleanup)

    def _destroyAfterCleanup(self):
        """Cleanup cache files, then close the GUI."""
        self._clearFrameBuffer(delete_files=True)
        self._cleanupCache(all_sessions=True)
        self.master.destroy()

    def _reconnectAndSetup(self):
        """Reconnect to server and send SETUP (used after HD/SD toggle)."""
        oldSessionId = self.sessionId
        if hasattr(self, 'playEvent'):
            self.playEvent.set()
        self._clearFrameBuffer(delete_files=True)
        self._cleanupCache(oldSessionId)
        # Close any existing RTP UDP socket to free the port before re-SETUP
        try:
            if hasattr(self, 'rtpSocket') and not self.isHD:
                try:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self.rtpSocket.close()
                except Exception:
                    pass
                try:
                    del self.rtpSocket
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.rtspSocket.close()
        except Exception:
            pass
        # Reset state for fresh session
        self.state = self.INIT
        self.sessionId = 0
        self.rtspSeq = 0
        self.frameNbr = 0
        self.teardownAcked = 0
        self.fragmentBuf = b''
        self.currentFragSeq = -1
        self.statusText = "Ready"
        self._showVideoPlaceholder()
        self._updateUiState()
        self.connectToServer()
        self.setupMovie()

    def _clearFrameBuffer(self, delete_files=False):
        """Clear queued frame file names and optionally delete the files."""
        while not self.frameBuffer.empty():
            try:
                imageFile = self.frameBuffer.get_nowait()
                if delete_files:
                    self._deleteCacheFile(imageFile)
            except queue.Empty:
                break

    def _deleteCacheFile(self, imageFile):
        """Delete one cache file if it exists."""
        try:
            if imageFile and os.path.exists(imageFile):
                os.remove(imageFile)
        except Exception:
            pass
        self.cacheFiles.discard(imageFile)

    def _cleanupCache(self, sessionId=None, all_sessions=False):
        """Remove all cache files for current session."""
        sessionId = self.sessionId if sessionId is None else sessionId
        if all_sessions:
            pattern = CACHE_FILE_NAME + '*' + CACHE_FILE_EXT
        else:
            pattern = CACHE_FILE_NAME + str(sessionId) + '*' + CACHE_FILE_EXT
        for f in glob.glob(pattern):
            self._deleteCacheFile(f)
        for f in list(self.cacheFiles):
            self._deleteCacheFile(f)

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
            self._setStatus(f"Buffering... (0/{PREBUFFER_SIZE})")

            if not self.isHD:
                # UDP: ensure RTP UDP socket is open (may have been closed on PAUSE)
                if not hasattr(self, 'rtpSocket'):
                    self.openRtpPort()
                # start listener before PLAY (separate socket, no conflict)
                threading.Thread(target=self.listenRtp, daemon=True).start()
            else:
                # HD/TCP: ensure RTSP reply receiver is running so PLAY reply
                # is read from the control socket and triggers listenRtp.
                threading.Thread(target=self.recvRtspReply, daemon=True).start()
            # TCP: listenRtp will be started by parseRtspReply after PLAY reply

            self.sendRtspRequest(self.PLAY)
            self.master.after(33, self._drainFrameBuffer)

    # ── RTP Listening & Fragment Reassembly ────────────────────────────────

    def listenRtp(self):
        """Lắng nghe RTP packets, ghép mảnh và đưa vào frame buffer."""
        while True:
            if hasattr(self, 'playEvent') and self.playEvent.isSet():
                break
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

                    # Fragment reassembly: same seqNum = same frame
                    if seqNum != self.currentFragSeq:
                        self.fragmentBuf    = rtpPacket.getPayload()
                        self.currentFragSeq = seqNum
                    else:
                        self.fragmentBuf += rtpPacket.getPayload()

                    # Marker=1 = last chunk = complete frame
                    if marker == 1:
                        if seqNum >= self.frameNbr:
                            self.frameNbr = seqNum
                            imageFile = self.writeFrame(self.fragmentBuf, seqNum)
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
        """Read one RTP packet or RTSP reply from TCP interleaved socket.

        TCP Interleaved (RFC 2326 s10.12):
          RTP frame:  $ (0x24) | channel (1B) | length (2B big-endian) | data
          RTSP reply: text starting with 'R' (e.g., 'RTSP/1.0 200 OK')

        Returns RTP payload bytes, or None if RTSP reply was parsed instead.
        """
        # Read first byte to determine data type
        first = self._recv_exact(1)
        if not first:
            return None

        if first[0] == 0x24:  # '$' = RTP interleaved frame
            rest = self._recv_exact(3)
            if not rest:
                return None
            length = (rest[1] << 8) | rest[2]
            rtp_data = self._recv_exact(length)
            return rtp_data
        else:
            # Text data: RTSP reply (e.g., for PAUSE/TEARDOWN during TCP playback)
            buf = first
            try:
                more = self.rtspSocket.recv(1024)
                if more:
                    buf += more
            except Exception:
                pass
            try:
                self.parseRtspReply(buf.decode('utf-8'))
            except Exception:
                pass
            return None

    def _recv_exact(self, n):
        """Read exactly n bytes from rtspSocket. Returns bytes or None."""
        buf = b''
        while len(buf) < n:
            chunk = self.rtspSocket.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _drainFrameBuffer(self):
        """Drain frame buffer trên main thread — an toàn với Tkinter."""
        bufSize = self.frameBuffer.qsize()

        if not self.bufferReady:
            self._setStatus(f"Buffering... ({min(bufSize, PREBUFFER_SIZE)}/{PREBUFFER_SIZE})")
            if bufSize >= PREBUFFER_SIZE:
                self.bufferReady = True
                self._setStatus("Playing")

        if self.bufferReady and not self.frameBuffer.empty():
            try:
                imageFile = self.frameBuffer.get_nowait()
                self.updateMovie(imageFile)
            except queue.Empty:
                pass

        if self.state == self.PLAYING or not self.frameBuffer.empty():
            self.master.after(33, self._drainFrameBuffer)   # ~30 fps

    # ── File & UI Helpers ──────────────────────────────────────────────────

    def writeFrame(self, data, frameNbr=None):
        """Ghi frame ra file tạm với tên unique. Trả về tên file."""
        # Dùng frameNbr làm suffix để tránh ghi đè giữa các frame
        suffix = frameNbr if frameNbr is not None else self.frameNbr
        cachename = CACHE_FILE_NAME + str(self.sessionId) + '-' + str(suffix) + CACHE_FILE_EXT
        with open(cachename, "wb") as f:
            f.write(data)
        self.cacheFiles.add(cachename)
        return cachename

    def updateMovie(self, imageFile):
        """Cập nhật frame lên GUI (gọi từ main thread)."""
        try:
            with Image.open(imageFile) as image:
                photo = ImageTk.PhotoImage(image.copy())
            self.label.configure(image=photo, text='', bg="#111827", height=288)
            self.label.image = photo
        except Exception:
            pass
        finally:
            self._deleteCacheFile(imageFile)

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
        print(f'\n[Client] mode={self._transportName()}\nData sent:\n{request}')

    def recvRtspReply(self):
        """Receive RTSP replies from server (runs on separate thread)."""
        while True:
            try:
                reply = self.rtspSocket.recv(1024)
            except Exception:
                break
            if reply:
                try:
                    self.parseRtspReply(reply.decode('utf-8'))
                except UnicodeDecodeError:
                    pass  # Binary data received — ignore
            if self.requestSent == self.TEARDOWN:
                try:
                    self.rtspSocket.shutdown(socket.SHUT_RDWR)
                    self.rtspSocket.close()
                except Exception:
                    pass
                break
            # TCP mode: stop after PLAY reply so listenRtp can take over
            if self.isHD and self.state == self.PLAYING:
                break

    def parseRtspReply(self, data):
        """Phân tích RTSP reply và cập nhật trạng thái Client."""
        try:
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
                            self._setStatus("Ready - click Play")
                            self.openRtpPort()
                        elif self.requestSent == self.PLAY:
                            self.state = self.PLAYING
                            self._setStatus("Playing")
                            if self.isHD:
                                # TCP: start RTP listener now that PLAY reply is received
                                # recvRtspReply will exit, listenRtp takes over the socket
                                threading.Thread(target=self.listenRtp, daemon=True).start()
                        elif self.requestSent == self.PAUSE:
                            self.state = self.READY
                            self._setStatus("Paused")
                            self.playEvent.set()
                            # Close UDP RTP socket on PAUSE to release bound port so
                            # the client can later re-bind (avoids "Unable to bind PORT" errors).
                            if not self.isHD:
                                try:
                                    if hasattr(self, 'rtpSocket'):
                                        try:
                                            self.rtpSocket.shutdown(socket.SHUT_RDWR)
                                        except Exception:
                                            pass
                                        try:
                                            self.rtpSocket.close()
                                        except Exception:
                                            pass
                                        try:
                                            del self.rtpSocket
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                        elif self.requestSent == self.TEARDOWN:
                            self.state = self.INIT
                            self.teardownAcked = 1
                            self._setStatus("Session closed")
                            self._clearFrameBuffer(delete_files=True)
                            self._cleanupCache(session)
                            self.master.after(0, self._showVideoPlaceholder)
                            # Ensure UDP socket is closed on TEARDOWN so port is released
                            if not self.isHD:
                                try:
                                    if hasattr(self, 'rtpSocket'):
                                        try:
                                            self.rtpSocket.shutdown(socket.SHUT_RDWR)
                                        except Exception:
                                            pass
                                        try:
                                            self.rtpSocket.close()
                                        except Exception:
                                            pass
                                        try:
                                            del self.rtpSocket
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                        self._scheduleUiState()
        except (ValueError, IndexError):
            pass  # Bỏ qua reply không đúng định dạng

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
