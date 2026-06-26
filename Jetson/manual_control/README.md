# Manual Control - Jetson

Legacy Jetson-side manual control and hardware test scripts copied from `/home/motus/Documents/motus` symlink targets.

## Contents

- `car_control.py` - Flask-based manual driving UI/API with motor, servo, encoder, and watchdog handling.
- `camera_stream.py` - Jetson camera stream utility.
- `mpu_6050.py` - MPU6050/MPU6500 hardware IMU reader over I2C.
- `motor_driver.py` - standalone motor driver helper.
- `servo_motor.py` - standalone servo test/helper.
- `config/` - copied runtime JSON settings from `/home/motus/data/motus`.

## Runtime Note

Some scripts use absolute runtime paths under `/home/motus/data/motus`. The files in `config/` preserve the current Jetson settings for submission/reference.
