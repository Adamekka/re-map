import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb, _encode_packet


def _fake_server(sock: socket.socket):
    conn, _ = sock.accept()
    with conn:
        buf = b""
        while True:
            try:
                data = conn.recv(4096)
            except ConnectionResetError:
                # Closing a client with unread ACKs can reset TCP during test teardown.
                return
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


class OneByteSocket(socket.socket):
    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        # Force TCP fragmentation, including the two checksum digits.
        return super().recv(min(bufsize, 1), flags)


@pytest.fixture
def packet_pair():
    raw_client, server = socket.socketpair()
    client = OneByteSocket(fileno=raw_client.detach())
    gdb = DuckStationGdb()
    # A connected socket is the smallest test seam for protocol-level replies.
    gdb._sock = client
    try:
        yield gdb, server
    finally:
        gdb.close()
        server.close()


@pytest.mark.parametrize("stop", [b"S05", b"T02watch:80000000;"])
def test_pause_notification_does_not_shift_memory_replies(packet_pair, stop, caplog):
    gdb, server = packet_pair
    server.sendall(
        b"+"
        + _encode_packet(stop)
        + _encode_packet(b"11" * 32)
        + _encode_packet(b"22" * 32)
    )
    with caplog.at_level("INFO"):
        first = gdb.read_memory(0x8004484C, 32)
    second = gdb.read_memory(0x80045F28, 32)
    assert first.ok and first.data == bytes([0x11]) * 32
    assert second.ok and second.data == bytes([0x22]) * 32
    assert "GDB stop notification during memory read" in caplog.text


def test_multiple_stop_notifications_and_continue_preserve_packets(packet_pair):
    gdb, server = packet_pair
    server.sendall(
        _encode_packet(b"S05") + _encode_packet(b"T05") + _encode_packet(b"aabb")
    )
    assert gdb.resume() == ""
    result = gdb.read_memory(0x80000000, 2)
    assert result.ok and result.data == bytes.fromhex("aabb")


def test_interrupt_consumes_complete_stop_reply(packet_pair):
    gdb, server = packet_pair
    server.sendall(_encode_packet(b"S02"))
    assert gdb.interrupt() == ""
    server.sendall(_encode_packet(b"1234"))
    result = gdb.read_memory(0x80000000, 2)
    assert result.ok and result.data == bytes.fromhex("1234")


def test_interrupt_already_paused_queries_stop_reason(packet_pair):
    gdb, server = packet_pair

    def respond():
        command = bytearray()
        expected = b"\x03" + _encode_packet(b"?")
        while len(command) < len(expected):
            command.extend(server.recv(len(expected) - len(command)))
        assert command == expected
        # A paused server replies only to '?' and emits no new interrupt stop.
        server.sendall(b"+" + _encode_packet(b"S02"))

    responder = threading.Thread(target=respond, daemon=True)
    responder.start()
    assert gdb.interrupt() == ""
    responder.join(timeout=1.0)
    assert not responder.is_alive()
    server.sendall(_encode_packet(b"1234"))
    result = gdb.read_memory(0x80000000, 2)
    assert result.ok and result.data == bytes.fromhex("1234")


def test_interrupt_query_reply_does_not_shift_next_memory_read(packet_pair):
    gdb, server = packet_pair
    server.sendall(_encode_packet(b"S02") + b"+" + _encode_packet(b"S02"))
    assert gdb.interrupt() == ""
    server.sendall(_encode_packet(b"1234"))
    result = gdb.read_memory(0x80000000, 2)
    assert result.ok and result.data == bytes.fromhex("1234")


@pytest.mark.parametrize(
    "reply,reason",
    [
        (b"$1122#00", "checksum mismatch"),
        (b"$11#62", "short reply"),
        (b"$zzzz#e8", "non-hex reply"),
    ],
)
def test_invalid_reply_closes_stream_before_next_request(packet_pair, reply, reason):
    gdb, server = packet_pair
    server.sendall(reply)
    result = gdb.read_memory(0x80000000, 2)
    assert not result.ok and reason in result.error
    next_read = gdb.read_memory(0x80000004, 2)
    assert not next_read.ok and next_read.error == "not connected"


def test_timed_out_request_cannot_leave_a_reply_for_next_read(packet_pair):
    gdb, _server = packet_pair
    result = gdb.read_memory(0x80000000, 2)
    assert not result.ok and "timed out" in result.error
    next_read = gdb.read_memory(0x80000004, 2)
    assert not next_read.ok and next_read.error == "not connected"


def test_gdb_error_response_keeps_aligned_connection(packet_pair):
    gdb, server = packet_pair
    server.sendall(_encode_packet(b"E01") + _encode_packet(b"1234"))
    result = gdb.read_memory(0x80000000, 2)
    assert not result.ok and "gdb error" in result.error
    next_read = gdb.read_memory(0x80000004, 2)
    assert next_read.ok and next_read.data == bytes.fromhex("1234")
