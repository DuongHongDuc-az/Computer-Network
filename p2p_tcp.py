import socket
import threading
import time
import os
from typing import Tuple, Dict, Any, Optional
import os
connected_peers = {}
DOWNLOAD_DIR = "download"
conn_lock = threading.Lock()

def recv_exact(sock, n_bytes):
    data = bytearray()
    while len(data) < n_bytes:
        packet = sock.recv(n_bytes-len(data))
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)

def recv_until_delimeter(sock, delimeter = b'|'):
    buffer = bytearray()
    while True:
        chunk = sock.recv(1)
        if not chunk:
            return None
        if chunk == delimeter:
            break
        buffer.extend(chunk)
    return bytes(buffer)

def send_hi(sock, name, tcp_port):
    header = f"HI|{name}|{tcp_port}|".encode('utf-8')
    sock.sendall(header)

def send_msg(sock, text):
    payload_bytes = text.encode('utf-8')
    length = len(payload_bytes)
    header = f"MSG|{length}|".encode('utf-8')
    sock.sendall(header + payload_bytes)
    
def send_bye(sock):
    sock.sendall(b"BYE|")

def send_file_frame(sock, filename, file_bytes):
    size = len(file_bytes)
    header = f"FILE|{filename}|{size}|".encode('utf-8')
    sock.sendall(header + file_bytes)
    
def close_connection(sock, say_bye=True):
    if say_bye:
        try:
            send_bye(sock)
        except OSError:
            pass
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass
    
def recv_frame(sock):
    frame_type_bytes = recv_until_delimeter(sock, b'|')
    if not frame_type_bytes:
        return None
    
    fram_type = frame_type_bytes.decode('utf-8').strip()
    
    if fram_type == "HI":
        name_bytes = recv_until_delimeter(sock, b'|')
        port_bytes = recv_until_delimeter(sock, b'|')
        if not name_bytes or not port_bytes:
            return None
        return "HI", {
            "name": name_bytes.decode('utf-8'),
            "tcp_port": int(port_bytes.decode('utf-8')),
        }
    
    elif fram_type == "MSG":
        length_bytes = recv_until_delimeter(sock, b'|')
        if not length_bytes:
            return None
        length = int(length_bytes.decode('utf-8'))
        payload = recv_exact(sock, length)
        if payload is None:
            return None
        return "MSG", {
            "text": payload.decode('utf-8')
        }
    
    elif fram_type == "FILE":
        filename_bytes = recv_until_delimeter(sock, b'|')
        size_bytes = recv_until_delimeter(sock, b'|')
        if not filename_bytes or not size_bytes:
            return None
        filename = filename_bytes.decode('utf-8')
        size = int(size_bytes.decode('utf-8'))
        
        file_data = recv_exact(sock, size)
        if file_data is None:
            return None
        return "FILE", {
            "filename": filename,
            "size": size,
            "data": file_data
        }
    elif fram_type == "BYE":
        return "BYE", {}
    else:
        raise ValueError(f"Unable to recognize frame type: {fram_type}!")

def tcp_receiver_thread(sock, peer_name=None):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    while True:
        try:
            result = recv_frame(sock)
            if result is None:
                print("UNCONNECTED!")
               
                break
            
            frame_type, data = result
            
            if frame_type == "HI":
                print(f"\n Successful conected with {data['name']} (Port:{data['tcp_port']})")
                peer_name = data['name']
                with conn_lock:
                    connected_peers[peer_name] = sock
                print(f"\r[+] {peer_name} connected (port {data['tcp_port']}).")
                
            elif frame_type == "MSG":
                print(f"\r[{peer_name or '?'}]: {data['text']}")
               
            elif frame_type == "FILE":
                safe_name = os.path.basename(data['filename'] or "unnamed")
                path  = os.path.join(DOWNLOAD_DIR, safe_name)
                with open(path, "wb") as f:
                    f.write(data['data'])
                print(f"Received file from {peer_name or '?'}: {path} ({data['size']} bytes)")
                
            elif frame_type == "BYE":
                print("\nCounterpart have closed.")
                
                break;
        except Exception as e:
            print(f"\n Error: {e}")
            break
    with conn_lock:
        if peer_name and connected_peers.get(peer_name) is sock:
            del connected_peers[peer_name]
    try:
        sock.close()
    except OSError:
        pass

def tcp_acceptor(server_socket):
    while True:
        try:
           conn, addr = server_socket.accept()
           threading.Thread(target=tcp_receiver_thread, args=(conn, ), daemon=True).start()
        except Exception as e:
            print(f"\nError Acceptor Threading or Server closed: {e}")
            break
