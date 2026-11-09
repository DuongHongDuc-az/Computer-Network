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

def init_status(status):
    global my_status
    my_status = status
    
    with peer_lock:
        if my_name in online_peers:
            online_peers[my_name]['status'] = status

def init_radar(name, port):
    global my_name, my_port
    my_name = name
    my_port = port

    with peer_lock:
        online_peers[my_name] = {
            "ip": "127.0.0.1",
            "port": my_port,
            "status": my_status,
            "last_seen": time.time()
        }

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
        
def broadcast_leave():
    global leaving
    leaving = True
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    message = f"LEAVE|{my_name}|{my_port}".encode('utf-8')
    for _ in range(2): 
        try:
            udp_sock.sendto(message, ('255.255.255.255', 9999))
        except Exception:
            pass
        time.sleep(0.05)
    udp_sock.close()

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
            elif len(parts) >= 3 and parts[0] == "LEAVE":
                peer_name = parts[1]

                with peer_lock:
                    if peer_name in online_peers:
                        del online_peers[peer_name]
                        print(f"\r[!] {peer_name} has left the network.")
                        print("> ", end="", flush=True)
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