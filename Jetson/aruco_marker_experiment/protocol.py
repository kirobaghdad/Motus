"""Binary protocol shared by the Android app and Jetson."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import BinaryIO

MAGIC = 0x52425431  # ASCII: RBT1
TYPE_IMAGE = 1
TYPE_ORIENTATION = 2
TYPE_GYRO = 3
TYPE_ACCEL = 4

HEADER = struct.Struct(">IBqI")  # magic, type, timestamp_ns, payload_size
IMAGE_INFO = struct.Struct(">II")  # width, height
FLOAT3 = struct.Struct(">fff")
FLOAT4 = struct.Struct(">ffff")

MAX_PAYLOAD = 4 * 1024 * 1024


@dataclass(frozen=True)
class Packet:
    packet_type: int
    timestamp_ns: int
    payload: bytes


def recv_exact(stream: BinaryIO, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise ConnectionError("Phone disconnected")
        data.extend(chunk)
    return bytes(data)


def read_packet(stream: BinaryIO) -> Packet:
    header = recv_exact(stream, HEADER.size)
    magic, packet_type, timestamp_ns, payload_size = HEADER.unpack(header)
    if magic != MAGIC:
        raise ValueError(f"Bad packet magic: 0x{magic:08X}")
    if payload_size < 0 or payload_size > MAX_PAYLOAD:
        raise ValueError(f"Invalid payload size: {payload_size}")
    return Packet(packet_type, timestamp_ns, recv_exact(stream, payload_size))
