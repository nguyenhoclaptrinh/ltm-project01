import socket
import struct
import sys
from Packet import Packet

# Cấu hình encoding UTF-8 để hỗ trợ in tiếng Việt trên console Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass


MULTICAST_GRP = '239.1.1.1'
MULTICAST_PORT = 5004

def run_test_receiver(loss_sim_rate=0.0):
    print("[TEST] Bắt đầu khởi tạo test receiver...")
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_socket.bind(('0.0.0.0', MULTICAST_PORT))
    
    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GRP), socket.INADDR_ANY)
    client_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    print(f"[TEST] Đã join multicast group {MULTICAST_GRP}:{MULTICAST_PORT}")

    client_socket.settimeout(5.0)
    packets_received = 0
    max_global_seq = -1
    packets_lost = 0
    packets_expected = 0
    
    print("[TEST] Chờ nhận dữ liệu multicast từ Server (Timeout 5s)...")
    try:
        for _ in range(30): # Nhận 30 gói tin để xác minh
            data, addr = client_socket.recvfrom(2048)
            
            # Giả lập mất gói ngẫu nhiên tại receiver
            if loss_sim_rate > 0.0:
                import random
                if random.random() * 100 < loss_sim_rate:
                    # Đánh dấu mất gói nhưng không xử lý tiếp để test thuật toán Loss Rate
                    continue
                
            packet = Packet()
            packet.decode(data)

            
            packets_received += 1
            seq = packet.global_seq
            
            if max_global_seq == -1:
                max_global_seq = seq
                packets_expected = 1
            else:
                if seq > max_global_seq:
                    diff = seq - max_global_seq
                    if diff > 1:
                        packets_lost += (diff - 1)
                    packets_expected += diff
                    max_global_seq = seq
            
            loss_rate = (packets_lost / packets_expected) * 100 if packets_expected > 0 else 0.0
            print(f"[TEST RECV] Nhận gói thành công: GlobalSeq={seq}, FrameID={packet.frame_id}, Mảnh={packet.frag_index}/{packet.total_frags}, Payload={packet.data_len} bytes, LossRate={loss_rate:.2f}%")
            
    except socket.timeout:
        print("[TEST] Hết thời gian chờ nhận gói tin (Timeout 5s).")
    except Exception as e:
        print(f"[TEST] Lỗi trong quá trình nhận: {e}")
    finally:
        try:
            client_socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
            client_socket.close()
        except Exception:
            pass
        print(f"[TEST] Đã đóng socket nhận. Kết quả -> Nhận được: {packets_received} gói, Dự kiến: {packets_expected} gói, Mất: {packets_lost} gói.")

if __name__ == '__main__':
    loss_rate = 0.0
    import sys
    if len(sys.argv) > 1:
        try:
            loss_rate = float(sys.argv[1])
            print(f"[TEST] Chạy với giả lập mất gói: {loss_rate}%")
        except ValueError:
            pass
    run_test_receiver(loss_sim_rate=loss_rate)
