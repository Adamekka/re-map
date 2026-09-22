import socket
import threading
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb


def _fake_server(sock: socket.socket):
    conn, _ = sock.accept()
    with conn:
        # Drain initial ack.
        conn.settimeout(0.5)
        try:
            conn.recv(16)
        except socket.timeout:
            pass
        buf = b""
        while True:
            data = conn.recv(4096)
            if not data:
                return
            buf += data
            while b"$" in buf and b"#" in buf:
                start = buf.index(b"$")
                end = buf.index(b"#", start)
                if len(buf) < end + 3:
                    break
                payload = buf[start + 1 : end]
                buf = buf[end + 3 :]
                # Only handle mADDR,LEN for 0x80000000 len 4 -> deadbeef.
                if payload.startswith(b"m"):
                    conn.sendall(b"$deadbeef#20")
                    conn.sendall(b"+")
                else:
                    conn.sendall(b"$E01#a6")


def test_read_memory_parses_hex():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    th = threading.Thread(target=_fake_server, args=(srv,), daemon=True)
    th.start()
    gdb = DuckStationGdb(port=port)
    assert gdb.connect() == ""
    res = gdb.read_memory(0x80000000, 4)
    gdb.close()
    srv.close()
    assert res.ok
    assert res.data == bytes.fromhex("deadbeef")


def test_read_memory_rejects_bad_length():
    gdb = DuckStationGdb()
    res = gdb.read_memory(0x80000000, 0)
    assert not res.ok
