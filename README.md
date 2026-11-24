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

## ✨ Điểm nổi bật về kỹ thuật

Khác với các ứng dụng chat Client–Server truyền thống, hệ thống này vận hành theo kiến trúc **Peer-to-Peer thuần túy (Decentralized P2P)** — mỗi máy trạm vừa là **Client**, vừa là **Server**, tự động tìm thấy nhau ngay khi cắm cáp mạng hoặc kết nối chung Wi-Fi mà không cần cấu hình địa chỉ IP thủ công:

* 📡 **UDP Radar tự động khám phá nút mạng (Port `9999`):** Phát quảng bá (`255.255.255.255`) gói tin `HI|<name>|<port>|<status>` mỗi **3 giây** và tự động dọn dẹp các nút "bốc hơi" (rớt mạng, tắt nóng) sau **10 giây** im lặng. Khi thoát chủ động (`/quit`), hệ thống bắn liên tiếp 2 gói `LEAVE` cách nhau `0.05s` để giảm thiểu rủi ro thất lạc gói tin UDP.
* 📦 **Phân khung dữ liệu chống dính gói TCP (Custom Framing):** Giải quyết triệt để bài toán *TCP Byte-Stream* bằng cơ chế đóng gói độ dài thực tế (`MSG|<byte_len>|<utf8_payload>`) kết hợp hàm đọc chính xác `recv_exact()`, hỗ trợ mượt mà tiếng Việt có dấu (multi-byte UTF-8).
* 🚀 **Ghép kênh truyền tệp tin đa luồng (`64 KB` Chunking):** Truyền tệp song song ngay trên kết nối TCP hiện có qua bộ khung `FSTART` → `FCHUNK` → `FEND` / `FABORT`. Giới hạn tối đa **4 luồng gửi đồng thời** (`BoundedSemaphore(4)`), bảo vệ luồng ghi socket bằng khóa riêng từng kết nối (`_send_locks`) giúp **nhắn tin hai chiều hoàn toàn không bị nghẽn** ngay cả khi đang gửi tệp nặng `50 MB`.
* 🛡️ **Bảo toàn dữ liệu với tệp tạm `.part`:** Dữ liệu nhận được ghi trực tiếp vào `downloads/<file>.part` và chỉ đổi tên sang tệp gốc khi khớp đủ `100%` số byte khai báo. Tự động xóa tệp lỗi nếu đứt kết nối giữa chừng hoặc nhận tín hiệu `FABORT`.
* ⌨️ **Giao diện CLI bất đồng bộ không vỡ dòng:** Tích hợp `prompt_toolkit` (`patch_stdout()`) giúp tin nhắn mới từ đồng đội hiển thị gọn gàng phía trên mà không cắt ngang hay làm mất nội dung bạn đang gõ dở.

---

## 🏗️ Kiến trúc hệ thống & Giao thức

```text
+-----------------------------------------------------------------------------------+
|                                MỘT NÚT MẠNG (PEER)                                |
|                                                                                   |
|  [Main CLI Thread]  <--->  prompt_toolkit (patch_stdout)  <--->  Màn hình Console |
|         |                                                                         |
|         +---> [UDP Broadcaster]  ---(Mỗi 3s: HI|Name|Port|Status)---> 255.255.255.255:9999
|         +---> [UDP Listener]     <--(Nhận HI / LEAVE từ LAN)--------- 0.0.0.0:9999
|         +---> [Timeout Checker]  ---(Quét mỗi 3s: Xóa peer > 10s)---> online_peers
|         |                                                                         |
|         +---> [TCP Acceptor]     <--(Lắng nghe kết nối mới)---------- 0.0.0.0:<Random_Port>
|         +---> [TCP Receiver x N] <--(recv_exact: MSG, FSTART, FCHUNK, FEND, BYE)  |
|         +---> [File Sender x 4]  ---(BoundedSemaphore(4) + _send_locks)---------> |
+-----------------------------------------------------------------------------------+
```

---

## 🛠️ 1. Hướng dẫn Cài đặt (Install)

### Yêu cầu môi trường
* **Python:** Phiên bản `3.10` trở lên (khuyến nghị `Python 3.12`).
* **Hệ điều hành:** Windows 10/11, Linux (Ubuntu/Debian), hoặc macOS.
* **Mạng:** Các máy tính tham gia kết nối cùng một mạng LAN / Wi-Fi (hoặc chạy nhiều cửa sổ Terminal trên cùng 1 máy).

