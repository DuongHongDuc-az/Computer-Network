import socket
import threading
import time
from typing import Tuple, Dict, Any, Optional
from prompt_toolkit import prompt
from prompt_toolkit.patch_stdout import patch_stdout
connected_peers = {}
last_seen = {}
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
        if chunk == bytes:
            break
        buffer.extend(chunk)
    return bytes(buffer)

def send_hi(sock, name, tcp_port):
    header = f"HI|{name}|{tcp_port}".encode('utf-8')
    sock.send(header)

def send_msg(sock, text):
    payload_bytes = text.encode('utf-8')
    length = len(payload_bytes)
    header = f"MSG|{length}|".encode('utf-8')
    sock.send(header + payload_bytes)
    
def send_bye(sock):
    sock.send(b"BYE|")

def send_file_frame(sock, filename, file_bytes):
    size = len(file_bytes)
    header = f"FILE|{filename}|{size}|".encode('utf-8')
    sock.send(header + file_bytes)
    
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

def tcp_receiver_thread(sock):
    while True:
        try:
            result = recv_frame(sock)
            if result is None:
                print("UNCONNECTED!")
                break
            
            frame_type, data = result
            
            if frame_type == "HI":
                print(f"\n Successful conected with {data['name']} (Port:{data['tcp_port']})")
            elif frame_type == "MSG":
                print(f"\n[Message]: {data['text']}")
            elif frame_type == "FILE":
                with open(f"dowload/{data['filename']}", "wb") as f:
                    f.write(data['data'])
            elif frame_type == "BYE":
                print("\nCounterpart have closed.")
                break;
        except Exception as e:
            print(f"\n Error: {e}")
            break
    sock.close()

def tcp_acceptor(server_socket):
    while True:
        try:
            conn, addr = server_socket.accept()
            print(f"Success conection with {addr}")

            client_thread = threading.Thread(
                target = tcp_receiver_thread,
                args = (conn, )
            )
            
            client_thread.daemon = True
            client_thread.start()
        except Exception as e:
            print(f"\nError Acceptor Threading or Server closed: {e}")
            break
    
def send_messages():
    current_chat_peer = ""
    
    with patch_stdout():
        while True:
            message = prompt("You: ")
            if message == 'quit':
                break
            
            if message.startswith('/'):
                parts = message.split()
                command = parts[0]
                if command == '/chat':
                    target = parts[1]
                    if target in connected_peers:
                        current_chat_peer = target
                        print(f"Set Connection with {target}")
                    else:
                        print("UNCONECTED")
                elif command == '/list':
                    print("\n--- List Online ---")
                    for name, last_time in list(last_seen.items()):
                        if time.time() - last_time <= 10:
                            print(f"- {name}")
                        else:
                            del connected_peers[name]
                            del last_seen[name]
            else:
                if current_chat_peer != "":
                    sock = connected_peers[current_chat_peer]
                    send_msg(sock, message)
                else:
                    print("You have chosen person to chat. Please use /chat <Username>")

HOST = '127.0.0.1'
PORT = 1025
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen();
print(f"Server is listening at {HOST}:{PORT}")
t1 = threading.Thread(target=tcp_acceptor, args=(server_socket,))
t1.start()
t2 = threading.Thread(target=send_messages)
t2.start()
t2.join()

print("End Connection")
server_socket.close()