import sys
import time
import socket
import struct
import threading
import queue
import cv2
import numpy as np
from Packet import Packet

# Cấu hình encoding UTF-8 để hỗ trợ in tiếng Việt trên console Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass


MULTICAST_GRP = '239.1.1.1'
MULTICAST_PORT = 5004

class MulticastClient:
    def __init__(self, loss_sim_rate=0.0):
        self.frame_queue = queue.Queue(maxsize=30)
        self.running = True
        self.loss_sim_rate = loss_sim_rate
        
        # Biến thống kê gói tin (Packet Loss)
        self.max_global_seq = -1
        self.packets_lost = 0
        self.packets_expected = 0
        self.packet_loss_rate = 0.0
        
        # Biến thống kê khung hình (Frame Loss)
        self.current_frame_id = -1
        self.fragments_received = {}
        self.total_expected_fragments = 0
        self.min_frame_id = -1
        self.total_lost_frames = 0
        self.total_expected_frames = 0
        self.frame_loss_rate = 0.0
        
        # Cấu hình Socket
        self.client_socket = None
        self.setup_socket()

    def setup_socket(self):
        """Khởi tạo socket UDP và join vào multicast group."""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            # Cho phép nhiều tiến trình bind cùng port
            self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind vào tất cả các interface mạng tại port multicast
            self.client_socket.bind(('0.0.0.0', MULTICAST_PORT))
            
            # Đăng ký Join Multicast Group
            mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GRP), socket.INADDR_ANY)
            self.client_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            print(f"Đã join thành công multicast group {MULTICAST_GRP}:{MULTICAST_PORT}")
        except Exception as e:
            print(f"Lỗi khởi tạo socket client: {e}")
            sys.exit(1)

    def receive_packets(self):
        """Thread liên tục nhận các gói tin nhị phân và lắp ráp frame."""
        print("Luồng nhận dữ liệu bắt đầu hoạt động...")
        import random
        while self.running:
            try:
                # Đặt timeout để luồng có thể thoát khi self.running = False
                self.client_socket.settimeout(1.0)
                data, addr = self.client_socket.recvfrom(2048) # Buffer size đủ lớn cho Header (12) + Payload (1400)
                
                # Giả lập mất gói tin ngẫu nhiên trên mạng
                if self.loss_sim_rate > 0.0 and random.random() * 100 < self.loss_sim_rate:
                    continue
                
                packet = Packet()
                packet.decode(data)
                
                # 1. Thống kê Packet Loss (Tỉ lệ mất gói tin)
                seq = packet.global_seq
                if self.max_global_seq == -1:
                    self.max_global_seq = seq
                    self.packets_expected = 1
                else:
                    if seq > self.max_global_seq:
                        diff = seq - self.max_global_seq
                        if diff > 1:
                            self.packets_lost += (diff - 1)
                        self.packets_expected += diff
                        self.max_global_seq = seq
                    
                    # Tính toán lại tỉ lệ mất gói
                    if self.packets_expected > 0:
                        self.packet_loss_rate = (self.packets_lost / self.packets_expected) * 100.0

                # 2. Xử lý lắp ráp (Reassembly) & Thống kê Frame Loss
                fid = packet.frame_id
                
                if self.min_frame_id == -1:
                    self.min_frame_id = fid

                if fid < self.current_frame_id:
                    # Gói tin của frame cũ, bỏ qua
                    continue
                elif fid > self.current_frame_id:
                    # Chuyển sang nhận frame mới
                    # Kiểm tra xem frame cũ đã nhận đủ mảnh chưa
                    if self.current_frame_id != -1:
                        if len(self.fragments_received) < self.total_expected_fragments:
                            self.total_lost_frames += 1
                    
                    # Cập nhật thông tin frame mới
                    self.current_frame_id = fid
                    self.fragments_received = {packet.frag_index: packet.payload}
                    self.total_expected_fragments = packet.total_frags
                    
                    # Cập nhật tổng số frame dự kiến nhận được từ đầu đến giờ
                    self.total_expected_frames = self.current_frame_id - self.min_frame_id + 1
                else:
                    # Thuộc frame hiện tại đang lắp ráp
                    self.fragments_received[packet.frag_index] = packet.payload

                # Tính toán tỉ lệ mất frame
                if self.total_expected_frames > 0:
                    self.frame_loss_rate = (self.total_lost_frames / self.total_expected_frames) * 100.0

                # Kiểm tra xem đã nhận đủ tất cả các mảnh của frame chưa
                if len(self.fragments_received) == self.total_expected_fragments:
                    # Lắp ráp hoàn chỉnh các mảnh theo thứ tự tăng dần
                    try:
                        assembled_image = b''.join([self.fragments_received[i] for i in range(self.total_expected_fragments)])
                        # Đẩy vào queue hiển thị, nếu queue đầy thì giải phóng gói cũ nhất
                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        self.frame_queue.put(assembled_image)
                    except KeyError:
                        # Trường hợp bị thiếu index nào đó (mặc dù hiếm khi xảy ra do độ dài dict đã bằng)
                        pass
                    
                    # Xóa bộ đệm frame hiện tại để tránh lắp ráp lại
                    self.fragments_received.clear()

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Lỗi khi nhận gói tin: {e}")
                break

    def run(self):
        """Khởi chạy ứng dụng, hiển thị video trên luồng chính."""
        # Chạy Receiver Thread
        receiver_thread = threading.Thread(target=self.receive_packets, daemon=True)
        receiver_thread.start()

        print("Đang khởi động cửa sổ hiển thị video...")
        print("Mẹo: Nhấp vào màn hình video và nhấn 'q' để THOÁT.")

        fps_count = 0
        fps_start_time = time.time()
        display_fps = 0.0

        cv2.namedWindow("Multicast Video Stream", cv2.WINDOW_NORMAL)

        while self.running:
            try:
                # Đọc frame từ Queue
                try:
                    frame_bytes = self.frame_queue.get(timeout=0.1)
                except queue.Empty:
                    # Không có frame mới, tiếp tục loop để kiểm tra phím bấm
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        self.running = False
                    continue

                # Giải mã dữ liệu JPEG thành ảnh
                nparr = np.frombuffer(frame_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if img is not None:
                    # Tính FPS hiển thị thực tế
                    fps_count += 1
                    elapsed = time.time() - fps_start_time
                    if elapsed >= 1.0:
                        display_fps = fps_count / elapsed
                        fps_count = 0
                        fps_start_time = time.time()

                    # Vẽ trực tiếp các thông số lên khung hình
                    h, w, _ = img.shape
                    
                    # Tạo thanh trạng thái màu đen ở góc trên để hiển thị text rõ nét
                    overlay = img.copy()
                    cv2.rectangle(overlay, (0, 0), (w, 90), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

                    # Viết chữ các chỉ số lên ảnh
                    text_color = (0, 255, 0) # Màu xanh lá
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    cv2.putText(img, f"Group: {MULTICAST_GRP}:{MULTICAST_PORT}", (15, 25), font, 0.6, text_color, 1, cv2.LINE_AA)
                    cv2.putText(img, f"Render FPS: {display_fps:.1f}", (15, 50), font, 0.6, text_color, 1, cv2.LINE_AA)
                    cv2.putText(img, f"Packet Loss: {self.packet_loss_rate:.2f}% (Lost: {self.packets_lost}/{self.packets_expected})", (15, 75), font, 0.6, text_color, 1, cv2.LINE_AA)
                    cv2.putText(img, f"Frame Loss: {self.frame_loss_rate:.2f}% (Lost: {self.total_lost_frames}/{self.total_expected_frames})", (w - 300, 25), font, 0.6, (0, 0, 255) if self.frame_loss_rate > 0 else text_color, 1, cv2.LINE_AA)

                    # Hiển thị frame
                    cv2.imshow("Multicast Video Stream", img)

                # Kiểm tra phím thoát 'q' hoặc khi tắt cửa sổ
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.running = False

                # Kiểm tra xem cửa sổ OpenCV có bị đóng thủ công không
                if cv2.getWindowProperty("Multicast Video Stream", cv2.WND_PROP_VISIBLE) < 1:
                    self.running = False

            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"Lỗi hiển thị: {e}")
                self.running = False

        # Dọn dẹp tài nguyên
        self.cleanup()

    def cleanup(self):
        """Hủy join multicast, đóng socket và hủy cửa sổ OpenCV."""
        print("\nĐang dọn dẹp tài nguyên và rời khỏi multicast group...")
        self.running = False
        
        # Rời Multicast Group
        if self.client_socket:
            try:
                mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GRP), socket.INADDR_ANY)
                self.client_socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
                self.client_socket.close()
                print("Đã rời multicast group và đóng socket.")
            except Exception as e:
                print(f"Lỗi khi đóng socket: {e}")
        
        cv2.destroyAllWindows()
        print("Đã đóng toàn bộ cửa sổ hiển thị. Tạm biệt Đại ca!")

if __name__ == '__main__':
    loss_rate = 0.0
    if len(sys.argv) > 1:
        try:
            loss_rate = float(sys.argv[1])
            print(f"Khởi động Client với chế độ giả lập mất gói: {loss_rate}%")
        except ValueError:
            print("Tham số tỉ lệ mất gói không hợp lệ. Sử dụng mặc định: 0%")
            
    client = MulticastClient(loss_sim_rate=loss_rate)
    client.run()
