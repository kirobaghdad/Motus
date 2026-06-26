#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/humble/setup.bash
cd "$ROOT/ros2_ws"
rosdep install --from-paths src --ignore-src -r -y || true
colcon build --symlink-install
printf '\nBuild complete. Source with:\nsource %s/ros2_ws/install/setup.bash\n' "$ROOT"
