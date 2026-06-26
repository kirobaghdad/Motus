"""Send a short fake ARCore route for interface testing without a phone."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time

import websockets


async def run(host: str, port: int) -> None:
    uri = f"ws://{host}:{port}/ws/pose"
    print(f"Connecting to {uri}")

    async with websockets.connect(uri) as socket:
        print(await socket.recv())
        origin_id = int(time.time())
        seq = 0

        for index in range(400):
            seq += 1
            x = min(index * 0.015, 5.5)
            y = 0.15 * math.sin(x * 0.7)
            yaw = 0.10 * math.cos(x * 0.7)
            packet = {
                "type": "pose",
                "seq": seq,
                "time_ms": int(time.time() * 1000),
                "origin_id": origin_id,
                "local_x": x,
                "local_y": y,
                "local_yaw": yaw,
                "tracking": True,
                "reason": "",
            }
            await socket.send(json.dumps(packet))
            await asyncio.sleep(0.05)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    asyncio.run(run(args.host, args.port))
