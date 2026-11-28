import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import socket
import time
import sys
import os
import re

import uti
from uti import Fore, Style
import p2p_radar
from p2p_radar import (init_radar, online_peers, peer_lock,
                       broadcaster_thread, listener_thread, timeout_checker_thread,
                       broadcast_leave)
import p2p_tcp
from p2p_tcp import (connected_peers, conn_lock, send_hi, send_msg, send_bye,
                     tcp_receiver_thread, tcp_acceptor, close_connection,
                     set_current_chat, get_current_chat, get_unseen_msg)
from file_sender import start_send_file, cancel_all

SCAN_SECONDS = 3.5

# Bảng màu đồng bộ với main.py / p2p_tcp.py / p2p_radar.py
C_ME   = Fore.LIGHTGREEN_EX
C_PEER = Fore.LIGHTCYAN_EX
C_WAIT = Style.BRIGHT + Fore.LIGHTMAGENTA_EX
C_SYS  = Fore.YELLOW
C_ERR  = Style.BRIGHT + Fore.RED
C_TIME = Fore.LIGHTBLACK_EX
RESET  = Style.RESET_ALL

# Ánh xạ mã màu ANSI (colorama) sang tag màu hiển thị trên CTkTextbox
ANSI_TAG_MAP = {
    "30": ("ansi_30", "#414868"),
    "31": ("ansi_31", "#f7768e"),   # RED / C_ERR
    "32": ("ansi_32", "#9ece6a"),
    "33": ("ansi_33", "#e0af68"),   # YELLOW / C_SYS
    "34": ("ansi_34", "#7aa2f7"),
    "35": ("ansi_35", "#bb9af7"),
    "36": ("ansi_36", "#7dcfff"),
    "37": ("ansi_37", "#c0caf5"),
    "90": ("ansi_90", "#565f89"),   # LIGHTBLACK_EX / C_TIME
    "91": ("ansi_91", "#ff6b6b"),
    "92": ("ansi_92", "#2ecc71"),   # LIGHTGREEN_EX / C_ME
    "93": ("ansi_93", "#f1fa8c"),
    "94": ("ansi_94", "#7aa2f7"),
    "95": ("ansi_95", "#ff79c6"),   # LIGHTMAGENTA_EX / C_WAIT
    "96": ("ansi_96", "#8be9fd"),   # LIGHTCYAN_EX / C_PEER
    "97": ("ansi_97", "#ffffff"),
}

ANSI_COLOR_RE = re.compile(r'\x1b\[([0-9;]*)m')
ANSI_OTHER_RE = re.compile(r'\x1b\[[0-9;?]*[A-Za-ln-z]')

_orig_print_color = uti.print_color

root_window = None
login_frame = None
main_chat_frame = None
sidebar_frame = None

entry_name = None
entry_msg = None
search_bar = None
chat_history = None
peer_list_frame = None
chat_target_lbl = None
waiting_bar_frame = None
waiting_items_frame = None

my_name = ""
my_port = 0
server_sock = None
current_chat_target = None
is_closing = False
_last_waiting_snapshot = None


def setup_chat_tags(textbox):
    textbox.tag_config("default", foreground="#ffffff")
    for tag_name, hex_color in ANSI_TAG_MAP.values():
        textbox.tag_config(tag_name, foreground=hex_color)


def parse_ansi_segments(text):
    text = ANSI_OTHER_RE.sub("", text)
    segments = []
    current_tag = "default"
    pos = 0
    for match in ANSI_COLOR_RE.finditer(text):
        if match.start() > pos:
            segments.append((text[pos:match.start()], current_tag))
        raw_codes = match.group(1)
        codes = [c for c in raw_codes.split(";") if c] if raw_codes else ["0"]
        for code in codes:
            if code in ("0", "39"):
                current_tag = "default"
            elif code in ANSI_TAG_MAP:
                current_tag = ANSI_TAG_MAP[code][0]
        pos = match.end()
    if pos < len(text):
        segments.append((text[pos:], current_tag))
    return segments


