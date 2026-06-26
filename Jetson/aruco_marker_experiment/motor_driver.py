"""Small motor interface. Dry-run is the default and safest mode."""

from __future__ import annotations

import time
import threading
from abc import ABC, abstractmethod
from typing import Any


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class MotorDriver(ABC):
    def set_armed(self, armed: bool) -> None:
        pass

    @abstractmethod
    def set_drive(self, throttle: float, steering: float) -> None:
        """throttle and steering are both in the range [-1, 1]."""

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class ConsoleMotorDriver(MotorDriver):
    """Prints commands instead of moving the car."""

    def __init__(self) -> None:
        self._last = (None, None)
        self._last_print = 0.0
        self.armed = False

    def set_armed(self, armed: bool) -> None:
        self.armed = armed

    def set_drive(self, throttle: float, steering: float) -> None:
        throttle = clamp(throttle)
        steering = clamp(steering)
        if not self.armed:
            throttle = 0.0
            steering = 0.0
        now = time.monotonic()
        if (abs(throttle - (self._last[0] or 0.0)) > 0.03 or
                abs(steering - (self._last[1] or 0.0)) > 0.03 or
                now - self._last_print > 1.0):
            print(f"DRIVE throttle={throttle:+.2f} steering={steering:+.2f}")
            self._last = (throttle, steering)
            self._last_print = now

    def stop(self) -> None:
        self.set_drive(0.0, 0.0)

    def close(self) -> None:
        self.stop()


