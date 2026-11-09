
import os
import socket
import sys
import threading
import time
import p2p_radar 
from p2p_radar import (init_radar, init_status, online_peers, peer_lock,
                       broadcaster_thread, listener_thread, timeout_checker_thread,
                       broadcast_leave)
from p2p_tcp import (connected_peers, conn_lock, send_hi, send_msg, send_bye,
                     send_file_frame, tcp_receiver_thread, tcp_acceptor,
                     close_connection)

MAX_FILE_SIZE = 50*1024*1024 # 50MB

def get_connection(name):
    with conn_lock:
        return connected_peers.get(name)
        
def drop_connection(name):
    with conn_lock:
        sock = connected_peers.pop(name, None)
    if sock:
        try:
            sock.close()
        except OSError:
            pass

def cmd_chat(parts, my_name, my_port):
    if len(parts) < 2:
        print("Usage: /chat <name>")
        return
    target = parts[1]
    
    if target == my_name:
        print("You cannot chat with yourself.")
        return
    if  get_connection(target):
        print(f"Already connectecd to {target}")
        return
    with peer_lock:
        info = online_peers.get(target)
    if not info:
        print("Users is not online!")
        return
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((info["ip"], info["port"]))
        sock.settimeout(None)
        send_hi(sock, my_name, my_port)
    except OSError as e:
        print(f"[!] Cannot connect to {target}: {e}")
        return
 
    with conn_lock:
        connected_peers[target] = sock
    threading.Thread(target=tcp_receiver_thread, args=(sock, target), daemon=True).start()
    print(f"Connected to {target}. Use /msg {target} <text> or /file {target} <path>")

def cmd_msg(command):
    parts = command.split(" ", 2)
    if len(parts) < 3 or not parts[2].strip():
        print("Usage: /msg <name> <text>")
        return
    _, target, text = parts
    
    sock = get_connection(target)
    
    if not sock:
        print(f"[!] Not connected to {target}. Use /chat {target} first.")
        return
    try:
        send_msg(sock, text)
    except OSError as e:
        print(f"[!] Send failed: {e}")
        drop_connection(target)

def cmd_file(command):
    parts = command.split(" ", 2)
    if len(parts) < 3:
        print("[!] Usage: /file <name> <path>")
        return
    _, target, path = parts
    path = path.strip().strip('"')
 
    sock = get_connection(target)
    if not sock:
        print(f"[!] Not connected to {target}. Use /chat {target} first.")
        return
    if not os.path.isfile(path):
        print(f"[!] File not found: {path}")
        return
    size = os.path.getsize(path)
    if size > MAX_FILE_SIZE:
        print(f"[!] File too large ({size} bytes, max {MAX_FILE_SIZE}).")
        return
 
    try:
        with open(path, "rb") as f:
            data = f.read()
        send_file_frame(sock, os.path.basename(path), data)
        print(f"[+] Sent {os.path.basename(path)} ({size} bytes) to {target}")
    except OSError as e:
        print(f"[!] Send failed: {e}")
        drop_connection(target)

def cmd_bye(parts):
    if len(parts) < 2:
        print("[!] Usage: /bye <name>")
        return
    target = parts[1]
    sock = get_connection(target)
    if not sock:
        print(f"[!] Not connected to {target}.")
        return
    try:
        send_bye(sock)
    except OSError:
        pass
    drop_connection(target)
    print(f"[*] Closed chat with {target}.")
 
 
def cmd_conns():
    with conn_lock:
        names = list(connected_peers.keys())
    if not names:
        print("[*] No active chats.")
    else:
        print("Active chats: " + ", ".join(names))
 
 
def shutdown(server_sock=None):
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
 


if __name__ == "__main__":
    print("="*50)
    print("            P2P RADAR SYSTEM - PHASE 1")
    print("="*50)
    
    while True:
        my_name = input("Enter your name: ").strip()
        if not my_name or "|" in my_name:
            print("[!] Name cannot be empty or contain '|'. Please try again.")
            continue
        break
        
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(('', 0))
    server_sock.listen(5)
    my_port = server_sock.getsockname()[1]
 
    init_radar(my_name, my_port) 

    print(f"\n[*] Starting Radar for [{my_name}]...")
    print("Supported commands: /chat <name>, /list, /msg <name> <text>, /status <status_name>, /quit")
    print("           /file <name> <path>, /bye <name>, /conns, /quit")
    print("-" * 50)
    
    threading.Thread(target=tcp_acceptor, args=(server_sock,), daemon=True).start()
    threading.Thread(target=broadcaster_thread, daemon=True).start()
    threading.Thread(target=listener_thread, daemon=True).start()
    threading.Thread(target=timeout_checker_thread, daemon=True).start()
    
    while True:
        try:
            command = input("> ").strip()
            parts = command.split()
            if command == "":
                continue
            elif parts[0] == "/chat":
                cmd_chat(parts, my_name, my_port)
            elif parts[0] == "/msg":
                cmd_msg(command)
            elif parts[0] == "/file":
                cmd_file(command)
            elif parts[0] == "/bye":
                cmd_bye(command)
            elif parts[0] == "/conns":
                cmd_conns()               
            elif parts[0] == "/list":
                with peer_lock:
                    if not online_peers:
                        print("[*] No peers found in the LAN yet.")
                    else:
                        print(f"------ ONLINE PEERS LIST ({len(online_peers)} peers) ------")
                        for name, info in online_peers.items():
                            print(f"- {name:<20} | Status: [{info['status']}]")
                        print("-" * 41)
                        
            elif parts[0] == "/status":
                parts = command.split(" ", 1)
                if len(parts) == 2:
                    new_status = parts[1].strip().lower() 
                    
                    if new_status in ["online", "busy", "away"]:
                        init_status(new_status)
                                
                        print(f"[*] Status changed to: {new_status}")
                    else:
                        print("[!] Error: Invalid status.")
                        print("[-] Allowed statuses are: online, busy, away")
                else:
                    print("[!] Invalid syntax. Usage: /status <status_name>")
                    
            elif command == "/quit":
                print("[*] Disconnecting and exiting...")
                shutdown()
                sys.exit(0)
                
            else:
                print(f"[!] Invalid command: {command}")
                
        except KeyboardInterrupt:
            print("\n[*] Shutting down system...")
            shutdown()
            sys.exit(0)
