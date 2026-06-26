#!/usr/bin/env python3
import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener


HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Motus Nav</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: #101318;
      color: #eef3f8;
      font-family: Arial, sans-serif;
    }
    main {
      display: grid;
      grid-template-rows: auto 1fr auto;
      height: 100vh;
    }
    header, footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 12px;
      background: #171d25;
      border-color: #2b3441;
    }
    header { border-bottom: 1px solid #2b3441; }
    footer { border-top: 1px solid #2b3441; flex-wrap: wrap; }
    h1 {
      margin: 0;
      font-size: 18px;
      letter-spacing: 0;
    }
    .status {
      color: #9fb0c5;
      font-size: 14px;
      white-space: nowrap;
    }
    .map-wrap {
      position: relative;
      min-height: 0;
      background: #252b34;
      overflow: hidden;
      touch-action: none;
    }
    canvas {
      display: block;
      width: 100%;
      height: 100%;
      cursor: crosshair;
    }
    .tools {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    button {
      height: 40px;
      min-width: 76px;
      border: 1px solid #3d4858;
      border-radius: 6px;
      background: #202734;
      color: #eef3f8;
      font-size: 15px;
      font-weight: 700;
    }
    button.primary { background: #1f6feb; border-color: #2d7bf0; }
    button.danger { background: #9f2424; border-color: #b93232; }
    .hint {
      color: #9fb0c5;
      font-size: 13px;
    }
    @media (max-width: 640px) {
      header, footer { align-items: flex-start; }
      footer { display: grid; }
      .tools { width: 100%; }
      button { flex: 1; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Motus Navigation</h1>
      <div class="status" id="status">connecting</div>
    </header>
    <section class="map-wrap">
      <canvas id="map"></canvas>
    </section>
    <footer>
      <div class="tools">
        <button id="fit">Fit</button>
        <button id="zoomIn">+</button>
        <button id="zoomOut">-</button>
        <button class="primary" id="send">Send Goal</button>
        <button class="danger" id="clear">Clear</button>
      </div>
      <div class="hint">Click to choose goal. Drag before release to set heading.</div>
    </footer>
  </main>
  <script>
    const canvas = document.getElementById("map");
    const ctx = canvas.getContext("2d");
    const statusEl = document.getElementById("status");
    const fitButton = document.getElementById("fit");
    const zoomInButton = document.getElementById("zoomIn");
    const zoomOutButton = document.getElementById("zoomOut");
    const sendButton = document.getElementById("send");
    const clearButton = document.getElementById("clear");

    let map = null;
    let mapImage = null;
    let robot = null;
    let goal = null;
    let dragging = false;
    let dragStart = null;
    let view = {scale: 1, tx: 0, ty: 0};

    function resize() {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      draw();
    }

    function setStatus(text) {
      statusEl.textContent = text;
    }

    function mapYaw() {
      return map ? map.origin_yaw || 0 : 0;
    }

    function worldToGrid(x, y) {
      const dx = x - map.origin_x;
      const dy = y - map.origin_y;
      const c = Math.cos(-mapYaw());
      const s = Math.sin(-mapYaw());
      return {
        gx: (c * dx - s * dy) / map.resolution,
        gy: (s * dx + c * dy) / map.resolution
      };
    }

    function gridToWorld(gx, gy) {
      const mx = gx * map.resolution;
      const my = gy * map.resolution;
      const c = Math.cos(mapYaw());
      const s = Math.sin(mapYaw());
      return {
        x: map.origin_x + c * mx - s * my,
        y: map.origin_y + s * mx + c * my
      };
    }

    function gridToScreen(gx, gy) {
      return {
        x: view.tx + gx * view.scale,
        y: view.ty + (map.height - gy) * view.scale
      };
    }

    function screenToGrid(px, py) {
      return {
        gx: (px - view.tx) / view.scale,
        gy: map.height - (py - view.ty) / view.scale
      };
    }

    function screenPoint(event) {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      return {
        x: (event.clientX - rect.left) * dpr,
        y: (event.clientY - rect.top) * dpr
      };
    }

    function fitMap() {
      if (!map) return;
      const margin = 18 * (window.devicePixelRatio || 1);
      const sx = (canvas.width - margin * 2) / map.width;
      const sy = (canvas.height - margin * 2) / map.height;
      view.scale = Math.max(0.2, Math.min(sx, sy));
      view.tx = (canvas.width - map.width * view.scale) / 2;
      view.ty = (canvas.height - map.height * view.scale) / 2;
      draw();
    }

    function zoom(factor) {
      if (!map) return;
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;
      view.tx = cx - (cx - view.tx) * factor;
      view.ty = cy - (cy - view.ty) * factor;
      view.scale = Math.max(0.2, Math.min(80, view.scale * factor));
      draw();
    }

    function makeMapImage(payload) {
      const imageData = new ImageData(payload.width, payload.height);
      for (let y = 0; y < payload.height; y++) {
        for (let x = 0; x < payload.width; x++) {
          const src = y * payload.width + x;
          const dstY = payload.height - 1 - y;
          const dst = (dstY * payload.width + x) * 4;
          const cell = payload.data[src];
          let v = 127;
          if (cell === 0) v = 238;
          else if (cell >= 65) v = 20;
          imageData.data[dst] = v;
          imageData.data[dst + 1] = v;
          imageData.data[dst + 2] = v;
          imageData.data[dst + 3] = 255;
        }
      }
      const offscreen = document.createElement("canvas");
      offscreen.width = payload.width;
      offscreen.height = payload.height;
      offscreen.getContext("2d").putImageData(imageData, 0, 0);
      return offscreen;
    }

    function drawArrow(x, y, yaw, color, size) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(-yaw);
      ctx.beginPath();
      ctx.moveTo(size, 0);
      ctx.lineTo(-size * 0.65, size * 0.55);
      ctx.lineTo(-size * 0.35, 0);
      ctx.lineTo(-size * 0.65, -size * 0.55);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.strokeStyle = "#101318";
      ctx.lineWidth = 2;
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#252b34";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      if (!map || !mapImage) return;

      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(
        mapImage,
        view.tx,
        view.ty,
        map.width * view.scale,
        map.height * view.scale
      );

      ctx.strokeStyle = "rgba(31,111,235,0.32)";
      ctx.lineWidth = 1;
      const gridStep = Math.max(1, Math.round(0.5 / map.resolution));
      for (let gx = 0; gx <= map.width; gx += gridStep) {
        const p = gridToScreen(gx, 0);
        ctx.beginPath();
        ctx.moveTo(p.x, view.ty);
        ctx.lineTo(p.x, view.ty + map.height * view.scale);
        ctx.stroke();
      }
      for (let gy = 0; gy <= map.height; gy += gridStep) {
        const p = gridToScreen(0, gy);
        ctx.beginPath();
        ctx.moveTo(view.tx, p.y);
        ctx.lineTo(view.tx + map.width * view.scale, p.y);
        ctx.stroke();
      }

      if (goal) {
        const g = worldToGrid(goal.x, goal.y);
        const p = gridToScreen(g.gx, g.gy);
        drawArrow(p.x, p.y, goal.yaw, "#2da44e", 12);
      }

      if (robot) {
        const g = worldToGrid(robot.x, robot.y);
        const p = gridToScreen(g.gx, g.gy);
        drawArrow(p.x, p.y, robot.yaw, "#f78166", 14);
      }
    }

    async function fetchMap() {
      try {
        const response = await fetch("/api/map");
        if (!response.ok) throw new Error("map unavailable");
        const payload = await response.json();
        if (!payload.available) {
          setStatus("waiting for map");
          return;
        }
        const firstMap = !map;
        map = payload;
        mapImage = makeMapImage(payload);
        if (firstMap) fitMap();
        draw();
      } catch (error) {
        setStatus("map offline");
      }
    }

    async function fetchState() {
      try {
        const response = await fetch("/api/state");
        const payload = await response.json();
        robot = payload.robot || null;
        if (payload.goal) goal = payload.goal;
        const parts = [];
        parts.push(map ? `${map.width}x${map.height}` : "no map");
        parts.push(robot ? `x ${robot.x.toFixed(2)} y ${robot.y.toFixed(2)}` : "no pose");
        setStatus(parts.join(" | "));
        draw();
      } catch (error) {
        setStatus("offline");
      }
    }

    async function sendGoal() {
      if (!goal) return;
      try {
        const response = await fetch("/api/goal", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(goal)
        });
        if (!response.ok) throw new Error("goal rejected");
        const payload = await response.json();
        goal = payload.goal;
        setStatus("goal sent");
        draw();
      } catch (error) {
        setStatus("goal failed");
      }
    }

    canvas.addEventListener("pointerdown", event => {
      if (!map) return;
      dragging = true;
      canvas.setPointerCapture(event.pointerId);
      const p = screenPoint(event);
      dragStart = p;
      const g = screenToGrid(p.x, p.y);
      const w = gridToWorld(g.gx, g.gy);
      goal = {x: w.x, y: w.y, yaw: robot ? robot.yaw : 0};
      draw();
    });

    canvas.addEventListener("pointermove", event => {
      if (!dragging || !goal || !map) return;
      const p = screenPoint(event);
      const dx = p.x - dragStart.x;
      const dy = p.y - dragStart.y;
      if (Math.hypot(dx, dy) > 8) {
        goal.yaw = Math.atan2(-dy, dx);
      }
      draw();
    });

    canvas.addEventListener("pointerup", event => {
      if (!dragging) return;
      dragging = false;
      sendGoal();
    });

    canvas.addEventListener("pointercancel", () => { dragging = false; });
    fitButton.addEventListener("click", fitMap);
    zoomInButton.addEventListener("click", () => zoom(1.25));
    zoomOutButton.addEventListener("click", () => zoom(0.8));
    sendButton.addEventListener("click", sendGoal);
    clearButton.addEventListener("click", () => { goal = null; draw(); });
    window.addEventListener("resize", resize);

    resize();
    fetchMap();
    fetchState();
    setInterval(fetchMap, 2000);
    setInterval(fetchState, 250);
  </script>
</body>
</html>
"""


class WebNavHandler(BaseHTTPRequestHandler):
    node = None

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        if self.path == '/':
            self._send_bytes(200, HTML.encode('utf-8'), 'text/html; charset=utf-8')
        elif self.path == '/api/map':
            self._send_json(200, self.node.map_payload())
        elif self.path == '/api/state':
            self._send_json(200, self.node.state_payload())
        else:
            self._send_json(404, {'error': 'not found'})

    def do_POST(self):
        if self.path == '/api/goal':
            payload = self._read_json()
            goal = self.node.publish_goal(payload)
            self._send_json(200, {'goal': goal})
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


class WebNav(Node):
    def __init__(self):
        super().__init__('web_nav')
        self.declare_parameter('host', '0.0.0.0')
        self.declare_parameter('port', 5001)
        self.declare_parameter('map_topic', '/map')
        self.declare_parameter('goal_topic', '/goal_pose')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')

        map_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            OccupancyGrid,
            str(self.get_parameter('map_topic').value),
            self._map_callback,
            map_qos,
        )
        self.goal_pub = self.create_publisher(PoseStamped, str(self.get_parameter('goal_topic').value), 10)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.lock = threading.Lock()
        self.map = None
        self.map_seq = 0
        self.last_goal = None
        self.server = None
        self._start_server()

    def _start_server(self):
        host = str(self.get_parameter('host').value)
        port = int(self.get_parameter('port').value)
        WebNavHandler.node = self
        ThreadingHTTPServer.allow_reuse_address = True
        self.server = ThreadingHTTPServer((host, port), WebNavHandler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.get_logger().info(f'Web nav listening on http://{host}:{port}')

    def _map_callback(self, message):
        with self.lock:
            self.map = message
            self.map_seq += 1

    def map_payload(self):
        with self.lock:
            message = self.map
            seq = self.map_seq
        if message is None:
            return {'available': False}

        origin = message.info.origin
        return {
            'available': True,
            'seq': seq,
            'frame_id': message.header.frame_id,
            'resolution': message.info.resolution,
            'width': message.info.width,
            'height': message.info.height,
            'origin_x': origin.position.x,
            'origin_y': origin.position.y,
            'origin_yaw': yaw_from_quaternion(origin.orientation),
            'data': list(message.data),
        }

    def state_payload(self):
        payload = {'robot': self._robot_pose()}
        with self.lock:
            if self.last_goal is not None:
                payload['goal'] = self.last_goal
        return payload

    def publish_goal(self, payload):
        x = float(payload.get('x', 0.0))
        y = float(payload.get('y', 0.0))
        yaw = float(payload.get('yaw', 0.0))

        message = PoseStamped()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = str(self.get_parameter('map_frame').value)
        message.pose.position.x = x
        message.pose.position.y = y
        message.pose.position.z = 0.0
        message.pose.orientation = quaternion_from_yaw(yaw)
        self.goal_pub.publish(message)

        goal = {'x': x, 'y': y, 'yaw': yaw}
        with self.lock:
            self.last_goal = goal
        self.get_logger().info(f'Published goal: x={x:.2f}, y={y:.2f}, yaw={math.degrees(yaw):.1f} deg')
        return goal

    def _robot_pose(self):
        map_frame = str(self.get_parameter('map_frame').value)
        base_frame = str(self.get_parameter('base_frame').value)
        try:
            transform = self.tf_buffer.lookup_transform(
                map_frame,
                base_frame,
                Time(),
                timeout=Duration(seconds=0.05),
            )
        except TransformException:
            return None
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        return {
            'x': translation.x,
            'y': translation.y,
            'yaw': yaw_from_quaternion(rotation),
        }

    def destroy_node(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        super().destroy_node()


def yaw_from_quaternion(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def quaternion_from_yaw(yaw):
    from geometry_msgs.msg import Quaternion

    q = Quaternion()
    q.z = math.sin(yaw * 0.5)
    q.w = math.cos(yaw * 0.5)
    return q


def main(args=None):
    rclpy.init(args=args)
    node = WebNav()
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
