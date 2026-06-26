# ARCore ROS 2 Navigation - Jetson

Jetson-side ROS 2 Humble code for the ARCore navigation experiment. The phone-side ARCore app is intentionally not included in this repository folder.

The system uses ARCore pose, camera, calibration, and depth data streamed from the phone as the odometry and perception source for RTAB-Map/Nav2. The encoder path has been removed from this experiment.

## Folder Layout

```text
arcore_ros2_navigation/
├── ros2_ws/src/motus_nav/  ROS 2 package
├── scripts/                Jetson install, build, mapping, navigation, and safety scripts
└── LICENSE
```

## Main Commands On The Jetson

```bash
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/build.sh
./scripts/check.sh
```

Raised-wheel car test:

```bash
./scripts/test_car.sh
```

Mapping:

```bash
./scripts/map.sh
```

Then, in another terminal:

```bash
./scripts/teleop.sh
```

Navigation using the saved RTAB-Map database:

```bash
./scripts/nav.sh
```

Emergency stop:

```bash
./scripts/stop.sh
```

Clear the latched stop:

```bash
./scripts/clear_stop.sh
```

Review `STILL_NEEDED.md` before enabling the real car.
