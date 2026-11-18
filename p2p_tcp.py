import socket
import threading
import time
import os
from typing import Tuple, Dict, Any, Optional
import os
connected_peers = {}
DOWNLOAD_DIR = "download"
conn_lock = threading.Lock()

MAX_FILE_SIZE = 50 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
MAX_CHUNK_RECV = 256 * 1024

_send_locks = {}
_send_locks_guard = threading.Lock()

def _get_send_lock(sock):
    with _send_locks_guard:
        lock = _send_locks.get(sock)
        if lock is None:
            lock = _send_locks[sock] = threading.Lock()
        return lock

def _drop_send_lock(sock):
    with _send_locks_guard:
        _send_locks.pop(sock, None)

def _send(sock, data: bytes):
    with _get_send_lock(sock):
        sock.sendall(data)

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
    _send(sock, header)

def send_msg(sock, text):
    payload_bytes = text.encode('utf-8')
    length = len(payload_bytes)
    header = f"MSG|{length}|".encode('utf-8')
    _send(sock, header + payload_bytes)
    
def send_bye(sock):
    _send(sock, b"BYE|")

def send_file_start(sock, tid, filename, size):
    filename = filename.replace("|", "_")
    _send(sock, f"FSTART|{tid}|{filename}|{size}|".encode('utf-8'))
    
def send_file_chunk(sock, tid, chunk: bytes):
    _send(sock, f"DATA|{tid}|{len(chunk)}|".encode('utf-8') + chunk)
    
def send_file_end(sock, tid):
    _send(sock, f"FEND|{tid}|".encode('utf-8'))

def send_file_abort(sock, tid):
    _send(sock, f"FABORT|{tid}|".encode('utf-8'))
    
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
    _drop_send_lock(sock)
    
def _field(sock):
    raw = recv_until_delimeter(sock, b'|')
    return None if raw is None else raw.decode('utf-8')
    
def recv_frame(sock):
    frame_type_bytes = recv_until_delimeter(sock, b'|')
    if not frame_type_bytes:
        return None
    
    frame_type = frame_type_bytes.decode('utf-8').strip()
    
    if frame_type == "HI":
        name_bytes = recv_until_delimeter(sock, b'|')
        port_bytes = recv_until_delimeter(sock, b'|')
        if not name_bytes or not port_bytes:
            return None
        return "HI", {
            "name": name_bytes.decode('utf-8'),
            "tcp_port": int(port_bytes.decode('utf-8')),
        }
    
    elif frame_type == "MSG":
        length_bytes = recv_until_delimeter(sock, b'|')
        if not length_bytes:
            return None
        length = int(length_bytes.decode('utf-8'))
        payload = recv_exact(sock, length)
        if payload is None:
            return None
        return "MSG", {
            "text": payload.decode('utf-8')}
    
    if frame_type == "FSTART":
        tid, name, size = _field(sock), _field(sock), _field(sock)
        if None in (tid, name, size):
            return None
        return "FSTART", {"tid": tid, "filename": name, "size": int(size)}

    if frame_type == "FDATA":
        tid, length = _field(sock), _field(sock)
        if tid is None or length is None:
            return None
        length = int(length)
        if length < 0 or length > MAX_CHUNK_RECV:
            raise ValueError(f"Invalid chunk length: {length}")
        data = recv_exact(sock, length)
        if data is None:
            return None
        return "FDATA", {"tid": tid, "data": data}

    if frame_type in ("FEND", "FABORT"):
        tid = _field(sock)
        if tid is None:
            return None
        return frame_type, {"tid": tid}
    
    elif frame_type == "BYE":
        return "BYE", {}
    else:
        raise ValueError(f"Unable to recognize frame type: {frame_type}!")

def _unique_path(filename):
    safe = os.path.basename(filename or "") or "unnamed"
    path = os.path.join(DOWNLOAD_DIR, safe)
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(path):
        path = f"{base} ({n}){ext}"
        n += 1
    return path

def _discard(entry):
    if entry.get("f"):
        try:
            entry["f"].close()
        except OSError:
            pass
        try:
            os.remove(entry["path"])
        except OSError:
            pass
        entry["f"] = None

def tcp_receiver_thread(sock, peer_name=None):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    incoming = {}
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
               
            elif frame_type == "FSTART":
                save_path = _unique_path(data["filename"])
                try:
                    f_out = open(save_path, "wb")
                    incoming[data["tid"]] = {
                        "f": f_out,
                        "path": save_path,
                        "size": data["size"],
                        "got": 0
                    }
                    print(f"\r[*] Receiving file '{data['filename']}' ({data['size']} bytes) from {peer_name or '?'}...")
                except OSError as e:
                    print(f"\r[!] Cannot save file: {e}")
            
            elif frame_type == "FDATA":
                entry = incoming.get(data["tid"])
                if entry is None or entry["f"] is None:
                    continue            # file bị từ chối / đã huỷ: bỏ qua dữ liệu
                entry["got"] += len(data["data"])
                if entry["got"] > entry["size"]:
                    print("[!] Received more data than declared, discarding file.")
                    _discard(entry)
                    continue
                entry["f"].write(data["data"])

            elif frame_type == "FEND":
                entry = incoming.pop(data["tid"], None)
                if entry and entry["f"]:
                    entry["f"].close()
                    if entry["got"] == entry["size"]:
                        print(f"Received file from {peer_name or '?'}: {entry['path']} ({entry['size']} bytes)")
                    else:
                        entry["f"] = open(entry["path"], "rb")  # để _discard đóng + xoá
                        print("[!] Incomplete file, discarded.")
                        _discard(entry)

            elif frame_type == "FABORT":
                entry = incoming.pop(data["tid"], None)
                if entry:
                    _discard(entry)
                    print(f"[!] {peer_name or '?'} cancelled a file transfer.")
                
            elif frame_type == "BYE":
                print("\nCounterpart have closed.")
                break
        except Exception as e:
            print(f"\n Error: {e}")
            break
    
    for entry in incoming.values():
        _discard(entry)
    
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
