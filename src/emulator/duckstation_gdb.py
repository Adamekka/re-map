"""Minimal GDB remote client for DuckStation RAM reads.

Only implements what the tracker needs: connect, read memory, close.
All reads return an explicit result, never a silent default.
Address space must be a PS1 virtual address such as 0x80000000.
See docs/research.md RE1-EMU-001, status Candidate.
"""
from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class MemRead:
    ok: bool
    data: bytes
    error: str = ""


def _checksum(payload: bytes) -> bytes:
    # GDB packet checksum is the low byte sum, sent as two hex digits.
    return f"{sum(payload) & 0xFF:02x}".encode("ascii")


def _encode_packet(payload: bytes) -> bytes:
    return b"$" + payload + b"#" + _checksum(payload)


def _read_packet(sock: socket.socket, timeout_s: float = 2.0) -> bytes:
    sock.settimeout(timeout_s)
    buf = bytearray()
    # Wait for start marker.
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("gdb server closed connection")
        if chunk == b"$":
            break
        # Ignore '+'/'-' acks and noise before a packet.
        continue
    # Read until '#' then two checksum chars.
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("gdb server closed mid-packet")
        buf.extend(chunk)
        if chunk == b"#":
            break
    csum = sock.recv(2)
    if len(csum) < 2:
        raise ConnectionError("gdb server sent short checksum")
    # Ack receipt so server keeps serving reads.
    try:
        sock.sendall(b"+")
    except OSError:
        pass
    return bytes(buf[:-1])


class DuckStationGdb:
    """TCP GDB client. Use as context manager or call close explicitly."""

    def __init__(self, host: str = "127.0.0.1", port: int = 2345) -> None:
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None

    def connect(self) -> str:
        """Connect to the GDB server. Returns empty string on success, else reason."""
        try:
            sock = socket.create_connection((self._host, self._port), timeout=2.0)
        except OSError as exc:
            return f"connect failed: {exc}"
        self._sock = sock
        # GDB servers may send an initial stop packet; drain it without blocking long.
        try:
            sock.settimeout(0.2)
            sock.recv(4096)
        except (socket.timeout, OSError):
            pass
        # Ack to put session in a known state.
        try:
            sock.sendall(b"+")
        except OSError as exc:
            self.close()
            return f"ack failed: {exc}"
        return ""

    def close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def __enter__(self) -> "DuckStationGdb":
        err = self.connect()
        if err:
            raise ConnectionError(err)
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def read_memory(self, address: int, length: int) -> MemRead:
        # Keep reads small: DuckStation caps packets at 16384 bytes,
        # so max read per packet is 8192 bytes. Stay well under that.
        if self._sock is None:
            return MemRead(ok=False, data=b"", error="not connected")
        if length <= 0 or length > 4096:
            return MemRead(ok=False, data=b"", error="length must be 1..4096")
        if address < 0 or address > 0xFFFFFFFF:
            return MemRead(ok=False, data=b"", error="address out of range")
        payload = f"m{address:x},{length:x}".encode("ascii")
        try:
            self._sock.sendall(_encode_packet(payload))
            resp = _read_packet(self._sock)
        except (OSError, ConnectionError) as exc:
            return MemRead(ok=False, data=b"", error=str(exc))
        if resp.startswith(b"E"):
            return MemRead(ok=False, data=b"", error=f"gdb error: {resp[:16]!r}")
        if len(resp) != length * 2:
            return MemRead(ok=False, data=b"", error=f"short reply: {len(resp)//2} of {length}")
        try:
            return MemRead(ok=True, data=bytes.fromhex(resp.decode("ascii")))
        except ValueError:
            return MemRead(ok=False, data=b"", error="non-hex reply")

    def read_u8(self, address: int) -> MemRead:
        return self.read_memory(address, 1)

    def read_u16_le(self, address: int) -> MemRead:
        return self.read_memory(address, 2)

    def read_u32_le(self, address: int) -> MemRead:
        return self.read_memory(address, 4)