### Các bước cài đặt chi tiết

**Bước 1: Clone mã nguồn từ GitHub**
```bash
git clone https://github.com/DuongHongDuc-az/Computer-Network.git
cd Computer-Network
```

**Bước 2: Tạo môi trường ảo (Khuyến nghị) & Cài đặt thư viện**
```bash
# Tạo virtual environment
python -m venv .venv

# Kích hoạt môi trường ảo:
# - Trên Windows (PowerShell / CMD):
.venv\Scripts\activate
# - Trên Linux / macOS:
source .venv/bin/activate

# Cài đặt thư viện giao diện CLI bất đồng bộ
pip install prompt_toolkit
```
*(Nếu đã có file `requirements.txt`, bạn chỉ cần chạy `pip install -r requirements.txt`)*

**Bước 3: Cấu hình Tường lửa (Bắt buộc khi chạy nhiều máy qua Wi-Fi/LAN)**
Hệ điều hành thường chặn các gói tin **UDP Broadcast** đến từ máy lạ. Hãy thực hiện nhanh thao tác sau:
* **Trên Windows:** Khi chạy chương trình lần đầu và thấy bảng *Windows Security Alert*, hãy tích chọn **cả 2 ô** (`Private networks` và `Public networks`) → nhấn **Allow access**.
  *(Hoặc mở PowerShell với quyền Administrator và chạy lệnh mở cổng nhanh:)*
  ```powershell
  New-NetFirewallRule -DisplayName "LAN_Chat_UDP_9999" -Direction Inbound -Protocol UDP -LocalPort 9999 -Action Allow
  ```
* **Trên Ubuntu/Linux (nếu bật UFW):**
  ```bash
  sudo ufw allow 9999/udp
  ```
* 💡 **Mẹo mạng Wi-Fi trường học/quán cà phê:** Nhiều bộ phát Wi-Fi công cộng bật tính năng *AP Isolation (Client Isolation)* chặn các thiết bị nhìn thấy nhau. Khi demo trên lớp, cách ổn định nhất là **dùng 1 điện thoại phát Wi-Fi Hotspot** cho các laptop cùng kết nối.

---

## 🚀 2. Hướng dẫn Chạy chương trình (Run)

### Kịch bản A: Chạy thử nhiều tài khoản trên cùng 1 máy (Localhost Sandbox)
Nhờ cơ chế `SO_REUSEADDR` trên cổng UDP `9999` và cấp phát cổng TCP động của hệ điều hành (`bind(('', 0))`), bạn có thể mở nhiều cửa sổ Terminal ngay trên 1 máy mà không bao giờ bị xung đột cổng:

* **Mở Terminal 1 (Đóng vai Dương Hồng Đức):**
  ```bash
  python main.py
  # Nhập tên hiển thị: Duc
  ```
* **Mở Terminal 2 (Đóng vai Huỳnh Hoàng Nguyên):**
  ```bash
  python main.py
  # Nhập tên hiển thị: Nguyen
  ```
* **Mở Terminal 3 (Đóng vai Nguyễn Gia Huy):**
  ```bash
  python main.py
  # Nhập tên hiển thị: Huy
  ```

### Kịch bản B: Chạy mạng ngang hàng trên 2+ máy tính thật (LAN / Wi-Fi)
1. Kết nối Máy A và Máy B vào cùng một mạng Wi-Fi / LAN.
2. Trên cả hai máy, mở Terminal tại thư mục dự án và chạy:
   ```bash
   python main.py
   ```
3. Nhập tên định danh cho từng máy (lưu ý: tên không được rỗng và **không chứa ký tự `|`**).
4. Chờ tối đa **3 giây**, gõ `/list` trên bất kỳ máy nào để thấy máy còn lại tự động xuất hiện cùng địa chỉ IP nội bộ.

### Bảng tra cứu lệnh điều khiển (CLI Commands)