def append_to_chat_ansi(text):
    if not chat_history or is_closing:
        return
    try:
        if not root_window or not root_window.winfo_exists():
            return
        chat_history.configure(state="normal")
        for seg_text, tag_name in parse_ansi_segments(text):
            chat_history.insert("end", seg_text, tag_name)
        chat_history.insert("end", "\n", "default")
        chat_history.see("end")
        chat_history.configure(state="disabled")
    except tk.TclError:
        pass


def _on_gui_log(full_text):
    append_to_chat_ansi(full_text)
    refresh_waiting_bar()


def gui_print_color(*args, sep=" ", **kwargs):
    raw = sep.join(str(a) for a in args)
    cleaned = raw.replace("\r", "").strip("\n")
    if not cleaned:
        return
    timestamp = time.strftime("%H:%M:%S")
    full_text = f"{C_TIME}[{timestamp}]{RESET} {cleaned}{RESET}"
    if root_window and not is_closing:
        try:
            root_window.after(0, _on_gui_log, full_text)
        except tk.TclError:
            pass


class ConsoleRedirector:
    encoding = "utf-8"

    def __init__(self):
        self._buffer = ""
        self._lock = threading.Lock()

    def isatty(self):
        return False

    def write(self, text):
        if not text:
            return 0
        with self._lock:
            self._buffer += text.replace("\r", "")
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip() and root_window and not is_closing:
                    try:
                        root_window.after(0, _on_gui_log, line)
                    except tk.TclError:
                        pass
        return len(text)

    def flush(self):
        with self._lock:
            if self._buffer.strip() and root_window and not is_closing:
                line = self._buffer
                self._buffer = ""
                try:
                    root_window.after(0, _on_gui_log, line)
                except tk.TclError:
                    pass


def install_gui_output():
    uti.print_color = gui_print_color
    p2p_radar.print_color = gui_print_color
    p2p_tcp.print_color = gui_print_color
    sys.stdout = ConsoleRedirector()
    sys.stderr = sys.stdout


def get_unseen_counts():
    with p2p_tcp._unseen_lock:
        return {name: len(msgs) for name, msgs in p2p_tcp._unseen_msg.items() if msgs}


def refresh_waiting_bar(force=False):
    global _last_waiting_snapshot
    if not waiting_items_frame or is_closing:
        return
    try:
        if not root_window or not root_window.winfo_exists():
            return
    except tk.TclError:
        return

    counts = get_unseen_counts()
    if not force and counts == _last_waiting_snapshot:
        return
    _last_waiting_snapshot = dict(counts)

    for widget in waiting_items_frame.winfo_children():
        widget.destroy()

    if not counts:
        ctk.CTkLabel(
            waiting_items_frame,
            text="Không có tin nhắn chờ",
            font=("Arial", 12),
            text_color="#565f89"
        ).pack(side="left", pady=6)
    else:
        for sender, count in counts.items():
            btn = ctk.CTkButton(
                waiting_items_frame,
                text=f"{sender} ({count})",
                height=26,
                width=10,
                corner_radius=13,
                fg_color="#3b264d",
                hover_color="#563670",
                text_color="#ff79c6",
                font=("Arial", 12, "bold"),
                command=lambda target=sender: connect_to_peer(target)
            )
            btn.pack(side="left", padx=(0, 6), pady=6)


def show_login_screen():
    global login_frame, entry_name

    login_frame = ctk.CTkFrame(root_window, fg_color="#1a1b26")
    login_frame.pack(fill="both", expand=True)

    card = ctk.CTkFrame(login_frame, width=400, height=300, corner_radius=15, fg_color="#24283b")
    card.place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(card, text="💬", font=("Arial", 30)).pack(pady=(30, 10))
    ctk.CTkLabel(card, text="Trò chuyện gần hơn.", font=("Arial", 20, "bold"), text_color="white").pack(anchor="w", padx=40)
    ctk.CTkLabel(
        card,
        text="Một không gian đơn giản để nhắn tin và chia sẻ file.\nBắt đầu bằng tên hiển thị của bạn.",
        font=("Arial", 12),
        text_color="#a9b1d6",
        justify="left"
    ).pack(anchor="w", padx=40, pady=(5, 20))

    ctk.CTkLabel(card, text="Tên hiển thị", font=("Arial", 11), text_color="#a9b1d6").pack(anchor="w", padx=40)

    entry_name = ctk.CTkEntry(
        card,
        placeholder_text="Nhập tên của bạn...",
        width=320,
        height=40,
        corner_radius=8,
        fg_color="#1f2335",
        border_width=1
    )
    entry_name.pack(pady=(5, 10))
    entry_name.bind("<Return>", lambda e: process_login())

    btn_start = ctk.CTkButton(
        card,
        text="Bắt đầu trò chuyện ➔",
        width=320,
        height=40,
        corner_radius=8,
        fg_color="#2ecc71",
        hover_color="#27ae60",
        text_color="black",
        font=("Arial", 14, "bold"),
        command=process_login
    )
    btn_start.pack(pady=(5, 20))


