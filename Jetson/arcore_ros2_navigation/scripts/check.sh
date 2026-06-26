#!/usr/bin/env bash
set -e
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/humble/setup.bash 2>/dev/null || true
[[ -f "$ROOT/ros2_ws/install/setup.bash" ]] && source "$ROOT/ros2_ws/install/setup.bash"

echo "=== Hardware libraries ==="
python3 - <<'PY'
for module in ('Jetson.GPIO', 'adafruit_servokit'):
    try:
        __import__(module)
        print(f'{module}: OK')
    except Exception as exc:
        print(f'{module}: ERROR: {exc}')
PY

echo
echo "=== Network ==="
ip -4 -brief address show || true
ss -lntp | grep ':5000' || echo "Port 5000 is not listening yet."

echo
echo "=== Main ROS topics ==="
for topic in /phone/connected /phone/tracking_ok /phone/odom /phone/image /phone/points /map /cmd_vel /cmd_vel_safe; do
  ros2 topic info "$topic" 2>/dev/null || echo "$topic: not available"
done

echo
echo "=== Odometry transform ==="
timeout 5 ros2 run tf2_ros tf2_echo odom base_link 2>/dev/null || true
