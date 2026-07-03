class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
        except OSError:
            raise IOError
        self.frameNum = 0
        self._buf = b''

    def _read_jpeg_frame(self):
        """Read a JPEG frame by scanning SOI/EOI markers."""
        soi = b'\xff\xd8'
        eoi = b'\xff\xd9'
        chunk_size = 4096

        while True:
            chunk = self.file.read(chunk_size)
            if not chunk and not self._buf:
                return b''
            if chunk:
                self._buf += chunk

            soi_pos = self._buf.find(soi)
            if soi_pos == -1:
                self._buf = self._buf[-1:] if self._buf else b''
                if not chunk:
                    return b''
                continue

            if soi_pos > 0:
                self._buf = self._buf[soi_pos:]

            eoi_pos = self._buf.find(eoi, 2)
            if eoi_pos != -1:
                frame = self._buf[:eoi_pos + 2]
                self._buf = self._buf[eoi_pos + 2:]
                self.frameNum += 1
                return frame

            if not chunk:
                return b''

    def nextFrame(self):
        """Get next frame."""
        if self._buf:
            return self._read_jpeg_frame()

        pos = self.file.tell()
        data = self.file.read(5)
        if not data:
            if self._buf:
                return self._read_jpeg_frame()
            return b''

        try:
            framelength = int(data)
        except ValueError:
            self.file.seek(pos)
            return self._read_jpeg_frame()

        frame = self.file.read(framelength)
        if frame:
            self.frameNum += 1
            return frame

        self.file.seek(pos)
        return self._read_jpeg_frame()

    def frameNbr(self):
        """Get frame number."""
        return self.frameNum


class HDVideoStream:
    """Read standard MJPEG files by scanning for JPEG SOI/EOI markers.

    Standard MJPEG: concatenated JPEG images without a length prefix.
    Each frame starts with SOI (\\xff\\xd8) and ends with EOI (\\xff\\xd9).
    """

    SOI = b'\xff\xd8'
    EOI = b'\xff\xd9'

    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
        except OSError:
            raise IOError
        self.frameNum = 0
        self._buf = b''

    def _read_jpeg_frame(self):
        """Get next JPEG frame by scanning SOI/EOI markers."""
        CHUNK = 4096

        while True:
            chunk = self.file.read(CHUNK)
            if not chunk and not self._buf:
                return b''
            if chunk:
                self._buf += chunk

            soi_pos = self._buf.find(self.SOI)
            if soi_pos == -1:
                self._buf = self._buf[-1:] if self._buf else b''
                if not chunk:
                    return b''
                continue

            if soi_pos > 0:
                self._buf = self._buf[soi_pos:]

            eoi_pos = self._buf.find(self.EOI, 2)
            if eoi_pos != -1:
                frame = self._buf[:eoi_pos + 2]
                self._buf = self._buf[eoi_pos + 2:]
                self.frameNum += 1
                return frame

            if not chunk:
                return b''

    def nextFrame(self):
        return self._read_jpeg_frame()

    def frameNbr(self):
        """Get frame number."""
        return self.frameNum