def show_main_chat_screen():
    global main_chat_frame, sidebar_frame, chat_history, entry_msg
    global search_bar, peer_list_frame, chat_target_lbl
    global waiting_bar_frame, waiting_items_frame

    root_window.configure(fg_color="#1a1b26")

    sidebar_frame = ctk.CTkFrame(root_window, width=280, corner_radius=0, fg_color="#16161e")
    sidebar_frame.pack(side="left", fill="y")
    sidebar_frame.pack_propagate(False)

    ctk.CTkLabel(sidebar_frame, text="TIN NHẮN CỦA BẠN", font=("Arial", 10, "bold"), text_color="#a9b1d6").pack(anchor="w", padx=20, pady=(20, 5))
    ctk.CTkLabel(sidebar_frame, text="Trò chuyện", font=("Arial", 22, "bold"), text_color="white").pack(anchor="w", padx=20)
    ctk.CTkLabel(sidebar_frame, text="Kết nối đang hoạt động", font=("Arial", 11), text_color="#2ecc71").pack(anchor="w", padx=20, pady=(0, 15))

    search_bar = ctk.CTkEntry(
        sidebar_frame,
        placeholder_text="🔍 Tìm người trò chuyện...",
        width=240,
        height=35,
        corner_radius=8,
        fg_color="#1f2335",
        border_width=0
    )
    search_bar.pack(pady=10)
    search_bar.bind("<KeyRelease>", lambda e: update_peer_list_ui(reschedule=False))

    ctk.CTkLabel(sidebar_frame, text="ĐANG TRỰC TUYẾN", font=("Arial", 10, "bold"), text_color="#a9b1d6").pack(anchor="w", padx=20, pady=(15, 5))

    peer_list_frame = ctk.CTkScrollableFrame(sidebar_frame, fg_color="transparent")
    peer_list_frame.pack(fill="both", expand=True, padx=10)

    main_chat_frame = ctk.CTkFrame(root_window, corner_radius=0, fg_color="#1a1b26")
    main_chat_frame.pack(side="right", fill="both", expand=True)

    header = ctk.CTkFrame(main_chat_frame, height=60, corner_radius=0, fg_color="#1a1b26")
    header.pack(fill="x", pady=10, padx=20)

    ctk.CTkButton(header, text=f"👤 {my_name}", fg_color="#24283b", width=100, height=35, corner_radius=20, hover=False).pack(side="right")

    chat_target_lbl = ctk.CTkLabel(header, text="Chào mừng đến với Kết nối", font=("Arial", 16, "bold"), text_color="white")
    chat_target_lbl.pack(side="left")

    chat_history = ctk.CTkTextbox(main_chat_frame, font=("Arial", 14), fg_color="#1f2335", text_color="white", corner_radius=15)
    chat_history.pack(fill="both", expand=True, padx=20, pady=(10, 8))
    setup_chat_tags(chat_history)
    chat_history.insert("0.0", "Hệ thống đã khởi động...\nChọn một người dùng bên trái để nhắn tin.\n", "ansi_33")
    chat_history.configure(state="disabled")

    # Dòng tin nhắn chờ ở dưới khung chat
    waiting_bar_frame = ctk.CTkFrame(main_chat_frame, height=38, corner_radius=10, fg_color="#16161e")
    waiting_bar_frame.pack(fill="x", padx=20, pady=(0, 10))
    waiting_bar_frame.pack_propagate(False)

    ctk.CTkLabel(
        waiting_bar_frame,
        text="📩 Tin nhắn chờ:",
        font=("Arial", 12, "bold"),
        text_color="#ff79c6"
    ).pack(side="left", padx=(12, 8))

    waiting_items_frame = ctk.CTkFrame(waiting_bar_frame, fg_color="transparent")
    waiting_items_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

    refresh_waiting_bar(force=True)
    install_gui_output()

    input_frame = ctk.CTkFrame(main_chat_frame, fg_color="transparent")
    input_frame.pack(fill="x", padx=20, pady=(0, 20))

    btn_file = ctk.CTkButton(input_frame, text="📁", width=40, height=40, fg_color="#24283b", corner_radius=10, command=handle_send_file)
    btn_file.pack(side="left", padx=(0, 10))

    entry_msg = ctk.CTkEntry(input_frame, placeholder_text="Nhập tin nhắn...", height=40, corner_radius=10, fg_color="#1f2335", border_width=0)
    entry_msg.pack(side="left", fill="x", expand=True, padx=(0, 10))
    entry_msg.bind("<Return>", lambda e: handle_send_msg())

    btn_send = ctk.CTkButton(
        input_frame,
        text="Gửi",
        width=60,
        height=40,
        fg_color="#2ecc71",
        text_color="black",
        hover_color="#27ae60",
        corner_radius=10,
        command=handle_send_msg
    )
    btn_send.pack(side="right")

    update_peer_list_ui()


