# ArUco Marker Experiment - Jetson

Jetson-side code for the marker and IMU robot prototype.

## Contents

- `navigation.py` - marker-driven route follower and heading controller.
- `sensor_server.py` - receives phone camera/IMU data.
- `stream_viewer.py` - camera/IMU stream test utility.
- `motor_driver.py` - Jetson motor and steering control.
- `protocol.py` - shared message parsing helpers.
- `config.json` - gains, GPIO pins, network port, and gyro settings.
- `route.json` - ordered marker route definition.

## Basic Run

```bash
python3 stream_viewer.py
python3 navigation.py
python3 navigation.py --gpio
```

Keep the wheels lifted during first GPIO tests.
