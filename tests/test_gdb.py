import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import emulator.duckstation_gdb as gdb_module
from emulator.duckstation_gdb import (
    DebugFailure,
    DuckStationGdb,
    NoStop,
    SignalStop,
    WriteWatchStop,
    _encode_packet,
)


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


@pytest.mark.parametrize("operation", ["memory", "interrupt"])
def test_cancelled_exchange_closes_the_partially_consumed_stream(
    monkeypatch, packet_pair, operation
):
    gdb, _ = packet_pair

    def cancelled(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(gdb_module, "_read_packet", cancelled)
    with pytest.raises(KeyboardInterrupt):
        if operation == "memory":
            gdb.read_memory(0x80000000, 1)
        else:
            gdb.interrupt()
    assert not gdb.connected


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


def test_watchpoint_commands_preserve_stops_and_register_reply_alignment(packet_pair):
    gdb, server = packet_pair
    server.sendall(
        _encode_packet(b"S02")
        + _encode_packet(b"OK")
        + _encode_packet(b"T05watch:800cf68e;")
        + _encode_packet(b"245c0280")
        + _encode_packet(b"OK")
    )
    assert gdb.change_write_watchpoint("insert", 0x800CF68E, 1) == ""
    pc = gdb.read_register(37)
    assert pc.ok and int.from_bytes(pc.data, "little") == 0x80025C24
    assert gdb.wait_stop(0) == WriteWatchStop(5, 0x800CF68E)
    assert gdb.change_write_watchpoint("remove", 0x800CF68E, 1) == ""
    commands = server.recv(4096)
    assert _encode_packet(b"Z2,800cf68e,1") in commands
    assert _encode_packet(b"p25") in commands
    assert _encode_packet(b"z2,800cf68e,1") in commands


def test_memory_read_does_not_lose_a_write_watchpoint(packet_pair):
    gdb, server = packet_pair
    server.sendall(_encode_packet(b"T05watch:a00cf68e;") + _encode_packet(b"1234"))
    result = gdb.read_memory(0x80000000, 2)
    assert result.ok and result.data == bytes.fromhex("1234")
    assert gdb.wait_stop(0) == WriteWatchStop(5, 0xA00CF68E)


def test_idle_stop_wait_drains_acks_without_closing_connection(packet_pair):
    gdb, server = packet_pair
    server.sendall(b"++")
    assert isinstance(gdb.wait_stop(0), NoStop)
    assert gdb.connected
    server.sendall(_encode_packet(b"T05watch:800cf68e;"))
    assert gdb.wait_stop(0) == WriteWatchStop(5, 0x800CF68E)


@pytest.mark.parametrize(
    "reply",
    [
        b"$T05watch:garbage;#00",
        _encode_packet(b"OK"),
        _encode_packet(b"T05watch:123456789;"),
    ],
)
def test_invalid_stop_closes_stream(packet_pair, reply):
    gdb, server = packet_pair
    server.sendall(reply)
    assert isinstance(gdb.wait_stop(0), DebugFailure)
    assert not gdb.connected


def test_plain_stop_and_single_step_are_explicit(packet_pair):
    gdb, server = packet_pair
    server.sendall(_encode_packet(b"S02") + b"+" + _encode_packet(b"S05"))
    assert gdb.wait_stop(0) == SignalStop(2)
    assert gdb.single_step() == ""
    assert _encode_packet(b"s") in server.recv(4096)


@pytest.mark.parametrize("reply", [b"", b"E01", b"not-ok"])
def test_watchpoint_rejection_is_not_success(packet_pair, reply):
    gdb, server = packet_pair
    server.sendall(_encode_packet(reply))
    assert gdb.change_write_watchpoint("insert", 0x800CF68E, 1)
    assert gdb.connected == (reply != b"not-ok")


@pytest.mark.parametrize("reply", [b"xxffffff", b"1234", b"112233gg"])
def test_invalid_register_value_closes_stream(packet_pair, reply):
    gdb, server = packet_pair
    server.sendall(_encode_packet(reply))
    assert not gdb.read_register(37).ok
    assert not gdb.connected


def test_unexpected_step_watchpoint_is_retained(packet_pair):
    gdb, server = packet_pair
    server.sendall(_encode_packet(b"T05watch:800cf68e;"))
    assert gdb.single_step()
    assert gdb.wait_stop(0) == WriteWatchStop(5, 0x800CF68E)
