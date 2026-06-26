# Jetson Code

This folder contains the Jetson-side robot code, experiments, and workspace content. Android apps live separately under the repository-level `Android/` folder.

## Structure

- `aruco_marker_experiment/` - Python prototype for ArUco marker detection, IMU-assisted heading control, routing, and Jetson motor control.
- `manual_control/` - Jetson manual-control scripts for direct motor, servo, encoder, and camera tests.
- `arcore_ros2_navigation/` - ROS 2 Humble package and Jetson run scripts for the ARCore navigation experiment.
- `arcore_jetson_server/` - Standalone Jetson web/navigation server with map, graph, planner, controller, and hardware integration code.
- `self_driving_ws/` - self-driving workspace and related Jetson-side development files.

## Notes

- ROS 2 build products should be regenerated on the Jetson with the scripts in `arcore_ros2_navigation/scripts/`.