| Cú pháp lệnh | Ví dụ sử dụng | Mô tả chức năng |
| :--- | :--- | :--- |
| `/list` | `/list` | Xem danh sách người dùng đang trực tuyến (STT, Tên, IP, Cổng TCP, Trạng thái). |
| `/chat <tên>` | `/chat Nguyen` | Mở kết nối TCP và bước vào phòng chat trực tiếp với `<tên>`. |
| `<văn bản>` | `Chào Nguyên, gửi file nhé!` | Gửi tin nhắn trực tiếp tới người đang mở khung chat hiện tại. |
| `/msg <tên> <nội dung>` | `/msg Huy Tí họp nhóm nha` | Gửi nhanh tin nhắn cho `<tên>` mà không cần chuyển khung chat hiện tại. |
| `/send <đường_dẫn>` *(hoặc `/file`)* | `/send ./bao_cao.pdf` | Gửi tệp tin tới đối tác (tối đa `50 MB`, chạy ngầm tối đa 4 tệp cùng lúc). |
| `/status <trạng_thái>` | `/status away` | Đổi trạng thái cá nhân (`online`, `away`, `busy`) cập nhật tức thì qua UDP. |
| `/back` | `/back` | Thoát khỏi khung chat hiện tại về sảnh chính (vẫn giữ kết nối TCP ngầm). |
| `/leave` *(hoặc `/bye`)* | `/leave` | Gửi gói `BYE` và ngắt hẳn kết nối TCP với đối tác hiện tại. |
| `/help` | `/help` | Hiển thị bảng hướng dẫn nhanh các lệnh ngay trong Console. |
| `/quit` | `/quit` | Hủy các tệp đang gửi, gửi `BYE` tới tất cả, phát gói `LEAVE` và thoát an toàn. |

### Minh họa phiên làm việc thực tế (Live Session)

```text
$ python main.py
Nhập tên của bạn: Duc
[*] Khởi tạo nút mạng thành công! Đang lắng nghe TCP tại cổng 54120
[*] UDP Radar đang phát quảng bá trên cổng 9999...

> /list
=== DANH SÁCH NGƯỜI DÙNG TRỰC TUYẾN (3) ===
  1. Duc      (127.0.0.1:54120)     [online] (Bạn)
  2. Nguyen   (192.168.1.15:58301)  [online]
  3. Huy      (192.168.1.22:60114)  [away]

> /chat Nguyen
[*] Đã thiết lập kết nối TCP tới Nguyen (192.168.1.15:58301)
[Duc -> Nguyen] Hi Nguyên, mình gửi bản nháp báo cáo nhé!
[Nguyen] Ok gửi qua đi, mình đang check đây
[*] Tin nhắn mới từ Huy (1 tin chưa đọc - gõ /chat Huy để xem)
[Duc -> Nguyen] /send report_v1.pdf
[*] Đang gửi tệp 'report_v1.pdf' (12.4 MB) [TID: a9f31c02]...
[Duc -> Nguyen] File hơi nặng chút, đợi tầm 2 giây nha!
[*] Tiến độ gửi 'report_v1.pdf': 25%... 50%... 75%... 100% (Hoàn tất!)
```

---

## 🧪 3. Kịch bản Kiểm thử Toàn diện (Test Suite)

Để xác minh tính ổn định của toàn bộ hệ thống trước khi nộp bài hoặc demo, hãy thực hiện lần lượt **6 bài kiểm thử (Test Cases)** dưới đây:

### Test 1: Khám phá mạng UDP, Cập nhật trạng thái & Cơ chế Timeout 10 giây
* **Mục đích:** Kiểm tra luồng `broadcaster_thread`, `listener_thread` và `timeout_checker_thread`.
* **Thao tác:**
  1. Bật Máy 1 (`Duc`) và Máy 2 (`Nguyen`). Sau 3 giây, gõ `/list` trên cả hai máy.
  2. Trên Máy 2 gõ `/status busy` → trên Máy 1 gõ `/list`.
  3. **Kiểm tra thoát chủ động:** Trên Máy 2 gõ `/quit` → kiểm tra Máy 1.
  4. **Kiểm tra rớt mạng đột ngột:** Bật lại Máy 2, sau đó bấm dấu **`X` tắt thẳng cửa sổ Terminal** (hoặc rút Wi-Fi Máy 2) để không cho phép gửi gói `LEAVE`.
