#!/usr/bin/env python3
"""Simple ROS 2 motor and steering node for the Motus car.

The phone provides the robot odometry.
"""

import atexit
import fcntl
import json
import math
import threading
import time
from pathlib import Path
from typing import Optional

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_srvs.srv import Trigger


_SERVO_KIT = None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def load_servo_kit():
    global _SERVO_KIT
    if _SERVO_KIT is None:
        from adafruit_servokit import ServoKit
        _SERVO_KIT = ServoKit
    return _SERVO_KIT


class Motor:
    def __init__(self, gpio, pwm_pin: int, direction_pin: int, frequency_hz: int,
                 ramp_step: float, ramp_interval: float):
        self.gpio = gpio
        self.pwm_pin = pwm_pin
        self.direction_pin = direction_pin
        self.ramp_step = float(ramp_step)
        self.ramp_interval = float(ramp_interval)
        self.target = 0.0
        self.output = 0.0
        self.running = True
        self.lock = threading.Lock()

        gpio.setup(direction_pin, gpio.OUT, initial=gpio.LOW)
        gpio.setup(pwm_pin, gpio.OUT, initial=gpio.LOW)
        self.pwm = gpio.PWM(pwm_pin, int(frequency_hz))
        self.pwm.start(0.0)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _write(self, percent: float):
        percent = clamp(percent, -100.0, 100.0)
        if percent > 0.0:
            self.gpio.output(self.direction_pin, self.gpio.LOW)
            self.pwm.ChangeDutyCycle(percent)
        elif percent < 0.0:
            self.gpio.output(self.direction_pin, self.gpio.HIGH)
            self.pwm.ChangeDutyCycle(abs(percent))
        else:
            self.pwm.ChangeDutyCycle(0.0)
            self.gpio.output(self.direction_pin, self.gpio.LOW)

    def _run(self):
        while self.running:
            with self.lock:
                target = self.target
                current = self.output

                # Always ramp to zero before reversing direction.
                if current and target and (current > 0.0) != (target > 0.0):
                    next_value = max(0.0, current - self.ramp_step) if current > 0.0 else min(0.0, current + self.ramp_step)
                else:
                    difference = target - current
                    if abs(difference) <= self.ramp_step:
                        next_value = target
                    elif difference > 0.0:
                        next_value = current + self.ramp_step
                    else:
                        next_value = current - self.ramp_step

                self.output = next_value
                self._write(next_value)
            time.sleep(self.ramp_interval)

    def set(self, percent: float):
        with self.lock:
            self.target = clamp(percent, -100.0, 100.0)

    def stop(self):
        with self.lock:
            self.target = 0.0
            self.output = 0.0
            self._write(0.0)

    def close(self):
        self.running = False
        self.stop()
        if self.thread.is_alive():
            self.thread.join(timeout=0.25)
        self.pwm.stop()


class Steering:
    def __init__(self, address: int, channel: int, center_deg: float,
                 range_deg: float, min_pulse_us: int, max_pulse_us: int):
        self.channel = int(channel)
        self.lock = threading.Lock()
        self.kit = load_servo_kit()(channels=16, address=int(address))
        self.kit.servo[self.channel].set_pulse_width_range(int(min_pulse_us), int(max_pulse_us))
        self.center_deg = clamp(float(center_deg), 0.0, 180.0)
        self.range_deg = clamp(float(range_deg), 0.0, 80.0)
        self.min_deg = max(0.0, self.center_deg - self.range_deg)
        self.max_deg = min(180.0, self.center_deg + self.range_deg)
        self.center()

    def set(self, normalized: float):
        normalized = clamp(normalized, -1.0, 1.0)
        angle = clamp(self.center_deg + normalized * self.range_deg, self.min_deg, self.max_deg)
        with self.lock:
            self.kit.servo[self.channel].angle = angle

    def center(self):
        self.set(0.0)


