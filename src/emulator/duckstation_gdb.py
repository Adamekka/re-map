"""GDB remote client for DuckStation RAM reads and isolated debug captures.

All reads return an explicit result, never a silent default.
Address space must be a PS1 virtual address such as 0x80000000.
See docs/research.md RE1-EMU-001 for access, RE1-EMU-007 for reply handling,
and RE1-EMU-008 for write watchpoints and single stepping.
"""

from __future__ import annotations

import logging
import math
import re
import select
import socket
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemRead:
    ok: bool
    data: bytes
    error: str = ""


@dataclass(frozen=True)
class SignalStop:
    signal: int


@dataclass(frozen=True)
class WriteWatchStop:
    signal: int
    address: int


@dataclass(frozen=True)
class NoStop:
    """No stop packet arrived within the requested wait."""


@dataclass(frozen=True)
class DebugFailure:
    error: str


def _decode_stop(payload: bytes) -> SignalStop | WriteWatchStop:
    assert _is_stop_reply(payload), "validated stop reply"
    signal = int(payload[1:3], 16)
    if payload.startswith(b"T") and b"watch:" in payload:
        match = re.fullmatch(rb"T[0-9a-fA-F]{2}watch:([0-9a-fA-F]{1,8});", payload)
        if match is None:
            raise ValueError("malformed GDB write-watchpoint stop")
        return WriteWatchStop(signal, int(match[1], 16))
    return SignalStop(signal)


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
        self._watch_stops: deque[WriteWatchStop] = deque()

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
        self._watch_stops.clear()
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
            stop = _decode_stop(reply)
            if isinstance(stop, WriteWatchStop):
                self._watch_stops.append(stop)
        except (OSError, ValueError) as exc:
            self.close()
            return str(exc)
        except KeyboardInterrupt:
            # Cancellation may split a frame; disconnect releases owned watches.
            self.close()
            raise
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
                    stop = _decode_stop(resp)
                    if isinstance(stop, WriteWatchStop):
                        self._watch_stops.append(stop)
                    continue
                break
        except (OSError, ValueError) as exc:
            # A late reply after failure cannot safely be assigned to a later request.
            self.close()
            return MemRead(ok=False, data=b"", error=str(exc))
        except KeyboardInterrupt:
            # Do not reuse a partially consumed reply during watchpoint cleanup.
            self.close()
            raise
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

    def _request(self, payload: bytes) -> MemRead:
        if self._sock is None:
            return MemRead(False, b"", "not connected")
        try:
            self._sock.sendall(_encode_packet(payload))
            deadline = time.monotonic() + 2.0
            while True:
                reply = _read_packet(self._sock, deadline)
                if not _is_stop_reply(reply):
                    break
                stop = _decode_stop(reply)
                if isinstance(stop, WriteWatchStop):
                    self._watch_stops.append(stop)
            if not reply:
                return MemRead(False, b"", "GDB command is unsupported")
            if reply.startswith(b"E"):
                return MemRead(False, b"", f"GDB error: {reply[:16]!r}")
            return MemRead(True, reply)
        except (OSError, ValueError) as error:
            self.close()
            return MemRead(False, b"", str(error))
        except KeyboardInterrupt:
            # A cancelled exchange can leave a partial frame. Disconnect also
            # releases this client's watches in the pinned DuckStation server.
            self.close()
            raise

    def change_write_watchpoint(
        self, action: Literal["insert", "remove"], address: int, width: int
    ) -> str:
        assert action in ("insert", "remove"), "explicit watchpoint action"
        if not 1 <= width <= 256 or not 0 <= address <= 0xFFFFFFFF - (width - 1):
            return "write watchpoint requires a valid address and width 1..256"
        prefix = "Z" if action == "insert" else "z"
        result = self._request(f"{prefix}2,{address:x},{width:x}".encode("ascii"))
        if not result.ok:
            return result.error
        if result.data != b"OK":
            self.close()
            return f"unexpected watchpoint reply: {result.data[:32]!r}"
        return ""

    def read_register(self, index: int) -> MemRead:
        if not 0 <= index <= 0xFF:
            return MemRead(False, b"", "register index must fit one byte")
        result = self._request(f"p{index:x}".encode("ascii"))
        if not result.ok:
            return result
        try:
            if len(result.data) != 8:
                raise ValueError("GDB register reply requires four bytes")
            data = bytes.fromhex(result.data.decode("ascii"))
            if len(data) != 4:
                raise ValueError("GDB register reply requires four bytes")
            return MemRead(True, data)
        except ValueError as error:
            self.close()
            return MemRead(False, b"", str(error))

    def wait_stop(
        self, wait_seconds: float
    ) -> SignalStop | WriteWatchStop | NoStop | DebugFailure:
        if not math.isfinite(wait_seconds) or wait_seconds < 0:
            return DebugFailure("stop wait must be finite and nonnegative")
        if self._sock is None:
            return DebugFailure("not connected")
        if self._watch_stops:
            return self._watch_stops.popleft()
        deadline = time.monotonic() + wait_seconds
        try:
            while True:
                ready, _, _ = select.select(
                    [self._sock], [], [], max(0.0, deadline - time.monotonic())
                )
                if not ready:
                    return NoStop()
                first = self._sock.recv(1, socket.MSG_PEEK)
                if not first:
                    raise ConnectionError("gdb server closed connection")
                if first == b"+":
                    # Continue only gets an ACK. It must not turn an idle wait
                    # into a packet timeout or consume part of a later stop.
                    self._sock.recv(1)
                    continue
                reply = _read_packet(self._sock, time.monotonic() + 2.0)
                if not _is_stop_reply(reply):
                    raise ConnectionError(f"unexpected GDB stop reply: {reply[:32]!r}")
                return _decode_stop(reply)
        except (OSError, ValueError) as error:
            self.close()
            return DebugFailure(str(error))
        except KeyboardInterrupt:
            self.close()
            raise

    def single_step(self) -> str:
        if self._sock is None:
            return "not connected"
        try:
            self._sock.sendall(_encode_packet(b"s"))
            reply = _read_packet(self._sock, time.monotonic() + 3.0)
            if not _is_stop_reply(reply):
                raise ConnectionError(f"unexpected GDB step reply: {reply[:32]!r}")
            stop = _decode_stop(reply)
            if isinstance(stop, WriteWatchStop):
                self._watch_stops.append(stop)
                return "single step encountered another write watchpoint"
            if stop.signal != 5:
                return f"single step stopped with signal {stop.signal}"
            return ""
        except (OSError, ValueError) as error:
            self.close()
            return str(error)
        except KeyboardInterrupt:
            self.close()
            raise
