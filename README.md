<div align="center">

# 🌐 LAN Chat & File Sharing (P2P Socket Programming)

**Ứng dụng nhắn tin và truyền tệp tin ngang hàng (Peer-to-Peer) đa luồng trong mạng LAN qua giao diện dòng lệnh (CLI)**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Protocol](https://img.shields.io/badge/Transport-UDP%20Broadcast%20%2B%20TCP%20Stream-00A86B?style=for-the-badge)]()
[![Architecture](https://img.shields.io/badge/Architecture-Pure%20P2P%20(Zero%20Server)-FF6B35?style=for-the-badge)]()
[![Course](https://img.shields.io/badge/HCMUS-M%E1%BA%A1ng%20M%C3%A1y%20T%C3%ADnh-1E3A8A?style=for-the-badge)]()

*Đồ án 1 — Khoa Công nghệ Thông tin, Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM*

</div>

---

## 👥 Thành viên thực hiện

| STT | Họ và Tên | MSSV | Vai trò & Phân công chính |
| :-: | :--- | :---: | :--- |
| 1 | **Huỳnh Hoàng Nguyên** | `25120213` | Thiết kế & xây dựng phân hệ dò tìm ngang hàng **UDP Radar** (`broadcaster`, `listener`, `timeout_checker`). |
| 2 | **Dương Hồng Đức** | `25120177` | Thiết kế giao thức phân khung **TCP**, truyền tệp tin bất đồng bộ đa luồng (`64 KB` chunking, dọn dẹp tệp lỗi). |
| 3 | **Nguyễn Gia Huy** | `25120192` | Xây dựng giao diện **CLI bất đồng bộ** (`prompt_toolkit`), bộ điều phối phiên chat & kiểm thử tích hợp đa máy. |

---

## ✨ Điểm nổi bật về kỹ thuật

Hệ thống vận hành theo kiến trúc **Peer-to-Peer thuần túy (Decentralized P2P)** — mỗi nút mạng vừa đóng vai trò **Client**, vừa đóng vai trò **Server**, tự động khám phá lẫn nhau trong cùng mạng LAN/Wi-Fi mà không cần cấu hình địa chỉ IP thủ công:

* 📡 **UDP Radar tự động khám phá nút mạng (Port `9999`):** Phát quảng bá (`255.255.255.255`) gói tin `HI|<name>|<port>|<status>` mỗi **3 giây** và tự động loại bỏ các nút ngắt kết nối đột ngột sau **10 giây** im lặng. Khi thoát chủ động (`/quit`), hệ thống gửi liên tiếp 2 gói `LEAVE` cách nhau `0.05s` để các máy khác cập nhật ngay lập tức.
* 📦 **Phân khung dữ liệu chống dính gói TCP (Custom Framing):** Giải quyết bài toán *TCP Byte-Stream* bằng cách đóng gói độ dài thực tế (`MSG|<byte_len>|<utf8_payload>`) kết hợp cơ chế đọc chính xác từng byte (`recv_exact`), hỗ trợ đầy đủ tiếng Việt có dấu (UTF-8).
* 🚀 **Ghép kênh truyền tệp tin đa luồng (`64 KB` Chunking):** Truyền tệp song song trên cùng kết nối TCP qua bộ khung `FSTART` → `FDATA` → `FEND` / `FABORT`. Giới hạn tối đa **4 luồng gửi đồng thời** (`BoundedSemaphore(4)`) và khóa ghi độc lập trên từng socket giúp **nhắn tin hai chiều không bị nghẽn** ngay cả khi đang truyền tệp nặng `50 MB`.
* 🛡️ **Bảo toàn dữ liệu & chống ghi đè:** Tệp nhận được lưu tự động vào thư mục `download/` (tự đánh số thứ tự nếu trùng tên). Hệ thống kiểm tra tổng số byte thực nhận và tự động xóa sạch tệp đang tải dở nếu đứt kết nối giữa chừng hoặc nhận tín hiệu hủy `FABORT`.
* ⌨️ **Giao diện CLI bất đồng bộ không vỡ dòng:** Tích hợp `prompt_toolkit` (`patch_stdout`) giúp thông báo và tin nhắn mới hiển thị gọn phía trên mà không làm mất nội dung người dùng đang gõ dở.

---

## 🏗️ Kiến trúc hệ thống

```text
+----------------------------------------------------------------------------------------------+
|                                    MỘT NÚT MẠNG (PEER)                                       |
|                                                                                              |
|  [Main CLI Thread]  <--->  prompt_toolkit (patch_stdout)  <--->  Màn hình Console            |
|         |                                                                                    |
|         +---> [UDP Broadcaster]  ---(Mỗi 3s: HI|Name|Port|Status)---> 255.255.255.255:9999   |
|         +---> [UDP Listener]     <--(Nhận HI / LEAVE từ LAN)--------- 0.0.0.0:9999           |
|         +---> [Timeout Checker]  ---(Quét mỗi 3s: Xóa peer > 10s)---> online_peers           |
|         |                                                                                    |
|         +---> [TCP Acceptor]     <--(Lắng nghe kết nối mới)---------- 0.0.0.0:<Random_Port>  |
|         +---> [TCP Receiver x N] <--(recv_exact: MSG, FSTART, FDATA, FEND, BYE)              |
|         +---> [File Sender x 4]  ---(BoundedSemaphore(4) + Send Lock)----------->            |
+----------------------------------------------------------------------------------------------+
```

---

## 🛠️ 1. Hướng dẫn Cài đặt

### Yêu cầu môi trường
* **Python:** `3.10` trở lên (khuyến nghị `Python 3.12`).
* **Hệ điều hành:** Windows 10/11, Linux (Ubuntu/Debian), hoặc macOS.

### Các bước cài đặt
```bash
# 1. Clone mã nguồn từ GitHub
git clone [https://github.com/DuongHongDuc-az/Computer-Network.git](https://github.com/DuongHongDuc-az/Computer-Network.git)
cd Computer-Network

# 2. Tạo và kích hoạt môi trường ảo (Khuyến nghị)
python -m venv .venv
# - Windows (PowerShell / CMD):
.venv\Scripts\activate
# - Linux / macOS:
source .venv/bin/activate

# 3. Cài đặt thư viện giao diện CLI
pip install prompt_toolkit colorama
```

### Lưu ý mạng & Tường lửa khi chạy nhiều máy
* **Mở cổng UDP `9999`:** Trên Windows, chọn **Allow access** cho cả *Private* và *Public networks* khi hộp thoại Firewall hiện lên (hoặc chạy `sudo ufw allow 9999/udp` trên Ubuntu).
* **Mạng Wi-Fi công cộng:** Nhiều bộ phát Wi-Fi trường học/quán cà phê bật *AP Isolation* chặn gói tin Broadcast giữa các máy. Khi demo trên lớp, nên dùng **1 điện thoại phát Wi-Fi Hotspot** cho các laptop cùng kết nối.

---

## 🚀 2. Hướng dẫn Chạy chương trình

### Kịch bản A: Chạy thử nhiều tài khoản trên cùng 1 máy
Nhờ tùy chọn `SO_REUSEADDR` trên cổng UDP `9999` và cấp phát cổng TCP động (`bind(('', 0))`), bạn có thể mở nhiều cửa sổ Terminal trên cùng 1 máy để chạy độc lập:
```bash
# Terminal 1 -> nhập tên: Duc
# Terminal 2 -> nhập tên: Nguyen
# Terminal 3 -> nhập tên: Huy
python main.py
```

### Kịch bản B: Chạy mạng ngang hàng trên nhiều máy tính (LAN / Wi-Fi)
1. Kết nối các máy vào cùng một mạng Wi-Fi / LAN và chạy `python main.py` trên từng máy.
2. Chờ khoảng `3.5` giây quét mạng ban đầu, sau đó nhập tên định danh (tên **không được rỗng**, **không chứa khoảng trắng**, **không chứa ký tự `|`** và không trùng với người đang trực tuyến).
3. Gõ `/list` để xem danh sách các máy đã tự động kết nối.

### Bảng tra cứu lệnh điều khiển (CLI Commands)

| Cú pháp lệnh | Ví dụ | Mô tả chức năng |
| :--- | :--- | :--- |
| `/list` | `/list` | Xem danh sách tên và trạng thái các người dùng đang trực tuyến. |
| `/chat <name>` | `/chat Nguyen` | Mở kết nối TCP và bước vào phòng chat trực tiếp với `<name>`. |
| `<text>` | `Hello Nguyen!` | Gửi tin nhắn trực tiếp tới người đang mở khung chat hiện tại. |
| `/msg <name> <text>` | `/msg Huy Hop nhom nhe` | Gửi nhanh tin nhắn cho `<name>` mà không cần đổi khung chat hiện tại. |
| `/file <name> <path>` *(hoặc `/sendfile`)* | `/file Nguyen report.pdf` | Gửi tệp tin tới đối tác (tối đa `50 MB`, chạy ngầm tối đa 4 tệp cùng lúc). |
| `/status <status_name>` | `/status away` | Đổi trạng thái cá nhân (`online`, `busy`, `away`) cập nhật qua UDP. |
| `/back` | `/back` | Rời khung chat hiện tại về sảnh chính (vẫn giữ kết nối TCP ngầm). |
| `/bye [name]` | `/bye` | Gửi gói `BYE` và đóng hẳn kết nối TCP với đối tác hiện tại (hoặc `<name>`). |
| `/conns` | `/conns` | Xem danh sách các đối tác đang duy trì kết nối TCP. |
| `/help` | `/help` | Hiển thị tóm tắt danh sách các lệnh hỗ trợ. |
| `/quit` | `/quit` | Hủy các tệp đang gửi, gửi `BYE` tới tất cả, phát gói `LEAVE` và thoát an toàn. |

### Minh họa phiên làm việc thực tế

```text
$ python main.py
==================================================
         P2P CHAT & FILE TRANSFER SYSTEM
==================================================
[*] Connecting to local network...
Enter your name: Duc

[*] Starting Radar for [Duc]...
Supported commands: /chat <name>, /back, /list, /msg <name> <text>, /status <status_name>
                    /file <name> <path>, /bye <name>, /conns, /quit
--------------------------------------------------
> /list
------ ONLINE PEERS LIST (3 peers) ------
- Duc                  | Status: [online]
- Nguyen               | Status: [online]
- Huy                  | Status: [away]
-----------------------------------------
> /chat Nguyen
[*] Connected to Nguyen.
> Hi Nguyen, I'm sending the draft report!
[Me] Hi Nguyen, I'm sending the draft report!
[Nguyen] Sure, send it over!
[*] New message from Huy (1 unread)
> /file Nguyen report_v1.pdf
Starting report_v1.pdf (12582912 bytes) in background
Sending report_v1.pdf -> Nguyen: 25%
Sending report_v1.pdf -> Nguyen: 50%
Sending report_v1.pdf -> Nguyen: 75%
Sending report_v1.pdf -> Nguyen: 100%
Send report_v1.pdf (12582912 bytes) to Nguyen
```

---

## 🧪 3. Tóm tắt Kịch bản Kiểm thử

| Bài kiểm thử | Thao tác thực hiện | Kết quả đạt được |
| :--- | :--- | :--- |
| **1. UDP Discovery & Timeout** | Đổi trạng thái `/status busy`; thoát bằng `/quit` và thử tắt nóng cửa sổ Terminal. | Trạng thái cập nhật trong `≤ 3s`; `/quit` xóa peer ngay lập tức qua gói `LEAVE`; tắt nóng tự động xóa sau `10–13s`. |
| **2. TCP Framing & Unread** | Gửi chuỗi tiếng Việt có dấu kèm ký tự đặc biệt; nhận tin từ nhiều người cùng lúc. | Hiển thị chính xác 100% byte UTF-8; tin từ người khác lưu vào hàng đợi `(N unread)` và xả đủ khi `/chat`. |
| **3. Chống đè dòng nhập liệu** | Gõ dở câu dài (chưa nhấn Enter) trong lúc đối phương gửi liên tiếp nhiều tin nhắn. | Tin nhắn mới chèn gọn phía trên, dòng đang gõ dở được giữ nguyên vẹn ký tự và vị trí con trỏ. |
| **4. Truyền tệp lớn & SHA-256** | Gửi tệp `30 MB` song song với nhắn tin; gửi lặp lại 2 lần và đối chiếu mã băm SHA-256. | Chat không bị nghẽn; tệp trùng tự đổi tên thành `file (1).ext`; mã SHA-256 gốc và nhận trùng khớp 100%. |
| **5. Xử lý sự cố (`FABORT`)** | Gửi tệp `> 50 MB`; nhấn `Ctrl + C` ngắt ngang khi đang truyền tệp `30 MB`. | Từ chối tệp vượt giới hạn; bên nhận tự động đóng và xóa sạch tệp đang tải dở trong `download/`. |
| **6. Kiểm chứng Wireshark** | Bắt gói tin với bộ lọc `udp.port == 9999` và theo dõi luồng `tcp.stream`. | Quan sát rõ gói `HI\|...` phát mỗi `3s`, quá trình bắt tay 3 bước TCP (`SYN`, `SYN-ACK`, `ACK`) và khung dữ liệu. |

---

## ❓ Xử lý sự cố thường gặp (Troubleshooting)

| Hiện tượng | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| Nhập tên báo lỗi không hợp lệ | Tên rỗng, chứa khoảng trắng hoặc ký tự dấu gạch đứng `\|` | Khoảng trắng dùng để tách tham số lệnh CLI và `\|` là dấu phân tách khung giao thức; chọn tên viết liền không chứa các ký tự này. |
| Nhập tên báo `Name '...' is already taken` | Trong mạng LAN đang có người dùng khác sử dụng tên này | Chọn một tên hiển thị khác không trùng với danh sách vừa đồng bộ lúc khởi động. |
| Hai máy cùng Wi-Fi nhưng `/list` không thấy nhau | Firewall chặn gói UDP `9999` hoặc Wi-Fi bật *AP Isolation* | Cho phép `python.exe` qua Firewall hoặc dùng điểm phát sóng di động (Mobile Hotspot) làm mạng LAN chung. |
| Lỗi `ModuleNotFoundError` (`prompt_toolkit` / `colorama`) | Chưa cài đủ thư viện hoặc chưa kích hoạt đúng `.venv` | Kích hoạt môi trường ảo và chạy lại `pip install prompt_toolkit colorama`. |
| Lỗi gửi tệp báo `File too large` | Tệp tin vượt quá giới hạn `50 MB` (`MAX_FILE_SIZE`) | Chỉ gửi các tệp có dung lượng tối đa `50 MB` hoặc nén nhỏ tệp trước khi gửi. |