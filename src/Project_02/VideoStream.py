class VideoStream:
    """
    Đọc file video MJPEG thô (chuỗi các ảnh JPEG nối tiếp nhau).
    Sử dụng việc quét tìm marker SOI (\\xff\\xd8) và EOI (\\xff\\xd9) để nhận diện frame.
    Tự động lặp lại video (loop) khi phát hết.
    """
    SOI = b'\xff\xd8'
    EOI = b'\xff\xd9'

    def __init__(self, filename):
        self.filename = filename
        self.file = None
        self.frameNum = 0
        self._buf = b''
        self.open_file()

    def open_file(self):
        """Mở file hoặc reset con trỏ file về đầu."""
        try:
            if self.file:
                self.file.close()
            self.file = open(self.filename, 'rb')
            self._buf = b''
        except OSError:
            raise IOError(f"Không thể mở file video: {self.filename}")

    def nextFrame(self):
        """Lấy dữ liệu JPEG thô của frame tiếp theo. Tự động loop lại từ đầu nếu hết video."""
        CHUNK_SIZE = 4096

        while True:
            chunk = self.file.read(CHUNK_SIZE)
            
            # Nếu hết file và buffer trống -> Loop lại video từ đầu
            if not chunk and not self._buf:
                self.open_file()
                continue
                
            if chunk:
                self._buf += chunk

            # Tìm kiếm marker bắt đầu của JPEG (SOI)
            soi_pos = self._buf.find(self.SOI)
            if soi_pos == -1:
                # Không tìm thấy SOI, dọn dẹp buffer chỉ giữ lại byte cuối đề phòng bị cắt đôi marker
                self._buf = self._buf[-1:] if self._buf else b''
                if not chunk:
                    self.open_file()
                continue

            # Loại bỏ phần dữ liệu thừa trước SOI (nếu có)
            if soi_pos > 0:
                self._buf = self._buf[soi_pos:]

            # Tìm kiếm marker kết thúc của JPEG (EOI) sau SOI
            eoi_pos = self._buf.find(self.EOI, 2)
            if eoi_pos != -1:
                # Cắt ra frame JPEG hoàn chỉnh
                frame = self._buf[:eoi_pos + 2]
                # Cập nhật buffer phần dữ liệu còn lại
                self._buf = self._buf[eoi_pos + 2:]
                self.frameNum += 1
                return frame

            # Nếu đọc hết file nhưng chưa tìm thấy EOI -> Loop lại video
            if not chunk:
                self.open_file()
                continue

    def frameNbr(self):
        """Lấy số thứ tự frame hiện tại."""
        return self.frameNum

    def close(self):
        """Đóng file video."""
        if self.file:
            self.file.close()
