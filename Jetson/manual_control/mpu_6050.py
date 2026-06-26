#!/usr/bin/env python3

import math
import struct
import time

from smbus2 import SMBus


I2C_BUS = 1
I2C_ADDRESS = 0x68

SAMPLE_RATE_HZ = 100
PRINT_RATE_HZ = 10
GYRO_CALIBRATION_SAMPLES = 500

# Smaller = smoother but slower. Higher complementary alpha = trust gyro more.
LOW_PASS_ALPHA = 0.15
COMPLEMENTARY_ALPHA = 0.98


# MPU registers
SMPLRT_DIV = 0x19
CONFIG = 0x1A
GYRO_CONFIG = 0x1B
ACCEL_CONFIG = 0x1C
ACCEL_CONFIG_2 = 0x1D
ACCEL_XOUT_H = 0x3B
PWR_MGMT_1 = 0x6B
WHO_AM_I = 0x75

# Selected ranges: accelerometer +/-2 g, gyroscope +/-250 deg/s.
ACCEL_SCALE = 16384.0
GYRO_SCALE = 131.0

SENSOR_NAMES = {
    0x68: "MPU6050",
    0x70: "MPU6500",
}


def low_pass(previous, current):
    return previous + LOW_PASS_ALPHA * (current - previous)


def accel_roll_pitch(ax, ay, az):
    roll = math.degrees(math.atan2(ay, az))
    pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))
    return roll, pitch


class MPU6XXX:
    def __init__(self, bus_number=I2C_BUS, address=I2C_ADDRESS):
        self.bus_number = bus_number
        self.address = address
        self.bus = SMBus(bus_number)

        self.device_id = self.detect_sensor()
        self.sensor_name = SENSOR_NAMES[self.device_id]

        self.gyro_offset = (0.0, 0.0, 0.0)
        self.filtered_accel = (0.0, 0.0, 1.0)
        self.filtered_gyro = (0.0, 0.0, 0.0)
        self.roll = 0.0
        self.pitch = 0.0

        self.configure_sensor()

    def detect_sensor(self):
        try:
            device_id = self.bus.read_byte_data(self.address, WHO_AM_I)
        except OSError as error:
            raise RuntimeError(
                f"Cannot find sensor on I2C bus {self.bus_number} "
                f"at address {hex(self.address)}"
            ) from error

        if device_id not in SENSOR_NAMES:
            raise RuntimeError(f"Unsupported device ID: {hex(device_id)}")

        print(f"{SENSOR_NAMES[device_id]} detected successfully.")
        print(f"I2C bus: {self.bus_number}")
        print(f"I2C address: {hex(self.address)}")
        print(f"WHO_AM_I: {hex(device_id)}\n")

        return device_id

    def write_register(self, register, value):
        self.bus.write_byte_data(self.address, register, value)

    def configure_sensor(self):
        self.write_register(PWR_MGMT_1, 0x80)  # reset
        time.sleep(0.1)

        settings = [
            (PWR_MGMT_1, 0x01),   # wake sensor, use gyro X clock
            (SMPLRT_DIV, 9),      # 1000 Hz / (1 + 9) = 100 Hz
            (CONFIG, 0x03),       # digital low-pass filter
            (GYRO_CONFIG, 0x00),  # +/-250 deg/s
            (ACCEL_CONFIG, 0x00), # +/-2 g
        ]

        if self.device_id == 0x70:
            settings.append((ACCEL_CONFIG_2, 0x03))

        for register, value in settings:
            self.write_register(register, value)

        time.sleep(0.2)

    def read_raw_data(self):
        data = self.bus.read_i2c_block_data(self.address, ACCEL_XOUT_H, 14)
        return struct.unpack(">hhhhhhh", bytes(data))

    def read_sensor(self):
        ax_raw, ay_raw, az_raw, temp_raw, gx_raw, gy_raw, gz_raw = self.read_raw_data()

        temperature = self.temperature_celsius(temp_raw)

        return {
            "ax": ax_raw / ACCEL_SCALE,
            "ay": ay_raw / ACCEL_SCALE,
            "az": az_raw / ACCEL_SCALE,
            "gx": gx_raw / GYRO_SCALE,
            "gy": gy_raw / GYRO_SCALE,
            "gz": gz_raw / GYRO_SCALE,
            "temperature": temperature,
        }

    def temperature_celsius(self, raw_value):
        if self.device_id == 0x70:
            return (raw_value / 333.87) + 21.0

        return (raw_value / 340.0) + 36.53

    def calibrate_gyro(self, samples=GYRO_CALIBRATION_SAMPLES):
        print("Gyroscope calibration starting.")
        print("Keep the robot completely stationary...\n")

        gx_total = 0.0
        gy_total = 0.0
        gz_total = 0.0

        for sample in range(samples):
            readings = self.read_sensor()
            gx_total += readings["gx"]
            gy_total += readings["gy"]
            gz_total += readings["gz"]

            if sample % 100 == 0:
                print(f"Calibration progress: {sample}/{samples}")

            time.sleep(0.005)

        self.gyro_offset = (
            gx_total / samples,
            gy_total / samples,
            gz_total / samples,
        )

        ox, oy, oz = self.gyro_offset
        print("\nCalibration completed.")
        print(f"Gyro offsets: X={ox:.3f}, Y={oy:.3f}, Z={oz:.3f} deg/s\n")

    def initialize_orientation(self):
        readings = self.read_sensor()
        self.filtered_accel = (
            readings["ax"],
            readings["ay"],
            readings["az"],
        )
        self.roll, self.pitch = accel_roll_pitch(*self.filtered_accel)

    def update(self, dt):
        readings = self.read_sensor()

        accel = (
            readings["ax"],
            readings["ay"],
            readings["az"],
        )

        gyro = (
            readings["gx"] - self.gyro_offset[0],
            readings["gy"] - self.gyro_offset[1],
            readings["gz"] - self.gyro_offset[2],
        )

        self.filtered_accel = tuple(
            low_pass(previous, current)
            for previous, current in zip(self.filtered_accel, accel)
        )

        self.filtered_gyro = tuple(
            low_pass(previous, current)
            for previous, current in zip(self.filtered_gyro, gyro)
        )

        accel_roll, accel_pitch = accel_roll_pitch(*self.filtered_accel)

        gyro_roll = self.roll + self.filtered_gyro[0] * dt
        gyro_pitch = self.pitch + self.filtered_gyro[1] * dt

        self.roll = (
            COMPLEMENTARY_ALPHA * gyro_roll
            + (1.0 - COMPLEMENTARY_ALPHA) * accel_roll
        )

        self.pitch = (
            COMPLEMENTARY_ALPHA * gyro_pitch
            + (1.0 - COMPLEMENTARY_ALPHA) * accel_pitch
        )

        ax, ay, az = self.filtered_accel
        gx, gy, gz = self.filtered_gyro

        return {
            "ax": ax,
            "ay": ay,
            "az": az,
            "gx": gx,
            "gy": gy,
            "gz": gz,
            "roll": self.roll,
            "pitch": self.pitch,
            "temperature": readings["temperature"],
        }

    def close(self):
        self.bus.close()


