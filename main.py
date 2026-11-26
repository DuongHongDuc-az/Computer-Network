import os
import socket
import sys
import threading
import time
import p2p_radar 
import asyncio
import uti


from uti import patch_stdout , PromptSession , print_color , Fore, Style

from p2p_radar import (init_radar, init_status, online_peers, peer_lock,
                       broadcaster_thread, listener_thread, timeout_checker_thread,
                       broadcast_leave)
from p2p_tcp import (connected_peers, conn_lock, send_hi, send_msg, send_bye,
                     tcp_receiver_thread, tcp_acceptor, close_connection, set_current_chat,
                     get_current_chat,get_unseen_msg)
from file_sender import start_send_file, cancel_all

MAX_FILE_SIZE = 50*1024*1024 # 50MB
SCAN_SECONDS = 3.5

C_ME     = Fore.LIGHTGREEN_EX
C_PEER   = Fore.LIGHTCYAN_EX
C_WAIT   = Style.BRIGHT + Fore.LIGHTMAGENTA_EX
C_SYS    = Fore.YELLOW
C_ERR    = Style.BRIGHT + Fore.RED
C_TIME   = Fore.LIGHTBLACK_EX
RESET    = Style.RESET_ALL



def get_connection(name):
    with conn_lock:
        return connected_peers.get(name)
        
def drop_connection(name):
    with conn_lock:
        sock = connected_peers.pop(name, None)
    if sock:
        try:
            sock.shutdown(socket.SHUT_WR)
            time.sleep(0.05)
            sock.close()
        except OSError:
            pass

def cmd_chat(parts, my_name, my_port):
    if len(parts) < 2:
        print_color(f"{C_SYS}Usage: /chat <name>")
        return
    target = parts[1]
    
    if target == my_name:
        print_color(f"{C_SYS}You cannot chat with yourself.")
        return
    if not get_connection(target):
        with peer_lock:
            info = online_peers.get(target)
        if not info:
            print_color(f"{C_SYS}Users is not online!")
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((info["ip"], info["port"]))
            sock.settimeout(None)
            send_hi(sock, my_name, my_port)
        except OSError as e:
            print_color(f"{C_ERR}[!] Cannot connect to {target}: {e}")
            return
    
        with conn_lock:
            connected_peers[target] = sock
        threading.Thread(target=tcp_receiver_thread, args=(sock, target), daemon=True).start()
    set_current_chat(target)
    print_color(f"{C_SYS}[*] Connected to {target}.")
    unseen = get_unseen_msg(target)
    for msg in unseen :
        print_color(f"{C_PEER}[{target}] {RESET}{msg}")

def send_direct_msg(target,text):
    sock = get_connection(target)
    if not sock:
        print_color(f"{C_ERR}[!] Not connected to {target}. Use /chat {target} first.")
        if get_current_chat() == target:
            set_current_chat(None)
        return
    try:
        send_msg(sock,text)
    except OSError as e:
        print_color(f"{C_ERR}[!] Send failed: {e}")
        drop_connection(target)
        if get_current_chat() == target:
            set_current_chat(None)

def cmd_msg(command):
    parts = command.split(" ", 2)
    if len(parts) < 3 or not parts[2].strip():
        print_color(f"{C_SYS}Usage: /msg <name> <text>")
        return
    _, target, text = parts
    
    sock = get_connection(target)
    
    if not sock:
        print_color(f"{C_ERR}[!] Not connected to {target}. Use /chat {target} first.")
        return
    try:
        send_msg(sock, text)
    except OSError as e:
        print_color(f"{C_ERR}[!] Send failed: {e}")
        drop_connection(target)

def cmd_file(command):
    parts = command.split(" ", 2)
    if len(parts) < 3:
        print_color(f"{C_SYS}[!] Usage: /file <name> <path>")
        return
    _, target, path = parts
    path = path.strip().strip('"')
 
    sock = get_connection(target)
    if not sock:
        print_color(f"{C_ERR}[!] Not connected to {target}. Use /chat {target} first.")
        return
    def on_progress(tr, pct):
        print_color(f"{C_SYS}Sending {tr.filename} -> {target}: {pct}")
        
    def on_done(tr, ok, err):
        if ok:
            print_color(f"{C_SYS}Send {tr.filename} ({tr.size} bytes) to {target}")
        else:
            print_color(f"{C_SYS}Send {tr.filename} failed: {err}")
    try:
        tr = start_send_file(sock, path, target, on_progress, on_done)
        print_color(f"{C_SYS}Starting {tr.filename} ({tr.size} bytes) in background")
    except (ValueError, OSError) as e:
        print_color(f"{C_ERR}{e}")

