"""
@file Server.py
@description RTSP Server sử dụng I/O Multiplexing (selectors) thay vì threading
             để xử lý đồng thời nhiều client trên một luồng duy nhất.
"""

import sys, socket, selectors
from ServerWorker import ServerWorker


class Server:

    def main(self):
        try:
            SERVER_PORT = int(sys.argv[1])
        except Exception:
            print("[Usage: Server.py Server_port]\n")
            return

        sel = selectors.DefaultSelector()

        rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rtspSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        rtspSocket.bind(('', SERVER_PORT))
        rtspSocket.listen(5)
        rtspSocket.setblocking(False)

        # Đăng ký socket lắng nghe — data=None đánh dấu đây là socket accept
        sel.register(rtspSocket, selectors.EVENT_READ, data=None)
        print(f'[Server] Listening on port {SERVER_PORT} - I/O Multiplexing mode')

        while True:
            events = sel.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    # Kết nối mới từ client
                    conn, addr = rtspSocket.accept()
                    conn.setblocking(False)
                    clientInfo = {'rtspSocket': (conn, addr)}
                    worker = ServerWorker(clientInfo)
                    sel.register(conn, selectors.EVENT_READ, data=worker)
                    print(f'[Server] Client connected: {addr}')
                else:
                    # Dữ liệu RTSP từ client đã kết nối
                    worker = key.data
                    conn = key.fileobj
                    try:
                        data = conn.recv(256)
                        if data:
                            print('Data received:\n' + data.decode('utf-8'))
                            worker.processRtspRequest(data.decode('utf-8'))
                        else:
                            # Client ngắt kết nối
                            print(f'[Server] Client disconnected')
                            sel.unregister(conn)
                            conn.close()
                    except Exception as e:
                        print(f'[Server] Read error: {e}')
                        sel.unregister(conn)
                        conn.close()


if __name__ == "__main__":
    (Server()).main()
