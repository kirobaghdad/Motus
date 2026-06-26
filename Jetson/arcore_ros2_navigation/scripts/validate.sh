#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile $(find "$ROOT/ros2_ws/src" -name '*.py' -type f)
python3 - <<'PY' "$ROOT"
import pathlib, struct, sys, xml.etree.ElementTree as ET
import yaml
root = pathlib.Path(sys.argv[1])
assert struct.calcsize('<HHQQB3x7fII4fIII') == 88
for path in root.rglob('*.yaml'):
    yaml.safe_load(path.read_text())
for path in root.rglob('*.xml'):
    ET.parse(path)
code_root = root/'ros2_ws/src'
all_text = '\n'.join(p.read_text(errors='ignore') for p in code_root.rglob('*') if p.is_file())
for forbidden in ('encoder', '/wheel/odom', 'robot_localization', '/odometry/filtered', 'ekf'):
    assert forbidden.lower() not in all_text.lower(), forbidden
car = yaml.safe_load((root/'ros2_ws/src/motus_nav/config/car.yaml').read_text())['car']['ros__parameters']
assert car['motor_pwm_pin'] == 33
assert car['motor_direction_pin'] == 29
assert car['servo_channel'] == 0
assert car['servo_center_angle_deg'] == 72.0
assert car['servo_turn_range_deg'] == 40.0
for launch in (root/'ros2_ws/src/motus_nav/launch').glob('*.launch.py'):
    text = launch.read_text()
    assert "'publish_odom_tf': True" in text
    assert "'odom_topic': '/phone/odom'" in text
print('Source, YAML, XML, protocol, no-encoder, hardware constants, and launch checks passed.')
PY
bash -n "$ROOT"/scripts/*.sh
find "$ROOT" -type d -name __pycache__ -prune -exec rm -rf {} +
echo "Validation complete."