* **Kết quả kỳ vọng:**
  * Trạng thái của `Nguyen` trên Máy 1 đổi từ `online` sang `busy` trong vòng tối đa 3 giây.
  * Khi gõ `/quit`, `Nguyen` biến mất khỏi danh sách của Máy 1 **ngay lập tức** (nhờ gói `LEAVE`).
  * Khi tắt nóng cửa sổ, sau đúng **10–13 giây**, luồng `timeout_checker` của Máy 1 tự động loại `Nguyen` khỏi `online_peers`.

### Test 2: Phân khung TCP, Tiếng Việt có dấu & Hàng đợi tin chưa đọc (`Unread`)
* **Mục đích:** Kiểm tra `recv_exact()` xử lý đúng độ dài byte UTF-8 và quản lý đa phiên kết nối.
* **Thao tác:**
  1. Mở 3 instance: `Duc`, `Nguyen`, `Huy`.
  2. `Duc` mở chat với `Nguyen` (`/chat Nguyen`) và gửi chuỗi tiếng Việt có dấu kèm ký tự đặc biệt: `"Tiếng Việt có dấu: ă â đ ê ô ơ ư — Giá trị 100$ | Test!"`.
  3. Trong khi `Duc` đang chat với `Nguyen`, `Huy` gõ `/chat Duc` và gửi liên tiếp 3 tin nhắn cho `Duc`.
  4. `Duc` gõ `/chat Huy`.
* **Kết quả kỳ vọng:**
  * Chuỗi tiếng Việt hiển thị nguyên vẹn trên máy `Nguyen`, không bị lỗi font hay cắt xén byte.
  * Máy `Duc` nhận thông báo có tin nhắn chưa đọc từ `Huy` mà không bị nhảy màn hình chat hiện tại; khi gõ `/chat Huy`, toàn bộ 3 tin nhắn của `Huy` được xả ra đầy đủ theo đúng thứ tự.

### Test 3: Chống đè dòng nhập liệu (Non-blocking Console UI)
* **Mục đích:** Kiểm tra `prompt_toolkit` (`patch_stdout`) chống xung đột luồng in màn hình.
* **Thao tác:**
  1. Trên Máy 2 (`Nguyen`), gõ một câu thật dài nhưng **chưa nhấn Enter**, ví dụ: `> Mình đang kiểm tra xem nếu tin nhắn đến thì dòng này có bị...`
  2. Lúc này, trên Máy 1 (`Duc`), gửi liên tiếp 3–4 tin nhắn sang cho `Nguyen`.
* **Kết quả kỳ vọng:**
  * Các tin nhắn của `Duc` tự động chèn lên phía trên lịch sử chat.
  * Dòng đang gõ dở trên màn hình của `Nguyen` **được giữ nguyên vẹn từng ký tự**, con trỏ vẫn nằm đúng cuối câu để gõ tiếp.

### Test 4: Truyền tệp tin lớn song song với Chat & Kiểm tra toàn vẹn SHA-256
* **Mục đích:** Kiểm tra ghép kênh `FSTART`/`FCHUNK`/`FEND`, khóa `_send_locks` và tính toàn vẹn dữ liệu nhị phân.
* **Thao tác:**
  1. Tạo nhanh một tệp nhị phân ngẫu nhiên dung lượng **30 MB** để test:
     * *Trên Windows (PowerShell):* `fsutil file createnew test_30mb.bin 31457280`
     * *Trên Linux/macOS:* `dd if=/dev/urandom of=test_30mb.bin bs=1M count=30`
  2. Gửi tệp bằng lệnh `/send test_30mb.bin`. Trong lúc tiến độ đang chạy (`25%... 50%... 75%`), **liên tục nhắn tin qua lại** giữa hai máy.
  3. Gửi tiếp cùng tệp đó thêm 1 lần nữa để kiểm tra cơ chế chống ghi đè `_unique_path()`.
  4. Đối chiếu mã băm SHA-256 giữa tệp gốc và tệp trong thư mục `downloads/`:
     * *Windows:* `certutil -hashfile test_30mb.bin SHA256` và `certutil -hashfile downloads\test_30mb.bin SHA256`
     * *Linux/macOS:* `sha256sum test_30mb.bin downloads/test_30mb.bin`
