from adafruit_servokit import ServoKit
import time

class ServoDriver:
    """
    Driver for MG996R Servo using PCA9685
    
    Prerequisites:
        pip3 install adafruit-circuitpython-servokit
    """
    def __init__(self, channels=16, address=0x40, bus_num=None, min_angle=60, max_angle=120):
        """
        Initialize the ServoDriver.
        
        Args:
            channels (int): Number of channels on the PCA9685 (default 16).
            address (int): I2C address of the PCA9685 (default 0x40).
            bus_num (int): I2C bus number (optional, usually detected automatically).
            min_angle (float): Minimum mechanical limit for steering (default 60).
            max_angle (float): Maximum mechanical limit for steering (default 120).
        """
        self.min_angle = min_angle
        self.max_angle = max_angle
        
        try:
            # ServoKit attempts to detect the correct I2C bus via 'board' library
            self.kit = ServoKit(channels=channels, address=address)
            
            # Configuring pulse width range for MG996R (500-2500us)
            for i in range(channels):
                self.kit.servo[i].set_pulse_width_range(500, 2500)
                
            print(f"ServoDriver initialized on address {hex(address)}")
            print(f"Steering limits set to: {self.min_angle}° - {self.max_angle}°")
            
        except Exception as e:
            print(f"Failed to initialize PCA9685: {e}")
            print("Ensure I2C is enabled (sudo jetson-io.py) and user has permissions.")
            raise

    def set_angle(self, channel, angle):
        """
        Set the angle of the servo, respecting the configured limits.
        
        Args:
            channel (int): The channel number on PCA9685 (0-15).
            angle (float): The desired angle (0-180).
        """
        if not (0 <= channel <= 15):
             print(f"Error: Channel {channel} out of range (0-15)")
             return

        # Clamp angle to mechanical limits
        clamped_angle = max(self.min_angle, min(self.max_angle, angle))
        
        if clamped_angle != angle:
            pass
        
        try:
            self.kit.servo[channel].angle = clamped_angle
        except Exception as e:
            print(f"Error setting angle on channel {channel}: {e}")

    def set_steering(self, channel, value):
        """
        Set steering using a normalized value (-1.0 to 1.0).
        
        Args:
            channel (int): Servo channel.
            value (float): Steering value from -1.0 (Left/Min) to 1.0 (Right/Max).
        """
        # Clamp value to -1.0 to 1.0
        value = max(-1.0, min(1.0, value))
        
        # Map [-1, 1] to [min_angle, max_angle]
        # 0.0 maps to center ((min + max) / 2)
        angle_range = self.max_angle - self.min_angle
        center_angle = (self.min_angle + self.max_angle) / 2
        
        # Linear mapping: angle = center + (value * range / 2)
        target_angle = center_angle + (value * (angle_range / 2))
        
        self.set_angle(channel, target_angle)

    def stop(self, channel):
        """
        Stop the servo by releasing the PWM signal (setting angle to None).
        """
        self.kit.servo[channel].angle = None

if __name__ == "__main__":
    print("Initializing Servo Driver...")
    try:
        # Assuming Servo is connected to Channel 0
        # Default limits: 60 to 120 degrees
        servo = ServoDriver(min_angle=60, max_angle=120)
        servo_channel = 0
        
        print("Testing Servo Sweep with Limits...")
        
        print("Center (0.0 -> 90°)")
        servo.set_steering(servo_channel, 0.0)
        time.sleep(1)
        
        print("Full Left (-1.0 -> 60°)")
        servo.set_steering(servo_channel, -1.0)
        time.sleep(1)
        
        print("Full Right (1.0 -> 120°)")
        servo.set_steering(servo_channel, 1.0)
        time.sleep(1)
        
        print("Center (0.0 -> 90°)")
        servo.set_steering(servo_channel, 0.0)
        time.sleep(1)
        
        print("Releasing Servo (Stop PWM)")
        servo.stop(servo_channel)
        
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")
