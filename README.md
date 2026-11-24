# LAN Chat & File Sharing (P2P Socket Programming)

Ứng dụng nhắn tin và truyền tệp tin ngang hàng (Peer-to-Peer) trên giao diện dòng lệnh (CLI) trong mạng LAN/Wi-Fi, kết hợp **UDP Broadcast** (khám phá nút mạng & trạng thái) và **TCP Stream** (trò chuyện đa phiên & truyền tệp tin tin cậy).

## 1. Kiến trúc & Tính năng chính
- **Tự động khám phá Peer (UDP Port 9999):** Phát gói tin quảng bá `HI|<name>|<port>|<status>` định kỳ mỗi 3 giây và tự động loại bỏ các nút mất tín hiệu quá 10 giây.
- **Trò chuyện TCP đa luồng (Multi-peer Chat):** Thiết lập kết nối trực tiếp qua TCP với giao thức phân khung `MSG|<byte_length>|<utf8_payload>`, hỗ trợ nhắn tin tiếng Việt có dấu và đếm tin nhắn chưa đọc (`unread`) khi đang chat với người khác.
- **Truyền tệp tin bất đồng bộ (Concurrent File Transfer):** Chia nhỏ tệp theo khối `64 KB` (`FSTART` / chunk / `FEND` / `FABORT`), giới hạn tối đa 4 luồng gửi song song qua `BoundedSemaphore(4)`, bảo vệ luồng ghi socket bằng `threading.Lock` và lưu tệp tạm `.part` trong thư mục `downloads/`.
- **Giao diện CLI không đè dòng (Non-blocking UI):** Sử dụng `prompt_toolkit` với `patch_stdout()` giúp tin nhắn đến hiển thị ngay lập tức phía trên mà không làm mất nội dung người dùng đang gõ.

## 2. Cấu trúc thư mục
```text
Computer-Network/
├── main.py              # Điểm khởi chạy ứng dụng, vòng lặp CLI & điều phối phiên
├── p2p_radar.py         # Phân hệ UDP Broadcast: broadcaster, listener, timeout_checker
├── p2p_tcp.py           # Phân hệ TCP: acceptor, receiver, framing, gửi/nhận file đa luồng
├── downloads/           # Thư mục mặc định lưu các tệp tin nhận được
├── requirements.txt     # Thư viện phụ thuộc (prompt_toolkit)
└── README.md            # Tài liệu hướng dẫn cài đặt, chạy và kiểm thử