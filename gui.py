import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import socket
import time
import sys
import os

import p2p_radar
from p2p_radar import (init_radar, online_peers, peer_lock,
                       broadcaster_thread, listener_thread, timeout_checker_thread,
                       broadcast_leave)
from p2p_tcp import (connected_peers, conn_lock, send_hi, send_msg, send_bye,
                     send_file_frame, tcp_receiver_thread, tcp_acceptor,
                     close_connection)


root_window = None
login_frame = None
main_chat_frame = None
sidebar_frame = None


entry_name = None
entry_msg = None
chat_history = None
peer_list_frame = None
chat_target_lbl = None


my_name = ""
my_port = 0
server_sock = None
current_chat_target = None



class ConsoleRedirector:
    def write(self, text):
        clean_text = text.replace('\r', '').replace('>', '')
        if clean_text.strip() and root_window:
            root_window.after(0, append_to_chat, clean_text)
    def flush(self):
        pass

def append_to_chat(text):
    if chat_history:
        chat_history.configure(state='normal')
        chat_history.insert("end", text + "\n")
        chat_history.see("end")
        chat_history.configure(state='disabled')



def show_login_screen():
    global login_frame, entry_name
    
    login_frame = ctk.CTkFrame(root_window, fg_color="#1a1b26")
    login_frame.pack(fill="both", expand=True)

    card = ctk.CTkFrame(login_frame, width=400, height=300, corner_radius=15, fg_color="#24283b")
    card.place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(card, text="💬", font=("Arial", 30)).pack(pady=(30, 10))
    ctk.CTkLabel(card, text="Trò chuyện gần hơn.", font=("Arial", 20, "bold"), text_color="white").pack(anchor="w", padx=40)
    ctk.CTkLabel(card, text="Một không gian đơn giản để nhắn tin và chia sẻ file.\nBắt đầu bằng tên hiển thị của bạn.", 
                 font=("Arial", 12), text_color="#a9b1d6", justify="left").pack(anchor="w", padx=40, pady=(5, 20))

    ctk.CTkLabel(card, text="Tên hiển thị", font=("Arial", 11), text_color="#a9b1d6").pack(anchor="w", padx=40)
    
    entry_name = ctk.CTkEntry(card, placeholder_text="Nhập tên của bạn...", width=320, height=40, corner_radius=8, fg_color="#1f2335", border_width=1)
    entry_name.pack(pady=(5, 10))
    entry_name.bind('<Return>', lambda e: process_login())

    btn_start = ctk.CTkButton(card, text="Bắt đầu trò chuyện ➔", width=320, height=40, corner_radius=8, 
                              fg_color="#2ecc71", hover_color="#27ae60", text_color="black", font=("Arial", 14, "bold"), command=process_login)
    btn_start.pack(pady=(5,20))

def show_main_chat_screen():
    global main_chat_frame, sidebar_frame, chat_history, entry_msg, peer_list_frame, chat_target_lbl

    root_window.configure(fg_color="#1a1b26")

   
    sidebar_frame = ctk.CTkFrame(root_window, width=280, corner_radius=0, fg_color="#16161e")
    sidebar_frame.pack(side="left", fill="y")
    sidebar_frame.pack_propagate(False)

    ctk.CTkLabel(sidebar_frame, text="TIN NHẮN CỦA BẠN", font=("Arial", 10, "bold"), text_color="#a9b1d6").pack(anchor="w", padx=20, pady=(20, 5))
    ctk.CTkLabel(sidebar_frame, text="Trò chuyện", font=("Arial", 22, "bold"), text_color="white").pack(anchor="w", padx=20)
    ctk.CTkLabel(sidebar_frame, text="Kết nối đang hoạt động", font=("Arial", 11), text_color="#2ecc71").pack(anchor="w", padx=20, pady=(0, 15))

    search_bar = ctk.CTkEntry(sidebar_frame, placeholder_text="🔍 Tìm người trò chuyện...", width=240, height=35, corner_radius=8, fg_color="#1f2335", border_width=0)
    search_bar.pack(pady=10)

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
    chat_history.pack(fill="both", expand=True, padx=20, pady=10)
    chat_history.insert("0.0", "Hệ thống đã khởi động...\nChọn một người dùng bên trái để nhắn tin.\n")
    chat_history.configure(state="disabled")

   
    sys.stdout = ConsoleRedirector()
    sys.stderr = sys.stdout

    input_frame = ctk.CTkFrame(main_chat_frame, fg_color="transparent")
    input_frame.pack(fill="x", padx=20, pady=(0, 20))

    btn_file = ctk.CTkButton(input_frame, text="📁", width=40, height=40, fg_color="#24283b", corner_radius=10, command=handle_send_file)
    btn_file.pack(side="left", padx=(0, 10))

    entry_msg = ctk.CTkEntry(input_frame, placeholder_text="Nhập tin nhắn...", height=40, corner_radius=10, fg_color="#1f2335", border_width=0)
    entry_msg.pack(side="left", fill="x", expand=True, padx=(0, 10))
    entry_msg.bind('<Return>', lambda e: handle_send_msg())

    btn_send = ctk.CTkButton(input_frame, text="Gửi", width=60, height=40, fg_color="#2ecc71", text_color="black", hover_color="#27ae60", corner_radius=10, command=handle_send_msg)
    btn_send.pack(side="right")

   
    update_peer_list_ui()