def process_login():
    global my_name, my_port, server_sock, login_frame

    name = entry_name.get().strip()
    if not name or "|" in name or any(ch.isspace() for ch in name):
        messagebox.showerror("Lỗi", "Tên không được để trống, chứa khoảng trắng hoặc ký tự '|'!")
        return

    my_name = name

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("", 0))
    server_sock.listen(5)
    my_port = server_sock.getsockname()[1]

    init_radar(my_name, my_port)
    with peer_lock:
        online_peers[my_name] = {
            "ip": "127.0.0.1",
            "port": my_port,
            "status": p2p_radar.my_status,
            "last_seen": time.time()
        }

    # Tạo giao diện và gắn bộ chuyển hướng màu trước khi khởi chạy các thread mạng
    login_frame.destroy()
    root_window.title(f"P2P Chat - {my_name} (Port: {my_port})")
    show_main_chat_screen()

    threading.Thread(target=tcp_acceptor, args=(server_sock,), daemon=True).start()
    threading.Thread(target=broadcaster_thread, daemon=True).start()
    threading.Thread(target=listener_thread, daemon=True).start()
    threading.Thread(target=timeout_checker_thread, daemon=True).start()


def update_peer_list_ui(reschedule=True):
    if is_closing or not peer_list_frame:
        return
    try:
        if not root_window or not root_window.winfo_exists():
            return
    except tk.TclError:
        return

    keyword = search_bar.get().strip().lower() if search_bar else ""
    unseen_counts = get_unseen_counts()

    for widget in peer_list_frame.winfo_children():
        widget.destroy()

    with peer_lock:
        peers_snapshot = list(online_peers.items())

    for name, info in peers_snapshot:
        if name == my_name:
            continue
        if keyword and keyword not in name.lower():
            continue

        icon = "🟢" if info["status"] == "online" else "🔴"
        unread = unseen_counts.get(name, 0)
        label_text = f"{icon} {name}  ({unread})" if unread > 0 else f"{icon} {name}"
        is_active = (name == current_chat_target)

        btn = ctk.CTkButton(
            peer_list_frame,
            text=label_text,
            anchor="w",
            fg_color="#24283b" if is_active else "transparent",
            hover_color="#24283b",
            text_color="#ff79c6" if unread > 0 else "white",
            height=35,
            command=lambda target=name: connect_to_peer(target)
        )
        btn.pack(fill="x", pady=2)

    refresh_waiting_bar()

    if reschedule and not is_closing:
        root_window.after(1500, update_peer_list_ui)


