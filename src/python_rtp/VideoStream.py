class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
        except OSError:
            raise IOError
        self.frameNum = 0

    def nextFrame(self):
        """Get next frame."""
        data = self.file.read(5)  # Get the framelength from the first 5 bits
        if data:
            framelength = int(data)

            # Read the current frame
            data = self.file.read(framelength)
            self.frameNum += 1
        return data

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

    def nextFrame(self):
        """Get next JPEG frame by scanning SOI/EOI markers."""
        CHUNK = 4096

        while True:
            chunk = self.file.read(CHUNK)
            if not chunk and not self._buf:
                return b''
            if chunk:
                self._buf += chunk

            # Find SOI marker
            soi_pos = self._buf.find(self.SOI)
            if soi_pos == -1:
                # No SOI found — discard buffer keeping last byte (could be partial 0xff)
                self._buf = self._buf[-1:] if self._buf else b''
                if not chunk:
                    return b''
                continue

            # Trim anything before SOI
            if soi_pos > 0:
                self._buf = self._buf[soi_pos:]

            # Find EOI marker after SOI
            eoi_pos = self._buf.find(self.EOI, 2)
            if eoi_pos != -1:
                # Complete frame found
                frame = self._buf[:eoi_pos + 2]
                self._buf = self._buf[eoi_pos + 2:]
                self.frameNum += 1
                return frame

            # EOI not yet found — need more data
            if not chunk:
                return b''
            # continue reading

    def frameNbr(self):
        """Get frame number."""
        return self.frameNum