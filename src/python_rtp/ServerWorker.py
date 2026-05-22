"""
@file ServerWorker.py
@description Xử lý phiên RTSP/RTP của từng client.
             Được điều khiển bởi I/O Multiplexing (selectors) ở Server.py.
             Hỗ trợ: Fragmentation (MTU), TCP Interleaved (RFC 2326 §10.12).
"""

from random import randint
import threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket

MAX_PAYLOAD = 1400  # bytes — an toàn dưới MTU Ethernet (1500)


class ServerWorker:

    SETUP    = 'SETUP'
    PLAY     = 'PLAY'
    PAUSE    = 'PAUSE'
    TEARDOWN = 'TEARDOWN'

    INIT    = 0
    READY   = 1
    PLAYING = 2

    OK_200            = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500        = 2

    def __init__(self, clientInfo):
        self.clientInfo = clientInfo
        self.state = self.INIT  # instance attribute — tránh shared state giữa các clients

    def processRtspRequest(self, data):
        """Xử lý yêu cầu RTSP từ client (được gọi bởi selector event loop)."""
        request = data.split('\n')
        line1 = request[0].split(' ')
        requestType = line1[0]
        filename = line1[1]
        seq = request[1].split(' ')

        # ── SETUP ──────────────────────────────────────────────────────────
        if requestType == self.SETUP:
            if self.state == self.INIT:
                print("processing SETUP\n")
                try:
                    self.clientInfo['videoStream'] = VideoStream(filename)
                    self.state = self.READY
                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
                    return

                self.clientInfo['session'] = randint(100000, 999999)

                # Phát hiện transport mode: UDP (SD) hoặc TCP (HD)
                transport_line = request[2] if len(request) > 2 else ''
                self.clientInfo['transport'] = 'TCP' if 'RTP/TCP' in transport_line else 'UDP'

                self.replyRtsp(self.OK_200, seq[1])

                # Lưu RTP port (chỉ dùng khi UDP)
                if self.clientInfo['transport'] == 'UDP':
                    try:
                        self.clientInfo['rtpPort'] = request[2].split(' ')[3]
                    except (IndexError, ValueError):
                        self.clientInfo['rtpPort'] = '25000'

        # ── PLAY ───────────────────────────────────────────────────────────
        elif requestType == self.PLAY:
            if self.state == self.READY:
                print("processing PLAY\n")
                self.state = self.PLAYING

                # Chỉ tạo UDP socket khi transport là UDP
                if self.clientInfo.get('transport') != 'TCP':
                    self.clientInfo['rtpSocket'] = socket.socket(
                        socket.AF_INET, socket.SOCK_DGRAM)

                self.replyRtsp(self.OK_200, seq[1])

                # Thread gửi RTP (daemon — tự kết thúc khi main thread thoát)
                self.clientInfo['event'] = threading.Event()
                t = threading.Thread(target=self.sendRtp)
                t.daemon = True
                self.clientInfo['worker'] = t
                t.start()

        # ── PAUSE ──────────────────────────────────────────────────────────
        elif requestType == self.PAUSE:
            if self.state == self.PLAYING:
                print("processing PAUSE\n")
                self.state = self.READY
                self.clientInfo['event'].set()
                self.replyRtsp(self.OK_200, seq[1])

        # ── TEARDOWN ───────────────────────────────────────────────────────
        elif requestType == self.TEARDOWN:
            print("processing TEARDOWN\n")
            if 'event' in self.clientInfo:
                self.clientInfo['event'].set()
            self.replyRtsp(self.OK_200, seq[1])
            if 'rtpSocket' in self.clientInfo:
                try:
                    self.clientInfo['rtpSocket'].close()
                except Exception:
                    pass

    def sendRtp(self):
        """Gửi RTP packet qua UDP hoặc TCP. Có hỗ trợ Fragmentation (MTU-safe)."""
        while True:
            if self.clientInfo['event'].wait(0.05):
                break

            data = self.clientInfo['videoStream'].nextFrame()
            if data:
                frameNumber = self.clientInfo['videoStream'].frameNbr()
                try:
                    # Fragmentation: chia frame thành chunk <= MAX_PAYLOAD bytes
                    chunks = [data[i:i + MAX_PAYLOAD]
                              for i in range(0, len(data), MAX_PAYLOAD)]

                    for i, chunk in enumerate(chunks):
                        marker = 1 if i == len(chunks) - 1 else 0
                        rtp_data = self.makeRtp(chunk, frameNumber, marker)

                        if self.clientInfo.get('transport') == 'TCP':
                            self._sendRtpInterleaved(rtp_data)
                        else:
                            address = self.clientInfo['rtspSocket'][1][0]
                            port = int(self.clientInfo['rtpPort'])
                            self.clientInfo['rtpSocket'].sendto(
                                rtp_data, (address, port))
                except Exception as e:
                    print(f"[Server] Lỗi gửi RTP: {e}")

    def _sendRtpInterleaved(self, rtp_data):
        """Gửi RTP qua TCP dùng Interleaved Frame (RFC 2326 §10.12).

        Cấu trúc: $ (1B) | channel 0 (1B) | length big-endian (2B) | RTP data
        """
        conn = self.clientInfo['rtspSocket'][0]
        length = len(rtp_data)
        header = bytearray(4)
        header[0] = 0x24          # '$'
        header[1] = 0             # channel 0 = video
        header[2] = (length >> 8) & 0xFF
        header[3] = length & 0xFF
        try:
            conn.sendall(bytes(header) + rtp_data)
        except Exception as e:
            print(f"[Server] Lỗi TCP interleaved: {e}")

    def makeRtp(self, payload, frameNbr, marker=0):
        """Đóng gói chunk video thành gói RTP."""
        rtpPacket = RtpPacket()
        rtpPacket.encode(
            version=2, padding=0, extension=0, cc=0,
            seqnum=frameNbr, marker=marker, pt=26, ssrc=0,
            payload=payload)
        return rtpPacket.getPacket()

    def replyRtsp(self, code, seq):
        """Gửi RTSP reply về client."""
        if code == self.OK_200:
            reply = ('RTSP/1.0 200 OK\nCSeq: ' + seq +
                     '\nSession: ' + str(self.clientInfo['session']))
            conn = self.clientInfo['rtspSocket'][0]
            try:
                conn.send(reply.encode())
            except Exception as e:
                print(f"[Server] Lỗi gửi RTSP reply: {e}")
        elif code == self.FILE_NOT_FOUND_404:
            print("404 NOT FOUND")
        elif code == self.CON_ERR_500:
            print("500 CONNECTION ERROR")