def safe_dt(dt, fallback):
    if dt <= 0.0 or dt > 0.1:
        return fallback

    return dt


def print_readings(readings):
    print(
        f"Accel[g] "
        f"X={readings['ax']:7.3f} "
        f"Y={readings['ay']:7.3f} "
        f"Z={readings['az']:7.3f} | "
        f"Gyro[deg/s] "
        f"X={readings['gx']:8.2f} "
        f"Y={readings['gy']:8.2f} "
        f"Z={readings['gz']:8.2f} | "
        f"Roll={readings['roll']:7.2f} deg "
        f"Pitch={readings['pitch']:7.2f} deg | "
        f"Temp={readings['temperature']:5.1f} C"
    )


def main():
    sensor = None

    try:
        sensor = MPU6XXX()
        sensor.calibrate_gyro()
        sensor.initialize_orientation()

        sample_period = 1.0 / SAMPLE_RATE_HZ
        print_period = 1.0 / PRINT_RATE_HZ

        previous_time = time.monotonic()
        last_print_time = previous_time

        print("Reading sensor.")
        print("Press Ctrl+C to stop.\n")

        while True:
            loop_start = time.monotonic()
            dt = safe_dt(loop_start - previous_time, sample_period)
            previous_time = loop_start

            readings = sensor.update(dt)

            now = time.monotonic()
            if now - last_print_time >= print_period:
                last_print_time = now
                print_readings(readings)

            sleep_time = sample_period - (time.monotonic() - loop_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nStopped.")

    except RuntimeError as error:
        print(f"Error: {error}")

    except OSError as error:
        print("I2C communication error.")
        print("Check the power, ground, SDA and SCL connections.")
        print(error)

    finally:
        if sensor is not None:
            sensor.close()


if __name__ == "__main__":
    main()
