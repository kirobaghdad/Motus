#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/humble/setup.bash
source "$ROOT/ros2_ws/install/setup.bash"
CONFIG="$(ros2 pkg prefix motus_nav)/share/motus_nav/config/car.yaml"
echo "Raise the wheels before continuing. Ctrl+C stops the node."
exec ros2 run motus_nav car --ros-args --params-file "$CONFIG" -p hardware_enabled:=true