def process_login():
    global my_name, my_port, server_sock, login_frame

    name = entry_name.get().strip()
    if not name or "|" in name:
        messagebox.showerror("Lỗi", "Tên không được để trống hoặc chứa ký tự '|'!")
        return

    my_name = name
    
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(('', 0))
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

    
    threading.Thread(target=tcp_acceptor, args=(server_sock,), daemon=True).start()
    threading.Thread(target=broadcaster_thread, daemon=True).start()
    threading.Thread(target=listener_thread, daemon=True).start()
    threading.Thread(target=timeout_checker_thread, daemon=True).start()

    
    login_frame.destroy()
    root_window.title(f"P2P Chat - {my_name} (Port: {my_port})")
    show_main_chat_screen()

def update_peer_list_ui():
    
    
    for widget in peer_list_frame.winfo_children():
        widget.destroy()

    with peer_lock:
        for name, info in online_peers.items():
            if name != my_name:
                icon = "🟢" if info['status'] == "online" else "🔴"
                btn = ctk.CTkButton(peer_list_frame, text=f"{icon} {name}", anchor="w", 
                                    fg_color="transparent", hover_color="#24283b", text_color="white", height=35,
                                    command=lambda target=name: connect_to_peer(target))
                btn.pack(fill="x", pady=2)
                
    
    root_window.after(1500, update_peer_list_ui)

def connect_to_peer(target_name):
    global current_chat_target
    current_chat_target = target_name
    chat_target_lbl.configure(text=f"Đang trò chuyện với: {target_name}")

    with conn_lock:
        sock = connected_peers.get(target_name)

    if not sock:
        with peer_lock:
            info = online_peers.get(target_name)
        
        if info:
            print(f"[*] Đang kết nối tới {target_name}...")
            try:
                new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                new_sock.settimeout(5)
                new_sock.connect((info["ip"], info["port"]))
                new_sock.settimeout(None)
                
                send_hi(new_sock, my_name, my_port)

                with conn_lock:
                    connected_peers[target_name] = new_sock

                threading.Thread(target=tcp_receiver_thread, args=(new_sock, target_name), daemon=True).start()
            except Exception as e:
                print(f"[!] Không thể kết nối: {e}")

def handle_send_msg():
    if not current_chat_target:
        messagebox.showwarning("Cảnh báo", "Vui lòng chọn người dùng bên trái trước!")
        return

    text = entry_msg.get().strip()
    if not text: return

    with conn_lock:
        sock = connected_peers.get(current_chat_target)

    if sock:
        try:
            send_msg(sock, text)
            print(f"[Bạn]: {text}")
            entry_msg.delete(0, tk.END)
        except Exception as e:
            print(f"[!] Gửi lỗi: {e}")
    else:
        print(f"[!] Mất kết nối TCP với {current_chat_target}.")

def handle_send_file():
    if not current_chat_target:
        messagebox.showwarning("Cảnh báo", "Vui lòng chọn người dùng bên trái trước!")
        return

    filepath = filedialog.askopenfilename()
    if not filepath: return

    size = os.path.getsize(filepath)
    if size > 50*1024*1024:
        messagebox.showerror("Lỗi", "Chỉ hỗ trợ file tối đa 50MB!")
        return

    with conn_lock:
        sock = connected_peers.get(current_chat_target)

    if sock:
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            filename = os.path.basename(filepath)
            print(f"[*] Đang gửi file {filename} ({size} bytes)...")
            send_file_frame(sock, filename, data)
            print("[+] Đã gửi file thành công!")
        except Exception as e:
            print(f"[!] Lỗi khi gửi file: {e}")

def handle_shutdown():
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

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
        except: pass

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