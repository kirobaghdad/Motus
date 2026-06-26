# Jetson Code

This folder contains the Jetson-side code only. Android phone apps, desktop-only development code, local virtual environments, generated build folders, logs, and cache files are intentionally excluded.

## Structure

- `aruco_marker_experiment/` - Python prototype for ArUco marker detection, IMU-assisted heading control, routing, and Jetson motor control.
- `manual_control/` - Legacy Jetson manual-control scripts for direct motor, servo, encoder, and camera tests.
- `arcore_ros2_navigation/` - ROS 2 Humble package and Jetson run scripts for the ARCore navigation experiment.
- `arcore_jetson_server/` - Standalone Jetson web/navigation server with map, graph, planner, controller, and hardware integration code.

## Notes

- The ArUco marker PNG/JPEG outputs are not included because they are generated artifacts. Regenerate them from `aruco_marker_experiment/generate_markers.py` if needed.
- The ARCore phone application is developed separately on the desktop side and is not included here.
- ROS 2 build products should be regenerated on the Jetson with the scripts in `arcore_ros2_navigation/scripts/`.
