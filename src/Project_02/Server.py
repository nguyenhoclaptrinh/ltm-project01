import sys
import time
import socket
from VideoStream import VideoStream
from Packet import Packet

# Cấu hình encoding UTF-8 để hỗ trợ in tiếng Việt trên console Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass


MULTICAST_GRP = '239.1.1.1'
MULTICAST_PORT = 5004
MAX_PAYLOAD_SIZE = 1400  # Kích thước payload tối đa trong mỗi mảnh gói UDP để tránh IP fragmentation

def main():
    if len(sys.argv) < 2:
        print("Cú pháp: python Server.py <file MJPEG>")
        sys.exit(1)

    video_file = sys.argv[1]
    
    try:
        video_stream = VideoStream(video_file)
    except IOError as e:
        print(f"Lỗi: {e}")
        sys.exit(1)

    # Khởi tạo Socket UDP
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    
    # Cấu hình IP_MULTICAST_TTL. TTL = 1 nghĩa là gói tin chỉ đi trong mạng nội bộ local (subnet).
    ttl = 1
    server_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

    print(f"Server đang phát video livestream tới multicast group {MULTICAST_GRP}:{MULTICAST_PORT}...")
    print("Nhấn Ctrl+C để tắt Server.")

    global_seq = 0

    try:
        while True:
            # Lấy frame ảnh tiếp theo từ VideoStream (tự động lặp lại khi kết thúc)
            frame_data = video_stream.nextFrame()
            if not frame_data:
                # Tránh lặp vô hạn gây nghẽn CPU khi file bị lỗi đọc hoàn toàn
                time.sleep(0.5)
                continue

            frame_id = video_stream.frameNbr()
            total_size = len(frame_data)
            
            # Chia nhỏ frame JPEG thành các mảnh (fragments)
            fragments = []
            offset = 0
            while offset < total_size:
                chunk = frame_data[offset : offset + MAX_PAYLOAD_SIZE]
                fragments.append(chunk)
                offset += MAX_PAYLOAD_SIZE

            total_frags = len(fragments)

            # Gửi tuần tự tất cả các mảnh của frame hiện tại
            for frag_index, payload in enumerate(fragments):
                packet = Packet()
                packet_bytes = packet.encode(
                    global_seq=global_seq,
                    frame_id=frame_id,
                    frag_index=frag_index,
                    total_frags=total_frags,
                    payload=payload
                )
                
                # Gửi gói tin nhị phân tới Multicast IP Group
                server_socket.sendto(packet_bytes, (MULTICAST_GRP, MULTICAST_PORT))
                global_seq += 1

            # Sleep 50 ms để duy trì tốc độ phát sóng xấp xỉ 20 FPS
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nĐang tắt Server...")
    finally:
        video_stream.close()
        server_socket.close()
        print("Server đã đóng socket thành công.")

if __name__ == '__main__':
    main()