def cmd_bye(command):
    parts = command.split()
    target = parts[1] if len(parts) >=2 else get_current_chat()
    if not target:
        print_color(f"{C_SYS}[!] Usage: /bye [name]")
        return
    
    sock = get_connection(target)
    if not sock:
        print_color(f"{C_ERR}[!] Not connected to {target}.")
        return
    try:
        send_bye(sock)
    except OSError:
        pass
    drop_connection(target)
    if get_current_chat() == target:
        set_current_chat(None)
    print_color(f"{C_SYS}[*] Closed chat with {target}.")
 
 
def cmd_conns():
    with conn_lock:
        names = list(connected_peers.keys())
    if not names:
        print_color(f"{C_SYS}[*] No active chats.")
    else:
        print_color(f"{C_SYS}Active chats: " + ", ".join(names))
 
 
def shutdown(server_sock=None):
    cancel_all()
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
async def main():
        
        print("="*50)
        print("         P2P CHAT & FILE TRANSFER SYSTEM")
        print("="*50)
        
        while True:
            my_name = input("Enter your name: ").strip()
            if not my_name or "|" in my_name:
                print_color(f"{C_SYS}[!] Name cannot be empty or contain '|'. Please try again.")
                continue
            break
            
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(('', 0))
        server_sock.listen(5)
        my_port = server_sock.getsockname()[1]
     
        init_radar(my_name, my_port) 
    
        print(f"\n[*] Starting Radar for [{my_name}]...")
        print("Supported commands: /chat <name>, /back, /list, /msg <name> <text>, /status <status_name>, /quit")
        print("           /file <name> <path>, /bye <name>, /conns, /quit")
        print("-" * 50)
        with patch_stdout():
                    threading.Thread(target=tcp_acceptor, args=(server_sock,), daemon=True).start()
                    threading.Thread(target=broadcaster_thread, daemon=True).start()
                    threading.Thread(target=listener_thread, daemon=True).start()
                    threading.Thread(target=timeout_checker_thread, daemon=True).start()
            
                    session = PromptSession()
                    session.app.erase_when_done = True
                    while True:
                        try:
                            active = get_current_chat()
                            prompt_text = "> "
                            command = await session.prompt_async(prompt_text)
                            command = command.strip()

                            if command == "":
                                continue            
                            if not command.startswith("/"):
                                if active:
                                    print_color(f"{C_ME}[Me] {RESET}{command}")
                                    send_direct_msg(active,command)
                                else:
                                    print(f"> {command}")
                                    print(f"{C_SYS}[!] You haven't selected a chat partner. Use /chat [name] to start.")
                                continue
                            print(f"> {command}")

                            parts = command.split()
                            if parts[0] == "/chat":
                                cmd_chat(parts, my_name, my_port)
                            elif parts[0] == "/back":
                                if active:
                                    set_current_chat(None)
                                    print_color(f"{C_SYS}[*] Left chat with {active} (still connected).")
                                else:
                                    print_color(f"{C_SYS}[*] You are on the main screen.")
                            elif parts[0] == "/msg":
                                cmd_msg(command)
                            elif parts[0] in ("/file", "/sendfile"):
                                cmd_file(command)
                            elif parts[0] == "/bye":
                                cmd_bye(command)
                            elif parts[0] == "/conns":
                                cmd_conns()               
                            elif parts[0] == "/list":
                                with peer_lock:
                                    if not online_peers:
                                        print_color(f"{C_SYS}[*] No peers found in the LAN yet.")
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
                                                
                                        print_color(f"{C_SYS}[*] Status changed to: {new_status}")
                                    else:
                                        print_color(f"{C_ERR}[!] Error: Invalid status.")
                                        print_color(f"{C_SYS}[-] Allowed statuses are: online, busy, away")
                                else:
                                    print_color(f"{C_SYS}[!] Invalid syntax. Usage: /status <status_name>")
                                    
                            elif command == "/quit":
                                print_color(f"{C_SYS}[*] Disconnecting and exiting...")
                                shutdown(server_sock)
                                sys.exit(0)
                                
                            else:
                                print_color(f"{C_SYS}[!] Invalid command: {command}")
                                
                        except KeyboardInterrupt:
                            print_color(f"\n{C_SYS}[*] Shutting down system...")
                            shutdown(server_sock)
                            sys.exit(0)
    

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