def connect_to_peer(target_name):
    global current_chat_target
    current_chat_target = target_name
    set_current_chat(target_name)
    chat_target_lbl.configure(text=f"Đang trò chuyện với: {target_name}")

    with conn_lock:
        sock = connected_peers.get(target_name)

    if not sock:
        with peer_lock:
            info = online_peers.get(target_name)

        if info:
            gui_print_color(f"{C_SYS}[*] Đang kết nối tới {target_name}...")
            try:
                new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                new_sock.settimeout(5)
                new_sock.connect((info["ip"], info["port"]))
                new_sock.settimeout(None)

                send_hi(new_sock, my_name, my_port)

                with conn_lock:
                    connected_peers[target_name] = new_sock

                threading.Thread(target=tcp_receiver_thread, args=(new_sock, target_name), daemon=True).start()
                gui_print_color(f"{C_SYS}[*] Đã kết nối tới {target_name}.")
            except Exception as e:
                gui_print_color(f"{C_ERR}[!] Không thể kết nối tới {target_name}: {e}")

    # Nạp và hiển thị toàn bộ tin nhắn chờ của người này
    unseen = get_unseen_msg(target_name)
    if unseen:
        for msg in unseen:
            gui_print_color(f"{C_PEER}[{target_name}] {RESET}{msg}")

    refresh_waiting_bar(force=True)
    update_peer_list_ui(reschedule=False)


def handle_send_msg():
    if not current_chat_target:
        messagebox.showwarning("Cảnh báo", "Vui lòng chọn người dùng bên trái trước!")
        return

    text = entry_msg.get().strip()
    if not text:
        return

    with conn_lock:
        sock = connected_peers.get(current_chat_target)

    if sock:
        try:
            send_msg(sock, text)
            gui_print_color(f"{C_ME}[Bạn] {RESET}{text}")
            entry_msg.delete(0, tk.END)
        except Exception as e:
            gui_print_color(f"{C_ERR}[!] Gửi lỗi: {e}")
    else:
        gui_print_color(f"{C_ERR}[!] Mất kết nối TCP với {current_chat_target}.")


def handle_send_file():
    if not current_chat_target:
        messagebox.showwarning("Cảnh báo", "Vui lòng chọn người dùng bên trái trước!")
        return

    filepath = filedialog.askopenfilename()
    if not filepath:
        return

    with conn_lock:
        sock = connected_peers.get(current_chat_target)

    if not sock:
        gui_print_color(f"{C_ERR}[!] Chưa có kết nối TCP với {current_chat_target}.")
        return

    def on_progress(tr, pct):
        gui_print_color(f"{C_SYS}[*] Đang gửi {tr.filename}: {pct}%")

    def on_done(tr, ok, err):
        if ok:
            gui_print_color(f"{C_SYS}[*] Gửi file {tr.filename} thành công.")
        else:
            gui_print_color(f"{C_ERR}[!] Gửi file thất bại: {err}")

    try:
        tr = start_send_file(sock, filepath, current_chat_target, on_progress, on_done)
        gui_print_color(f"{C_SYS}[*] Bắt đầu gửi file {tr.filename} ({tr.size} bytes)...")
    except (ValueError, OSError) as e:
        messagebox.showerror("Lỗi", str(e))


def handle_shutdown():
    global is_closing
    is_closing = True

    uti.print_color = _orig_print_color
    p2p_radar.print_color = _orig_print_color
    p2p_tcp.print_color = _orig_print_color
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

    cancel_all()
    print("Đang đóng các kết nối...")
    with conn_lock:
        socks = list(connected_peers.values())
        connected_peers.clear()
    for sock in socks:
        close_connection(sock, say_bye=True)

    broadcast_leave()
    if server_sock:
        try:
            server_sock.close()
        except OSError:
            pass

    if root_window:
        root_window.destroy()
    sys.exit(0)


def main():
    global root_window

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    root_window = ctk.CTk()
    root_window.title("Ứng dụng P2P Chat")
    root_window.geometry("1000x600")

    root_window.protocol("WM_DELETE_WINDOW", handle_shutdown)

    show_login_screen()
    root_window.mainloop()


if __name__ == "__main__":
    main()