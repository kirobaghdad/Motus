"""Receives phone camera and IMU packets over TCP."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from protocol import (
    FLOAT3,
    FLOAT4,
    IMAGE_INFO,
    TYPE_ACCEL,
    TYPE_GYRO,
    TYPE_IMAGE,
    TYPE_ORIENTATION,
    read_packet,
)


@dataclass
class TimedVector:
    timestamp_ns: int
    values: tuple[float, ...]


class SensorServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        frame_flip_code: int | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.frame_flip_code = frame_flip_code
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._connected = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._server_socket: Optional[socket.socket] = None
        self._client_socket: Optional[socket.socket] = None

        self.frame: Optional[np.ndarray] = None
        self.frame_timestamp_ns = 0
        self.orientation: Optional[TimedVector] = None
        self.gyro: Optional[TimedVector] = None
        self.accel: Optional[TimedVector] = None
        self.error: Optional[str] = None

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def wait_for_client(self, timeout: Optional[float] = None) -> bool:
        return self._connected.wait(timeout)

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            if self._client_socket:
                try:
                    self._client_socket.shutdown(socket.SHUT_RDWR)
                    self._client_socket.close()
                except OSError:
                    pass
            if self._server_socket:
                try:
                    self._server_socket.close()
                except OSError:
                    pass
        if self._thread:
            self._thread.join(timeout=1.0)

    def get_frame(self) -> tuple[Optional[np.ndarray], int]:
        with self._lock:
            return (None if self.frame is None else self.frame.copy(), self.frame_timestamp_ns)

    def get_gyro(self) -> Optional[TimedVector]:
        with self._lock:
            return self.gyro

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                self._server_socket = server
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((self.host, self.port))
                server.listen(1)
                print(f"Listening on {self.host}:{self.port}")
                client, address = server.accept()
                with self._lock:
                    self._client_socket = client
                with client:
                    print(f"Phone connected from {address[0]}:{address[1]}")
                    self._connected.set()
                    stream = client.makefile("rb", buffering=1024 * 1024)
                    while not self._stop.is_set():
                        packet = read_packet(stream)
                        self._handle_packet(packet.packet_type, packet.timestamp_ns, packet.payload)
        except Exception as exc:  # Keep the error visible to the controller.
            if not self._stop.is_set():
                self.error = str(exc)
                print(f"Sensor server stopped: {exc}")
        finally:
            self._connected.clear()
            with self._lock:
                self._client_socket = None

    def _handle_packet(self, packet_type: int, timestamp_ns: int, payload: bytes) -> None:
        with self._lock:
            if packet_type == TYPE_IMAGE:
                if len(payload) < IMAGE_INFO.size:
                    return
                width, height = IMAGE_INFO.unpack_from(payload, 0)
                expected = width * height
                image_bytes = payload[IMAGE_INFO.size:]
                if len(image_bytes) != expected:
                    return
                frame = np.frombuffer(image_bytes, dtype=np.uint8).reshape(height, width).copy()
                self.frame = self._apply_frame_flip(frame)
                self.frame_timestamp_ns = timestamp_ns
            elif packet_type == TYPE_ORIENTATION and len(payload) == FLOAT4.size:
                self.orientation = TimedVector(timestamp_ns, FLOAT4.unpack(payload))
            elif packet_type == TYPE_GYRO and len(payload) == FLOAT3.size:
                self.gyro = TimedVector(timestamp_ns, FLOAT3.unpack(payload))
            elif packet_type == TYPE_ACCEL and len(payload) == FLOAT3.size:
                self.accel = TimedVector(timestamp_ns, FLOAT3.unpack(payload))

    def _apply_frame_flip(self, frame: np.ndarray) -> np.ndarray:
        if self.frame_flip_code is None:
            return frame
        if self.frame_flip_code == 0:
            return np.flip(frame, axis=0).copy()
        if self.frame_flip_code == 1:
            return np.flip(frame, axis=1).copy()
        if self.frame_flip_code == -1:
            return np.flip(frame, axis=(0, 1)).copy()
        return frame
