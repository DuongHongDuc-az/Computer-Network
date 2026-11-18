import os
import threading
import uuid

from p2p_tcp import (send_file_start, send_file_chunk, send_file_end,
                     send_file_abort, MAX_FILE_SIZE, CHUNK_SIZE)

MAX_CONCURRENT_SENDS = 4                      
_slots = threading.BoundedSemaphore(MAX_CONCURRENT_SENDS)

_active = {}                                 
_active_lock = threading.Lock()

class FileTransfer:
    def __init__(self, sock, path, peer_name):
        self.tid = uuid.uuid4().hex[:8]
        self.sock = sock
        self.path = path
        self.peer_name = peer_name
        self.filename = os.path.basename(path)
        self.size = os.path.getsize(path)
        self.sent = 0
        self.cancel_event = threading.Event()
        self.thread = None

    def cancel(self):
        self.cancel_event.set()


def start_send_file(sock, path, peer_name="", on_progress=None, on_done=None):
    if not os.path.isfile(path):
        raise ValueError(f"File not found: {path}")
    size = os.path.getsize(path)
    if size > MAX_FILE_SIZE:
        raise ValueError(f"File too large ({size} bytes, max {MAX_FILE_SIZE}).")

    tr = FileTransfer(sock, path, peer_name)
    with _active_lock:
        _active[tr.tid] = tr
    tr.thread = threading.Thread(target=_run, args=(tr, on_progress, on_done),
                                 name=f"send-{tr.filename}", daemon=True)
    tr.thread.start()
    return tr


def _run(tr, on_progress, on_done):
    ok, error = False, None
    got_slot = False
    try:
        # Chờ slot (hàng đợi) nhưng vẫn huỷ được khi đang chờ
        while not tr.cancel_event.is_set():
            if _slots.acquire(timeout=0.2):
                got_slot = True
                break
        if not got_slot:
            error = "cancelled"
            return

        send_file_start(tr.sock, tr.tid, tr.filename, tr.size)
        last_pct = -1
        with open(tr.path, "rb") as f:
            while tr.sent < tr.size:
                if tr.cancel_event.is_set():
                    send_file_abort(tr.sock, tr.tid)
                    error = "cancelled"
                    return
                chunk = f.read(min(CHUNK_SIZE, tr.size - tr.sent))
                if not chunk:                       # file bị cắt ngắn khi đang gửi
                    send_file_abort(tr.sock, tr.tid)
                    error = "file changed while sending"
                    return
                send_file_chunk(tr.sock, tr.tid, chunk)
                tr.sent += len(chunk)
                pct = tr.sent * 100 // tr.size if tr.size else 100
                if on_progress and pct // 25 != last_pct // 25:
                    last_pct = pct
                    on_progress(tr, pct)
        send_file_end(tr.sock, tr.tid)
        ok = True
    except OSError as e:
        error = str(e)
        try:
            send_file_abort(tr.sock, tr.tid)
        except OSError:
            pass
    finally:
        if got_slot:
            _slots.release()
        with _active_lock:
            _active.pop(tr.tid, None)
        if on_done:
            on_done(tr, ok, error)


def cancel_all():
    with _active_lock:
        transfers = list(_active.values())
    for tr in transfers:
        tr.cancel()