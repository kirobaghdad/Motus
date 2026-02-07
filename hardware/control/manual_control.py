#!/usr/bin/env python3
import evdev
import sys
import time
import os

# Add parent directory to path to import drivers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from drivers.motor_driver import MotorDriver
from drivers.servo_driver import ServoDriver

# PS3 Controller Axis Mappings (Usually)
# Adjust based on your specific controller
AXIS_LEFT_STICK_Y = 1   # Forward/Backward
AXIS_RIGHT_STICK_X = 3  # Steering (Left/Right)

# Deadzone to filter out small joystick movements
DEADZONE = 10 

def map_range(value, leftMin, leftMax, rightMin, rightMax):
    # Figure out how 'wide' each range is
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin

    # Convert the left range into a 0-1 range (float)
    valueScaled = float(value - leftMin) / float(leftSpan)

    # Convert the 0-1 range into a value in the right range.
    return rightMin + (valueScaled * rightSpan)

def main():
    print("Finding PS3 Controller...")
    device_path = None
    
    # Try to find the PS3 controller device
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        print(f"Found device: {device.name} at {device.path}")
        if "Sony" in device.name or "PLAYSTATION" in device.name or "Motion" in device.name: 
            device_path = device.path
            print(f"-> Selected: {device.name}")
            break
            
    if not device_path:
        print("Error: PS3 Controller not found. Please pair it via Bluetooth first.")
        return

    # Initialize Hardware
    try:
        motor = MotorDriver(pwm_pin=33, dir_pin=29)
        servo = ServoDriver(min_angle=60, max_angle=120) 
        # Configure servo to center initially
        servo.set_steering(0, 0.0) 
        
        gamepad = evdev.InputDevice(device_path)
        print("Controller Connected. Press Ctrl+C to exit.")
        print("Left Stick Y: Speed | Right Stick X: Steering")

        # Variables to track current state
        current_speed = 0
        current_steering = 0.0

        for event in gamepad.read_loop():
            # Handle Axis Events
            if event.type == evdev.ecodes.EV_ABS:
                
                # Steering (Right Stick X)
                if event.code == AXIS_RIGHT_STICK_X:
                    val = event.value
                    # PS3 Stick range is usually 0-255, center approx 127
                    # Normalize to -1.0 (Left) to 1.0 (Right)
                    
                    if 118 < val < 138: # Deadzone
                        steering_val = 0.0
                    else:
                        steering_val = map_range(val, 0, 255, -1.0, 1.0)
                    
                    servo.set_steering(0, steering_val)
                    current_steering = steering_val

                # Speed (Left Stick Y)
                elif event.code == AXIS_LEFT_STICK_Y:
                    val = event.value
                    # PS3 Stick range is usually 0-255
                    # 0 is Full Up (Forward), 255 is Full Down (Backward)
                    
                    if 118 < val < 138: # Deadzone
                        speed_val = 0
                    else:
                        # Map 0 -> 100 (Forward), 255 -> -100 (Backward)
                        speed_val = map_range(val, 0, 255, 100, -100)
                    
                    motor.set_speed(speed_val)
                    current_speed = speed_val
                    
            # Handle Button Events (e.g., specific buttons to stop)
            # You can add more logic here, e.g., 'X' button to force stop

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        print("Stopping hardware...")
        try:
            motor.stop()
            servo.stop(0)
            motor.cleanup()
        except:
            pass

if __name__ == "__main__":
    main()