* **Kết quả kỳ vọng:**
  * Tin nhắn vẫn gửi/nhận tức thì trong lúc truyền tệp, không bị kẹt hay dính ký tự nhị phân vào tin nhắn.
  * Lần gửi thứ 2 tự động lưu thành `test_30mb (1).bin` trong `downloads/`.
  * Hai chuỗi mã băm **SHA-256 trùng khớp 100%**.

### Test 5: Xử lý sự cố & Dọn dẹp tệp dở dang (`Fault Tolerance`)
* **Mục đích:** Kiểm tra `FABORT`, cơ chế tự xóa tệp `.part` và giới hạn an toàn (`50 MB`).
* **Thao tác:**
  1. Thử gửi một tệp có dung lượng **> 50 MB** (ví dụ `60 MB`) → Hệ thống từ chối và báo lỗi rõ ràng, không làm sập chương trình.
  2. Bắt đầu gửi tệp `30 MB`, khi tiến độ đạt khoảng `25%–50%`, nhấn **`Ctrl + C`** (hoặc gõ `/quit`) trên máy gửi.
  3. Kiểm tra thư mục `downloads/` trên máy nhận.
* **Kết quả kỳ vọng:**
  * Máy nhận phát hiện ngắt luồng/nhận khung `FABORT`, thông báo hủy truyền tệp và **tự động xóa sạch tệp `.part` đang tải dở**, không để lại rác trong thư mục `downloads/`.

### Test 6: Bắt gói tin kiểm chứng trên Wireshark
* **Mục đích:** Xác minh hoạt động thực tế ở tầng Transport (UDP & TCP).
* **Thao tác:** Mở Wireshark trên card mạng `Wi-Fi` (hoặc `Loopback` nếu test 1 máy) và áp dụng 2 bộ lọc:
  1. **Kiểm tra UDP Discovery:** Nhập filter `udp.port == 9999` → Quan sát các gói tin gửi tới `255.255.255.255` định kỳ mỗi 3 giây chứa chuỗi `HI|...`.
  2. **Kiểm tra TCP 3-Way Handshake:** Nhập filter `tcp.flags.syn == 1` hoặc theo dõi luồng `tcp.stream` tương ứng với cổng TCP của máy nhận → Quan sát đủ 3 gói `[SYN]`, `[SYN, ACK]`, `[ACK]` ngay khi gõ lệnh `/chat`, theo sau là các gói `[PSH, ACK]` mang khung `HI|` và `MSG|`.

---

## ❓ Xử lý sự cố thường gặp (Troubleshooting)

| Hiện tượng | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| Hai máy cùng Wi-Fi nhưng `/list` không thấy nhau | Windows Firewall chặn gói UDP đến, hoặc Wi-Fi bật *AP Isolation* | Cho phép `python.exe` qua Firewall (mục Private & Public) hoặc dùng điểm phát sóng di động (Mobile Hotspot) làm mạng LAN chung. |
| Lỗi `ModuleNotFoundError: No module named 'prompt_toolkit'` | Chưa cài thư viện phụ thuộc hoặc chưa kích hoạt đúng môi trường ảo `.venv` | Chạy lại `pip install prompt_toolkit` trong đúng cửa sổ Terminal đang dùng. |
| Nhập tên báo lỗi không hợp lệ | Tên chứa ký tự dấu gạch đứng `\|` hoặc chỉ toàn khoảng trắng | Ký tự `\|` được dùng làm dấu phân tách khung giao thức tầng ứng dụng, hãy chọn tên khác không chứa ký tự này. |

---

## 👥 Thành viên thực hiện (Nhóm Đồ án 1)

| STT | Họ và Tên | MSSV | Vai trò & Phân công chính |
| :-: | :--- | :---: | :--- |
| 1 | **Huỳnh Hoàng Nguyên** | `25120213` | Thiết kế & xây dựng phân hệ dò tìm ngang hàng **UDP Radar** (`broadcaster`, `listener`, `timeout_checker`). |
| 2 | **Dương Hồng Đức** | `25120177` | Thiết kế giao thức phân khung **TCP**, truyền tệp tin bất đồng bộ đa luồng (`64 KB` chunking, `.part` safety). |
| 3 | **Nguyễn Gia Huy** | `25120192` | Xây dựng giao diện **CLI bất đồng bộ** (`prompt_toolkit`), bộ điều phối phiên chat & kiểm thử tích hợp đa máy. |