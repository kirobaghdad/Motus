from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .math_utils import clamp
from .settings import CarSettings


@dataclass
class HardwareStatus:
    enabled: bool
    speed_pwm: float
    steering: float
    message: str


class MockHardware:
    def __init__(self) -> None:
        self.speed_pwm = 0.0
        self.steering = 0.0

    def command(self, speed_pwm: float, steering: float) -> None:
        self.speed_pwm = speed_pwm
        self.steering = steering

    def stop(self, center: bool = True) -> None:
        self.speed_pwm = 0.0
        if center:
            self.steering = 0.0

    def status(self) -> HardwareStatus:
        return HardwareStatus(
            enabled=False,
            speed_pwm=self.speed_pwm,
            steering=self.steering,
            message="Simulation mode",
        )

    def steering_config(self) -> dict[str, float]:
        return {"center_deg": 0.0, "range_deg": 0.0}

    def set_steering_config(self, center_deg: float, range_deg: float) -> dict[str, float]:
        return self.steering_config()

    def cleanup(self) -> None:
        self.stop()


class JetsonHardware:
    """Motor and steering driver adapted from the user's tested pinout."""

    def __init__(self, settings: CarSettings) -> None:
        import Jetson.GPIO as GPIO
        from adafruit_servokit import ServoKit

        self.settings = settings
        self.GPIO = GPIO
        self.lock = threading.RLock()
        self.running = True
        self.target_pwm = 0.0
        self.output_pwm = 0.0
        self.steering = 0.0
        self.last_command = time.monotonic()

        GPIO.setwarnings(False)
        try:
            GPIO.cleanup()
        except Exception:
            pass
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(settings.motor_dir_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(settings.motor_pwm_pin, GPIO.OUT, initial=GPIO.LOW)

        self.motor_pwm = GPIO.PWM(settings.motor_pwm_pin, 1000)
        self.motor_pwm.start(0)

        self.servo_kit = ServoKit(channels=16, address=settings.servo_address)
        for channel in range(16):
            self.servo_kit.servo[channel].set_pulse_width_range(500, 2500)
        self._set_steering(0.0)

        threading.Thread(target=self._ramp_loop, daemon=True).start()
        threading.Thread(target=self._watchdog_loop, daemon=True).start()

    def _apply_motor(self, value: float) -> None:
        value = clamp(value * self.settings.motor_sign, -100.0, 100.0)
        if value > 0:
            self.GPIO.output(self.settings.motor_dir_pin, self.GPIO.LOW)
            self.motor_pwm.ChangeDutyCycle(abs(value))
        elif value < 0:
            self.GPIO.output(self.settings.motor_dir_pin, self.GPIO.HIGH)
            self.motor_pwm.ChangeDutyCycle(abs(value))
        else:
            self.motor_pwm.ChangeDutyCycle(0)
            self.GPIO.output(self.settings.motor_dir_pin, self.GPIO.LOW)

    def _set_steering(self, value: float) -> None:
        value = clamp(value * self.settings.servo_sign, -1.0, 1.0)
        angle = self.settings.servo_center_deg + value * self.settings.servo_range_deg
        angle = clamp(angle, 0.0, 180.0)
        self.servo_kit.servo[self.settings.servo_channel].angle = angle
        self.steering = value

    def steering_config(self) -> dict[str, float]:
        return {
            "center_deg": self.settings.servo_center_deg,
            "range_deg": self.settings.servo_range_deg,
            "min_deg": max(0.0, self.settings.servo_center_deg - self.settings.servo_range_deg),
            "max_deg": min(180.0, self.settings.servo_center_deg + self.settings.servo_range_deg),
        }

    def set_steering_config(self, center_deg: float, range_deg: float) -> dict[str, float]:
        with self.lock:
            self.settings.servo_center_deg = clamp(center_deg, 0.0, 180.0)
            self.settings.servo_range_deg = clamp(range_deg, 0.0, 80.0)
            self._set_steering(0.0)
            return self.steering_config()

    def _ramp_loop(self) -> None:
        while self.running:
            with self.lock:
                target = self.target_pwm
                current = self.output_pwm
                step = self.settings.motor_ramp_step

                if current != 0 and target != 0 and (current > 0) != (target > 0):
                    next_pwm = max(0.0, current - step) if current > 0 else min(0.0, current + step)
                else:
                    diff = target - current
                    if abs(diff) <= step:
                        next_pwm = target
                    elif diff > 0:
                        next_pwm = current + step
                    else:
                        next_pwm = current - step

                self.output_pwm = next_pwm
                self._apply_motor(next_pwm)

            time.sleep(self.settings.motor_ramp_interval)

    def _watchdog_loop(self) -> None:
        while self.running:
            if time.monotonic() - self.last_command > 1.5:
                self.stop(center=True)
            time.sleep(0.1)

    def command(self, speed_pwm: float, steering: float) -> None:
        with self.lock:
            self.last_command = time.monotonic()
            self.target_pwm = clamp(speed_pwm, -100.0, 100.0)
            self._set_steering(steering)

    def stop(self, center: bool = True) -> None:
        with self.lock:
            self.last_command = time.monotonic()
            self.target_pwm = 0.0
            self.output_pwm = 0.0
            self._apply_motor(0.0)
            if center:
                self._set_steering(0.0)

    def status(self) -> HardwareStatus:
        with self.lock:
            return HardwareStatus(
                enabled=True,
                speed_pwm=round(self.output_pwm, 2),
                steering=round(self.steering, 3),
                message="Jetson GPIO active",
            )

    def cleanup(self) -> None:
        self.running = False
        self.stop(center=True)
        time.sleep(0.1)
        self.motor_pwm.stop()
        self.GPIO.cleanup()


def build_hardware(settings: CarSettings):
    if not settings.hardware_enabled:
        return MockHardware()

    try:
        return JetsonHardware(settings)
    except Exception as error:
        print(f"Hardware startup failed; using simulation mode: {error}")
        return MockHardware()