class CarNode(Node):
    def __init__(self):
        super().__init__('car')
        self._declare_parameters()

        self.input_topic = str(self.get_parameter('input_topic').value)
        self.hardware_enabled = bool(self.get_parameter('hardware_enabled').value)
        self.wheelbase = max(0.01, float(self.get_parameter('wheelbase_m').value))
        self.max_steer = max(0.01, float(self.get_parameter('max_steering_angle_rad').value))
        self.max_forward = max(0.01, float(self.get_parameter('max_forward_speed_mps').value))
        self.max_reverse = max(0.01, float(self.get_parameter('max_reverse_speed_mps').value))
        self.max_pwm = clamp(float(self.get_parameter('max_pwm_percent').value), 1.0, 100.0)
        self.min_pwm = clamp(float(self.get_parameter('minimum_drive_pwm_percent').value), 0.0, self.max_pwm)
        self.motor_sign = 1.0 if float(self.get_parameter('motor_sign').value) >= 0.0 else -1.0
        self.steering_sign = 1.0 if float(self.get_parameter('steering_sign').value) >= 0.0 else -1.0
        self.angular_input_mode = str(self.get_parameter('angular_input_mode').value)
        self.allow_reverse = bool(self.get_parameter('allow_reverse').value)
        self.command_timeout = max(0.05, float(self.get_parameter('command_timeout_sec').value))
        self.speed_deadband = max(0.0, float(self.get_parameter('speed_deadband_mps').value))

        self.gpio = None
        self.motor: Optional[Motor] = None
        self.steering: Optional[Steering] = None
        self.lock_file = None
        self.cleaned = False
        self.emergency_latched = False
        self.last_command_time = 0.0
        self.last_command_log_time = 0.0

        self._start_hardware()
        self.create_subscription(Twist, self.input_topic, self._on_command, 10)
        self.create_service(Trigger, '/car/stop', self._stop_service)
        self.create_service(Trigger, '/car/clear_stop', self._clear_stop_service)
        self.create_timer(0.05, self._watchdog)
        atexit.register(self.close)

        if self.hardware_enabled:
            self.get_logger().warning('REAL CAR ENABLED. Raise the wheels for the first test.')
        else:
            self.get_logger().warning('Hardware disabled. Commands are calculated but GPIO is not driven.')

    def _declare_parameters(self):
        defaults = {
            'input_topic': '/cmd_vel_safe',
            'hardware_enabled': False,
            'motor_pwm_pin': 33,
            'motor_direction_pin': 29,
            'motor_pwm_frequency_hz': 1000,
            'motor_ramp_step_percent': 5.0,
            'motor_ramp_interval_sec': 0.05,
            'max_pwm_percent': 99.0,
            'minimum_drive_pwm_percent': 35.0,
            'servo_i2c_address': 64,
            'servo_channel': 0,
            'servo_center_angle_deg': 72.0,
            'servo_turn_range_deg': 40.0,
            'servo_min_pulse_us': 500,
            'servo_max_pulse_us': 2500,
            'settings_file': '/home/motus/data/motus/car_settings.json',
            'wheelbase_m': 0.25,
            'max_steering_angle_rad': 0.45,
            'max_forward_speed_mps': 0.25,
            'max_reverse_speed_mps': 0.25,
            'motor_sign': 1.0,
            'steering_sign': 1.0,
            'angular_input_mode': 'yaw_rate',
            'allow_reverse': True,
            'command_timeout_sec': 1.5,
            'speed_deadband_mps': 0.01,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)

    def _lock_gpio(self):
        self.lock_file = open('/tmp/motus_car_gpio.lock', 'w', encoding='utf-8')
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('GPIO is already in use. Stop the old Flask controller or another car node.') from error

    def _steering_settings(self):
        center = float(self.get_parameter('servo_center_angle_deg').value)
        turn_range = float(self.get_parameter('servo_turn_range_deg').value)
        path = Path(str(self.get_parameter('settings_file').value)).expanduser()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                center = float(data.get('servo_center_angle', center))
                turn_range = float(data.get('servo_turn_range', turn_range))
                self.get_logger().info(f'Loaded steering settings from {path}')
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                self.get_logger().warning(f'Cannot read {path}: {error}. Using car.yaml values.')
        return center, turn_range

    def _start_hardware(self):
        if not self.hardware_enabled:
            return

        self._lock_gpio()
        try:
            import Jetson.GPIO as GPIO
            load_servo_kit()
        except ImportError as error:
            raise RuntimeError('Jetson.GPIO or adafruit_servokit is missing. Run scripts/install.sh.') from error

        self.gpio = GPIO
        GPIO.setwarnings(False)
        try:
            GPIO.cleanup()
        except Exception:
            pass
        GPIO.setmode(GPIO.BOARD)

        center, turn_range = self._steering_settings()
        self.motor = Motor(
            GPIO,
            int(self.get_parameter('motor_pwm_pin').value),
            int(self.get_parameter('motor_direction_pin').value),
            int(self.get_parameter('motor_pwm_frequency_hz').value),
            float(self.get_parameter('motor_ramp_step_percent').value),
            float(self.get_parameter('motor_ramp_interval_sec').value),
        )
        self.steering = Steering(
            int(self.get_parameter('servo_i2c_address').value),
            int(self.get_parameter('servo_channel').value),
            center,
            turn_range,
            int(self.get_parameter('servo_min_pulse_us').value),
            int(self.get_parameter('servo_max_pulse_us').value),
        )

    def _on_command(self, message: Twist):
        self.last_command_time = time.monotonic()
        if self.emergency_latched:
            self._apply_stop()
            return

        speed = float(message.linear.x)
        if not self.allow_reverse:
            speed = max(0.0, speed)
        speed = clamp(speed, -self.max_reverse, self.max_forward)
        angular_input = float(message.angular.z)

        if self.angular_input_mode == 'steering':
            steering_normalized = clamp(angular_input, -1.0, 1.0) * self.steering_sign
            steering_angle = steering_normalized * self.max_steer
        elif abs(speed) < self.speed_deadband:
            speed = 0.0
            steering_angle = 0.0
            steering_normalized = 0.0
        else:
            steering_angle = math.atan(self.wheelbase * angular_input / speed)
            steering_angle = clamp(steering_angle, -self.max_steer, self.max_steer)
            steering_normalized = clamp(steering_angle / self.max_steer, -1.0, 1.0) * self.steering_sign

        pwm = self._speed_to_pwm(speed)

        if self.motor is not None:
            self.motor.set(pwm)
        if self.steering is not None:
            self.steering.set(steering_normalized)

        now = time.monotonic()
        if now - self.last_command_log_time > 0.5:
            self.last_command_log_time = now
            self.get_logger().info(
                f'speed={speed:+.3f} m/s, pwm={pwm:+.1f}%, steering={steering_angle:+.3f} rad'
            )

    def _speed_to_pwm(self, speed: float) -> float:
        if speed == 0.0:
            return 0.0
        speed_limit = self.max_forward if speed > 0.0 else self.max_reverse
        pwm = clamp(abs(speed) / speed_limit, 0.0, 1.0) * self.max_pwm
        pwm = max(pwm, self.min_pwm)
        return math.copysign(pwm, speed) * self.motor_sign

    def _watchdog(self):
        if time.monotonic() - self.last_command_time > self.command_timeout:
            self._apply_stop()

    def _apply_stop(self):
        if self.motor is not None:
            self.motor.stop()
        if self.steering is not None:
            self.steering.center()

    def _stop_service(self, _request, response):
        self.emergency_latched = True
        self._apply_stop()
        response.success = True
        response.message = 'Stop latched. Call /car/clear_stop before moving again.'
        self.get_logger().error(response.message)
        return response

    def _clear_stop_service(self, _request, response):
        self._apply_stop()
        self.emergency_latched = False
        self.last_command_time = 0.0
        response.success = True
        response.message = 'Stop cleared. The car remains stopped until a new command arrives.'
        self.get_logger().warning(response.message)
        return response

    def close(self):
        if self.cleaned:
            return
        self.cleaned = True
        try:
            self._apply_stop()
            if self.motor is not None:
                self.motor.close()
            if self.steering is not None:
                self.steering.center()
            if self.gpio is not None:
                self.gpio.cleanup()
        except Exception as error:
            try:
                self.get_logger().error(f'Hardware cleanup error: {error}')
            except Exception:
                pass
        if self.lock_file is not None:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
            except Exception:
                pass
            self.lock_file = None


def main(args=None):
    rclpy.init(args=args)
    node = CarNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
