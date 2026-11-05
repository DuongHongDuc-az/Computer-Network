import socket
import threading
import time
import sys
import random

my_name = ""   
my_port = 0      
my_status = "online"

online_peers = {}             
peer_lock = threading.Lock() 

def find_random_port():
    while True:
        tmp_port = random.randint(1024, 65535)
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            test_sock.bind(('', tmp_port))
            test_sock.close() 
            return tmp_port
        except OSError:
            pass

def broadcaster_thread():
    global my_status
    
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    while True:
        message = f"HI|{my_name}|{my_port}|{my_status}"
        try:
            udp_sock.sendto(message.encode('utf-8'), ('255.255.255.255', 9999))
        except Exception:
            pass 
            
        time.sleep(3) 

def listener_thread():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_sock.bind(('', 9999))
    
    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            received_str = data.decode('utf-8')
            parts = received_str.split('|')
            
            if len(parts) >= 4 and parts[0] == "HI":
                peer_name = parts[1]
                peer_port = int(parts[2])
                peer_status = parts[3]
                
                if peer_name == my_name and peer_port == my_port:
                    continue
                    
                with peer_lock:
                    if peer_name not in online_peers:
                        print(f"\r[*] Radar detected new peer: {peer_name} ({addr[0]}:{peer_port})")
                        print("> ", end="", flush=True)
                        
                    online_peers[peer_name] = {
                        "ip": addr[0],
                        "port": peer_port,
                        "status": peer_status,
                        "last_seen": time.time()
                    }
        except Exception:
            pass

def timeout_checker_thread():
    while True:
        time.sleep(3) 
        current_time = time.time()
        
        with peer_lock:
            blacklist = []
            
            for name, info in online_peers.items():
                if name == my_name:
                    continue

                if current_time - info['last_seen'] > 10:
                    blacklist.append(name)
            
            for dead_peer in blacklist:
                del online_peers[dead_peer]
                print(f"\r[!] {dead_peer} disconnected (Timeout).")
                print("> ", end="", flush=True)

if __name__ == "__main__":
    print("="*50)
    print("            P2P RADAR SYSTEM - PHASE 1")
    print("="*50)
    
    while True:
        my_name = input("Enter your name: ").strip()
        if my_name and "|" not in my_name:
            break
        print("[!] Name cannot be empty or contain '|'. Please try again.")
        
    my_port = find_random_port()

    online_peers[my_name] = {
            "ip": "127.0.0.1",
            "port": my_port,
            "status": my_status,
            "last_seen": time.time()
        }

    print(f"\n[*] Starting Radar for [{my_name}]...")
    print("Supported commands: /list, /status <status_name>, /quit")
    print("-" * 50)

    threading.Thread(target=broadcaster_thread, daemon=True).start()
    threading.Thread(target=listener_thread, daemon=True).start()
    threading.Thread(target=timeout_checker_thread, daemon=True).start()
    
    while True:
        try:
            command = input("> ").strip()
            
            if command == "":
                continue
                
            elif command == "/list":
                with peer_lock:
                    if not online_peers:
                        print("[*] No peers found in the LAN yet.")
                    else:
                        print(f"------ ONLINE PEERS LIST ({len(online_peers)} peers) ------")
                        for name, info in online_peers.items():
                            print(f"- {name:<20} | Status: [{info['status']}]")
                        print("-" * 41)
                        
            elif command.startswith("/status "):
                parts = command.split(" ", 1)
                if len(parts) == 2:
                    new_status = parts[1].strip().lower() 
                    
                    if new_status in ["online", "busy", "away"]:
                        my_status = new_status
                   
                        with peer_lock:
                            if my_name in online_peers:
                                online_peers[my_name]['status'] = my_status
                                
                        print(f"[*] Status changed to: {my_status}")
                    else:
                        print("[!] Error: Invalid status.")
                        print("[-] Allowed statuses are: online, busy, away")
                else:
                    print("[!] Invalid syntax. Usage: /status <status_name>")
                    
            elif command == "/quit":
                print("[*] Disconnecting and exiting...")
                sys.exit(0)
                
            else:
                print(f"[!] Invalid command: {command}")
                
        except KeyboardInterrupt:
            print("\n[*] Shutting down system...")
            sys.exit(0)