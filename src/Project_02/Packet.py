import struct

class Packet:
    """
    Custom Packet Format for Video Streaming Project 02.
    
    Header structure (12 bytes):
      - Global Sequence Number (4 bytes): unsigned int (I)
      - Frame ID               (2 bytes): unsigned short (H)
      - Fragment Index         (2 bytes): unsigned short (H)
      - Total Fragments        (2 bytes): unsigned short (H)
      - Data Length            (2 bytes): unsigned short (H)
    Format string: '!IHHHH'
    """
    HEADER_SIZE = 12

    def __init__(self):
        self.global_seq = 0
        self.frame_id = 0
        self.frag_index = 0
        self.total_frags = 0
        self.data_len = 0
        self.payload = b''

    def encode(self, global_seq, frame_id, frag_index, total_frags, payload):
        """Đóng gói dữ liệu header và payload thành gói tin bytes nhị phân."""
        self.global_seq = global_seq
        self.frame_id = frame_id
        self.frag_index = frag_index
        self.total_frags = total_frags
        self.payload = payload
        self.data_len = len(payload)
        
        # Đóng gói 12 bytes header
        header = struct.pack(
            '!IHHHH',
            self.global_seq,
            self.frame_id,
            self.frag_index,
            self.total_frags,
            self.data_len
        )
        return header + self.payload

    def decode(self, byte_stream):
        """Giải gói dữ liệu nhị phân nhận được từ mạng."""
        if len(byte_stream) < self.HEADER_SIZE:
            raise ValueError("Gói tin nhận được có kích thước nhỏ hơn Header kích thước tối thiểu (12 bytes)")
        
        header_bytes = byte_stream[:self.HEADER_SIZE]
        self.payload = byte_stream[self.HEADER_SIZE:]
        
        # Giải nén 12 bytes header
        (
            self.global_seq,
            self.frame_id,
            self.frag_index,
            self.total_frags,
            self.data_len
        ) = struct.unpack('!IHHHH', header_bytes)

        # Xác thực độ dài dữ liệu thực tế nhận được
        if len(self.payload) != self.data_len:
            self.payload = self.payload[:self.data_len]
            
    def get_packet(self):
        """Lấy toàn bộ gói tin (header + payload)."""
        header = struct.pack(
            '!IHHHH',
            self.global_seq,
            self.frame_id,
            self.frag_index,
            self.total_frags,
            self.data_len
        )
        return header + self.payload
