#!/usr/bin/env python3
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Motus Teleop</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: #101318;
      color: #f4f7fb;
      font-family: Arial, sans-serif;
      text-align: center;
      padding: 20px 12px;
    }
    main {
      max-width: 430px;
      margin: 0 auto;
    }
    h1 {
      margin: 0 0 14px;
      font-size: 28px;
      letter-spacing: 0;
    }
    h2 {
      margin: 0 0 14px;
      font-size: 22px;
    }
    .card {
      background: #171d25;
      border-radius: 20px;
      padding: 18px;
      margin: 14px auto;
    }
    .status {
      min-height: 24px;
      color: #9fb0c5;
      margin-top: 10px;
    }
    .joystick {
      width: 260px;
      height: 260px;
      max-width: calc(100vw - 72px);
      border-radius: 50%;
      background: #222837;
      border: 3px solid #444c60;
      position: relative;
      touch-action: none;
      margin: 20px auto;
    }
    .knob {
      width: 85px;
      height: 85px;
      border-radius: 50%;
      background: #2f80ff;
      position: absolute;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      pointer-events: none;
    }
    .readout {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .speed-config {
      display: grid;
      gap: 8px;
      text-align: left;
    }
    input[type="number"] {
      width: 100%;
      height: 44px;
      border: 1px solid #344050;
      border-radius: 6px;
      padding: 0 12px;
      background: #101318;
      color: #f4f7fb;
      font-size: 20px;
    }
    .tile {
      background: #252b38;
      border-radius: 14px;
      padding: 12px;
    }
    .label {
      color: #aaa;
      font-size: 14px;
      margin-bottom: 6px;
    }
    .value {
      font-size: 24px;
      font-weight: 700;
    }
    button {
      width: min(280px, 100%);
      height: 65px;
      border: 0;
      border-radius: 16px;
      background: #c62828;
      color: white;
      font-size: 22px;
      font-weight: 700;
      touch-action: manipulation;
      margin-top: 8px;
    }
  </style>
</head>
<body>
  <main>
    <h1>Jetson Car</h1>
    <div class="card">
      <h2>Joystick</h2>
      <div class="joystick" id="joystick">
        <div class="knob" id="knob"></div>
      </div>
      <p>
        Command Speed: <span id="cmdSpeed">0</span> |
        Steering: <span id="cmdSteering">0.00</span>
      </p>
    </div>
    <div class="card speed-config">
      <label class="label" for="maxSpeed">Max speed (m/s)</label>
      <input id="maxSpeed" type="number" min="0.01" max="0.12" step="0.01" value="0.10">
    </div>
    <div class="card">
      <div class="readout">
        <div class="tile">
          <div class="label">Speed</div>
          <div class="value" id="speed">0.00</div>
        </div>
        <div class="tile">
          <div class="label">Turn</div>
          <div class="value" id="turn">0.00</div>
        </div>
      </div>
      <button id="stop">STOP</button>
      <div class="status" id="status">idle</div>
    </div>
  </main>
  <script>
    const joystick = document.getElementById("joystick");
    const knob = document.getElementById("knob");
    const statusEl = document.getElementById("status");
    const speedEl = document.getElementById("speed");
    const turnEl = document.getElementById("turn");
    const cmdSpeedEl = document.getElementById("cmdSpeed");
    const cmdSteeringEl = document.getElementById("cmdSteering");
    const maxSpeedEl = document.getElementById("maxSpeed");
    const stopButton = document.getElementById("stop");

    let joystickActive = false;
    let currentSpeed = 0;
    let currentSteering = 0;
    let controlTimer = null;
    let controlBusy = false;
    const deadzone = 0.15;
    const maxCommandSpeed = 100;

    function clamp(v, lo, hi) {
      return Math.max(lo, Math.min(hi, v));
    }

    function setStatus(text) {
      statusEl.textContent = text;
    }

    function updateReadout() {
      speedEl.textContent = (currentSpeed / maxCommandSpeed).toFixed(2);
      turnEl.textContent = currentSteering.toFixed(2);
      cmdSpeedEl.textContent = currentSpeed.toFixed(0);
      cmdSteeringEl.textContent = currentSteering.toFixed(2);
    }

    function maxSpeed() {
      const value = Number(maxSpeedEl.value);
      if (!Number.isFinite(value)) return 0.10;
      return clamp(value, 0.01, 0.12);
    }

    function moveJoystick(clientX, clientY) {
      const rect = joystick.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const maxRadius = rect.width / 2 - knob.offsetWidth / 2;
      let dx = clientX - centerX;
      let dy = clientY - centerY;
      const distance = Math.hypot(dx, dy);
      if (distance > maxRadius) {
        dx = dx / distance * maxRadius;
        dy = dy / distance * maxRadius;
      }

      knob.style.transform =
        `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;

      let x = dx / maxRadius;
      let y = dy / maxRadius;
      if (Math.abs(x) < deadzone) x = 0;
      if (Math.abs(y) < deadzone) y = 0;

      currentSteering = clamp(x, -1, 1);
      let throttle = -y;
      if (Math.abs(throttle) < deadzone) throttle = 0;
      currentSpeed = throttle * maxCommandSpeed;
      updateReadout();
    }

    async function sendControl() {
      if (controlBusy) return;
      controlBusy = true;
      try {
        await fetch("/control", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            speed_percent: currentSpeed,
            steering: currentSteering,
            max_speed_mps: maxSpeed()
          })
        });
        setStatus("active");
      } catch (error) {
        setStatus("offline");
      } finally {
        controlBusy = false;
      }
    }

    function startControlLoop() {
      if (controlTimer !== null) return;
      controlTimer = setInterval(sendControl, 120);
    }

    function stopControlLoop() {
      if (controlTimer === null) return;
      clearInterval(controlTimer);
      controlTimer = null;
    }

    async function stop() {
      joystickActive = false;
      stopControlLoop();
      currentSpeed = 0;
      currentSteering = 0;
      updateReadout();
      knob.style.transform = "translate(-50%, -50%)";
      try {
        await fetch("/stop", {method: "POST", keepalive: true});
        setStatus("stopped");
      } catch (error) {
        setStatus("offline");
      }
    }

    joystick.addEventListener("pointerdown", event => {
      joystickActive = true;
      joystick.setPointerCapture(event.pointerId);
      moveJoystick(event.clientX, event.clientY);
      sendControl();
      startControlLoop();
    });

    joystick.addEventListener("pointermove", event => {
      if (!joystickActive) return;
      moveJoystick(event.clientX, event.clientY);
    });

    joystick.addEventListener("pointerup", stop);
    joystick.addEventListener("pointercancel", stop);
    stopButton.addEventListener("click", stop);
    updateReadout();
  </script>
</body>
</html>
"""


class TeleopHandler(BaseHTTPRequestHandler):
    node = None

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        if self.path == '/':
            self._send_bytes(200, HTML.encode('utf-8'), 'text/html; charset=utf-8')
        elif self.path == '/status':
            self._send_json(200, self.node.status())
        else:
            self._send_json(404, {'error': 'not found'})

    def do_POST(self):
        if self.path == '/control':
            payload = self._read_json()
            self.node.set_command(
                float(payload.get('speed_percent', payload.get('speed', 0.0))),
                float(payload.get('steering', payload.get('turn', 0.0))),
                float(payload.get('max_speed_mps', self.node.command_max_linear)),
            )
            self._send_json(200, self.node.status())
        elif self.path == '/stop':
            self.node.stop_command()
            self._send_json(200, self.node.status())
        else:
            self._send_json(404, {'error': 'not found'})

    def _read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode('utf-8'))

    def _send_json(self, status, payload):
        self._send_bytes(status, json.dumps(payload).encode('utf-8'), 'application/json')

    def _send_bytes(self, status, data, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)


class WebTeleop(Node):
    def __init__(self):
        super().__init__('web_teleop')
        self.declare_parameter('host', '0.0.0.0')
        self.declare_parameter('port', 5000)
        self.declare_parameter('output_topic', '/cmd_vel')
        self.declare_parameter('max_linear_mps', 0.12)
        self.declare_parameter('default_command_max_linear_mps', 0.10)
        self.declare_parameter('command_timeout_sec', 0.35)

        self.max_linear = float(self.get_parameter('max_linear_mps').value)
        self.timeout = float(self.get_parameter('command_timeout_sec').value)
        self.publisher = self.create_publisher(Twist, str(self.get_parameter('output_topic').value), 10)

        self.lock = threading.Lock()
        self.normalized_speed = 0.0
        self.normalized_turn = 0.0
        self.command_max_linear = self._clamp(
            float(self.get_parameter('default_command_max_linear_mps').value), 0.01, self.max_linear
        )
        self.last_command_time = 0.0
        self.server = None

        self.timer = self.create_timer(0.05, self._publish_command)
        self._start_server()

    def _start_server(self):
        host = str(self.get_parameter('host').value)
        port = int(self.get_parameter('port').value)
        TeleopHandler.node = self
        ThreadingHTTPServer.allow_reuse_address = True
        self.server = ThreadingHTTPServer((host, port), TeleopHandler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.get_logger().info(f'Web teleop listening on http://{host}:{port}')

    @staticmethod
    def _clamp(value, low, high):
        return max(low, min(high, value))

    def set_command(self, speed, turn, max_speed_mps):
        with self.lock:
            if abs(speed) > 1.0:
                speed = speed / 100.0
            self.normalized_speed = self._clamp(speed, -1.0, 1.0)
            self.normalized_turn = self._clamp(turn, -1.0, 1.0)
            self.command_max_linear = self._clamp(max_speed_mps, 0.01, self.max_linear)
            self.last_command_time = time.monotonic()

    def stop_command(self):
        with self.lock:
            self.normalized_speed = 0.0
            self.normalized_turn = 0.0
            self.last_command_time = 0.0
        self.publisher.publish(Twist())

    def status(self):
        with self.lock:
            return {
                'speed': self.normalized_speed,
                'turn': self.normalized_turn,
                'command_max_linear_mps': self.command_max_linear,
                'max_linear_mps': self.max_linear,
            }

    def _publish_command(self):
        with self.lock:
            age = time.monotonic() - self.last_command_time
            speed = self.normalized_speed if age <= self.timeout else 0.0
            turn = self.normalized_turn if age <= self.timeout else 0.0
            max_linear = self.command_max_linear

        message = Twist()
        message.linear.x = speed * max_linear
        message.angular.z = turn
        self.publisher.publish(message)

    def destroy_node(self):
        self.stop_command()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = WebTeleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
