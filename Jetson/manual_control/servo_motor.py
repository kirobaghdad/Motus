from adafruit_servokit import ServoKit
import time


class ServoDriver:
    def __init__(
        self,
        channels=16,
        address=0x40,
        center_angle=72,
        turn_range=35
    ):
        self.center_angle = center_angle
        self.turn_range = turn_range

        self.min_angle = center_angle - turn_range
        self.max_angle = center_angle + turn_range

        try:
            self.kit = ServoKit(channels=channels, address=address)

            for i in range(channels):
                self.kit.servo[i].set_pulse_width_range(500, 2500)

            print(f"ServoDriver initialized on I2C address {hex(address)}")
            print(f"Left limit:   {self.min_angle}°")
            print(f"Center angle: {self.center_angle}°")
            print(f"Right limit:  {self.max_angle}°")

        except Exception as e:
            print(f"Failed to initialize PCA9685: {e}")
            raise

    def set_angle(self, channel, angle):
        if not 0 <= channel <= 15:
            print(f"Error: Channel {channel} out of range. Use 0-15.")
            return

        clamped_angle = max(self.min_angle, min(self.max_angle, angle))

        try:
            self.kit.servo[channel].angle = clamped_angle
            print(f"Channel {channel} angle set to {clamped_angle:.1f}°")
        except Exception as e:
            print(f"Error setting angle on channel {channel}: {e}")

    def set_steering(self, channel, value):
        """
        -1.0 = full left
         0.0 = center
         1.0 = full right
        """

        value = max(-1.0, min(1.0, value))

        target_angle = self.center_angle + (value * self.turn_range)

        self.set_angle(channel, target_angle)

    def center(self, channel):
        self.set_steering(channel, 0.0)

    def stop(self, channel):
        self.kit.servo[channel].angle = None
        print(f"Channel {channel} PWM released.")


if __name__ == "__main__":
    servo_channel = 0

    servo = ServoDriver(
        center_angle=72,
        turn_range=27
    )

    print("Center")
    servo.set_steering(servo_channel, 0.0)
    time.sleep(2)

    print("Full Left")
    servo.set_steering(servo_channel, -1.0)
    time.sleep(2)

    print("Center")
    servo.set_steering(servo_channel, 0.0)
    time.sleep(2)

    print("Full Right")
    servo.set_steering(servo_channel, 1.0)
    time.sleep(2)

    print("Center")
    servo.set_steering(servo_channel, 0.0)
    time.sleep(5)