class JetsonGpioMotorDriver(MotorDriver):
    """
    Reference-code-compatible motor + steering driver.

    The drive motor uses Jetson.GPIO with one BOARD PWM pin and one BOARD
    direction pin. Steering uses a PCA9685 over I2C through adafruit_servokit.
    """

    def __init__(
        self,
        motor_pwm_pin: int = 33,
        motor_dir_pin: int = 29,
        motor_pwm_hz: int = 1000,
        servo_channels: int = 16,
        servo_i2c_address: int | str = 0x40,
        servo_channel: int = 0,
        servo_center_angle: float = 72.0,
        servo_turn_range: float = 27.0,
        servo_min_pulse_us: int = 500,
        servo_max_pulse_us: int = 2500,
        motor_ramp_step: float = 5.0,
        motor_ramp_interval: float = 0.05,
        throttle_sign: float = 1.0,
        steering_sign: float = -1.0,
        **_unused: Any,
    ) -> None:
        try:
            import Jetson.GPIO as GPIO
        except ImportError as exc:
            raise RuntimeError("Install Jetson.GPIO or run without --gpio") from exc
        try:
            from adafruit_servokit import ServoKit
        except ImportError as exc:
            raise RuntimeError(
                "Install adafruit-circuitpython-servokit for PCA9685 steering"
            ) from exc

        self.GPIO = GPIO
        self.ServoKit = ServoKit
        self.motor_pwm: Any | None = None
        self.servo_kit: Any | None = None
        self.motor_dir_pin = motor_dir_pin
        self.motor_pwm_hz = motor_pwm_hz
        self.motor_ramp_step = float(motor_ramp_step)
        self.motor_ramp_interval = float(motor_ramp_interval)
        self.servo_channel = servo_channel
        self.servo_center_angle = servo_center_angle
        self.servo_turn_range = servo_turn_range
        self.servo_min_angle = servo_center_angle - servo_turn_range
        self.servo_max_angle = servo_center_angle + servo_turn_range
        self.throttle_sign = throttle_sign
        self.steering_sign = steering_sign
        self.armed = False
        self._motor_lock = threading.Lock()
        self._target_motor_speed = 0.0
        self._current_motor_speed = 0.0
        self._ramp_running = False
        self._ramp_thread: threading.Thread | None = None
        if isinstance(servo_i2c_address, str):
            servo_i2c_address = int(servo_i2c_address, 0)

        try:
            GPIO.setwarnings(False)
            try:
                GPIO.cleanup()
            except Exception:
                pass
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(motor_pwm_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(motor_dir_pin, GPIO.OUT, initial=GPIO.LOW)

            self.motor_pwm = GPIO.PWM(motor_pwm_pin, motor_pwm_hz)
            self.motor_pwm.start(0.0)
            self.servo_kit = ServoKit(channels=servo_channels, address=servo_i2c_address)
            for channel in range(servo_channels):
                self.servo_kit.servo[channel].set_pulse_width_range(
                    servo_min_pulse_us,
                    servo_max_pulse_us,
                )
            self._set_servo_steering(0.0)
            self._ramp_running = True
            self._ramp_thread = threading.Thread(target=self._ramp_loop, daemon=True)
            self._ramp_thread.start()
        except (OSError, RuntimeError, ValueError) as exc:
            self._cleanup_failed_init()
            raise RuntimeError(
                self._hardware_init_error(
                    exc,
                    motor_pwm_pin,
                    motor_dir_pin,
                    motor_pwm_hz,
                    int(servo_i2c_address),
                    servo_channel,
                )
            ) from exc

    def set_armed(self, armed: bool) -> None:
        self.armed = armed
        if not armed:
            self.stop()

    def set_drive(self, throttle: float, steering: float) -> None:
        if self.motor_pwm is None or self.servo_kit is None:
            raise RuntimeError("GPIO motor driver is not initialized")

        throttle = clamp(throttle) * self.throttle_sign
        steering = clamp(steering) * self.steering_sign
        if not self.armed:
            throttle = 0.0
            steering = 0.0

        with self._motor_lock:
            self._target_motor_speed = throttle * 100.0
        self._set_servo_steering(steering)

    def stop(self) -> None:
        if self.motor_pwm is not None:
            with self._motor_lock:
                self._target_motor_speed = 0.0
                self._current_motor_speed = 0.0
                self._apply_motor_output(0.0)
        self._set_servo_steering(0.0)

    def close(self) -> None:
        if self.motor_pwm is not None and self.servo_kit is not None:
            self.stop()
        time.sleep(0.2)
        self._release_hardware()

        try:
            self.GPIO.cleanup()
        except Exception:
            pass

    def _cleanup_failed_init(self) -> None:
        self._release_hardware()
        try:
            self.GPIO.cleanup()
        except Exception:
            pass

    def _ramp_loop(self) -> None:
        while self._ramp_running:
            with self._motor_lock:
                target = self._target_motor_speed
                current = self._current_motor_speed

                if current != 0.0 and target != 0.0 and (current > 0.0) != (target > 0.0):
                    if current > 0.0:
                        next_speed = max(0.0, current - self.motor_ramp_step)
                    else:
                        next_speed = min(0.0, current + self.motor_ramp_step)
                else:
                    difference = target - current
                    if abs(difference) <= self.motor_ramp_step:
                        next_speed = target
                    elif difference > 0.0:
                        next_speed = current + self.motor_ramp_step
                    else:
                        next_speed = current - self.motor_ramp_step

                self._current_motor_speed = next_speed
                self._apply_motor_output(next_speed)

            time.sleep(self.motor_ramp_interval)

    def _apply_motor_output(self, speed: float) -> None:
        if self.motor_pwm is None:
            return

        speed = clamp(speed, -100.0, 100.0)
        if speed > 0.01:
            self.GPIO.output(self.motor_dir_pin, self.GPIO.LOW)
            motor_duty = abs(speed)
        elif speed < -0.01:
            self.GPIO.output(self.motor_dir_pin, self.GPIO.HIGH)
            motor_duty = abs(speed)
        else:
            self.GPIO.output(self.motor_dir_pin, self.GPIO.LOW)
            motor_duty = 0.0

        self.motor_pwm.ChangeDutyCycle(motor_duty)

    def _set_servo_steering(self, steering: float) -> None:
        if self.servo_kit is None:
            return
        angle = self.servo_center_angle + clamp(steering) * self.servo_turn_range
        angle = clamp(angle, self.servo_min_angle, self.servo_max_angle)
        self.servo_kit.servo[self.servo_channel].angle = angle

    def _release_hardware(self) -> None:
        self._ramp_running = False
        if self._ramp_thread is not None:
            self._ramp_thread.join(timeout=1.0)
            self._ramp_thread = None

        if self.servo_kit is not None:
            try:
                self.servo_kit.servo[self.servo_channel].angle = None
            except Exception:
                pass
            self.servo_kit = None

        if self.motor_pwm is not None:
            try:
                self.motor_pwm.ChangeDutyCycle(0.0)
                self.motor_pwm.stop()
            except Exception:
                pass
            self.motor_pwm = None

    def _hardware_init_error(
        self,
        exc: Exception,
        motor_pwm_pin: int,
        motor_dir_pin: int,
        motor_pwm_hz: int,
        servo_i2c_address: int,
        servo_channel: int,
    ) -> str:
        model = getattr(self.GPIO, "JETSON_INFO", {}).get("TYPE", "unknown Jetson")
        return (
            "Failed to initialize reference motor/steering hardware "
            f"on {model}: motor PWM BOARD pin {motor_pwm_pin} at {motor_pwm_hz} Hz, "
            f"motor direction BOARD pin {motor_dir_pin}, PCA9685 address "
            f"0x{servo_i2c_address:02x} channel {servo_channel}. Reported error: {exc}. "
            "Check that the motor PWM pin matches the working reference wiring, "
            "I2C is enabled, the PCA9685 is visible with `i2cdetect`, and "
            "adafruit-circuitpython-servokit is installed."
        )
