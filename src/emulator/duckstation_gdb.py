"""Minimal GDB remote client for DuckStation RAM reads.

Only implements what the tracker needs: connect, read memory, close.
All reads return an explicit result, never a silent default.
Address space must be a PS1 virtual address such as 0x80000000.
See docs/research.md RE1-EMU-001 for access and RE1-EMU-007 for reply handling.
"""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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


def _is_stop_reply(payload: bytes) -> bool:
    return (
        len(payload) >= 3
        and payload[:1] in (b"S", b"T")
        and all(c in b"0123456789abcdefABCDEF" for c in payload[1:3])
        and (payload[:1] == b"T" or len(payload) == 3)
    )


def _read_packet(sock: socket.socket, deadline: float) -> bytes:
    def receive(width: int) -> bytes:
        received = bytearray()
        while len(received) < width:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("timed out waiting for GDB reply")
            sock.settimeout(remaining)
            chunk = sock.recv(width - len(received))
            if not chunk:
                raise ConnectionError("gdb server closed connection")
            received.extend(chunk)
        return bytes(received)

    buf = bytearray()
    while True:
        chunk = receive(1)
        if chunk == b"$":
            break
        if chunk == b"+":
            continue
        if chunk == b"-":
            raise ConnectionError("gdb server rejected command checksum")
        raise ConnectionError(f"unexpected byte before GDB packet: {chunk!r}")
    while True:
        chunk = receive(1)
        if chunk == b"#":
            break
        # DuckStation's declared packet limit bounds malformed or unterminated replies.
        if len(buf) >= 16384:
            raise ConnectionError("gdb reply exceeds packet limit")
        buf.extend(chunk)
    # TCP may split even the two checksum digits into separate reads.
    csum = receive(2)
    payload = bytes(buf)
    if csum.lower() != _checksum(payload):
        raise ConnectionError("gdb reply checksum mismatch")
    sock.sendall(b"+")
    return payload


class DuckStationGdb:
    """TCP GDB client. Use as context manager or call close explicitly."""

    def __init__(self, host: str = "127.0.0.1", port: int = 2345) -> None:
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self) -> str:
        """Connect to the GDB server. Returns empty string on success, else reason."""
        try:
            sock = socket.create_connection((self._host, self._port), timeout=2.0)
        except OSError as exc:
            return f"connect failed: {exc}"
        self._sock = sock
        # Leave initial stop notifications for the framed reader; raw drains can split packets.
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

    def resume(self) -> str:
        """Send continue. Game runs again. Empty string on success."""
        if self._sock is None:
            return "not connected"
        try:
            self._sock.sendall(_encode_packet(b"c"))
            # Continue has no data reply; its ACK and later stops belong to the packet reader.
        except OSError as exc:
            self.close()
            return str(exc)
        return ""

    def interrupt(self) -> str:
        """Send 0x03 to pause. Reads are stable afterwards."""
        if self._sock is None:
            return "not connected"
        try:
            # An already paused DuckStation sends no new interrupt notification.
            # Query its stop reason after the interrupt so both states have a reply.
            self._sock.sendall(b"\x03" + _encode_packet(b"?"))
            reply = _read_packet(self._sock, time.monotonic() + 3.0)
            if not _is_stop_reply(reply):
                raise ConnectionError(f"unexpected GDB interrupt reply: {reply[:32]!r}")
        except OSError as exc:
            self.close()
            return str(exc)
        return ""

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
            deadline = time.monotonic() + 2.0
            while True:
                resp = _read_packet(self._sock, deadline)
                if _is_stop_reply(resp):
                    # A pause notification does not finish the outstanding memory request.
                    logger.info("GDB stop notification during memory read: %r", resp)
                    continue
                break
        except (OSError, ConnectionError) as exc:
            # A late reply after failure cannot safely be assigned to a later request.
            self.close()
            return MemRead(ok=False, data=b"", error=str(exc))
        if resp.startswith(b"E"):
            return MemRead(ok=False, data=b"", error=f"gdb error: {resp[:16]!r}")
        if len(resp) != length * 2:
            self.close()
            return MemRead(
                ok=False, data=b"", error=f"short reply: {len(resp) // 2} of {length}"
            )
        try:
            return MemRead(ok=True, data=bytes.fromhex(resp.decode("ascii")))
        except ValueError:
            self.close()
            return MemRead(ok=False, data=b"", error="non-hex reply")

    def read_u8(self, address: int) -> MemRead:
        return self.read_memory(address, 1)

    def read_u16_le(self, address: int) -> MemRead:
        return self.read_memory(address, 2)

    def read_u32_le(self, address: int) -> MemRead:
        return self.read_memory(address, 4)
