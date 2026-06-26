#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import sys
import os

# Ensure Python can locate your low-level drivers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import your partner's validated hardware drivers
from drivers.motor_driver import MotorDriver
from drivers.servo_driver import ServoDriver

class CarMoveBridge(Node):
    def __init__(self):
        super().__init__('car_move_bridge')
        
        # --- CALIBRATION PARAMETERS ---
        # Match these exactly to what your Nav2 parameters use!
        self.MAX_LINEAR_VEL = 1.2   # Maximum forward velocity in m/s
        self.MAX_ANGULAR_VEL = 1.0  # Maximum turning velocity in rad/s
        
        # Initialize Hardware Drivers using your partner's configurations
        try:
            self.get_logger().info("Initializing Jetson Hardware Drivers...")
            self.motor = MotorDriver(pwm_pin=33, dir_pin=29)
            self.servo = ServoDriver(min_angle=60, max_angle=120)
            
            # Set steering straight initially
            self.servo.set_steering(0, 0.0)
            self.get_logger().info("Hardware successfully bound.")
        except Exception as e:
            self.get_logger().error(f"Hardware initialization failed: {e}")
            raise e

        # Subscribe to the velocity commands sent by Nav2
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            'cmd_vel',
            self.cmd_vel_callback,
            10
        )
        
        self.get_logger().info("Car Move Bridge active. Listening to /cmd_vel...")

    def cmd_vel_callback(self, msg: Twist):
        linear_x = msg.linear.x
        angular_z = msg.angular.z

        # --- 1. PROCESS MOTOR SPEED ---
        # Map linear.x (m/s) to percentage (-100 to 100)
        if abs(linear_x) < 0.01:
            speed_pct = 0
        else:
            speed_pct = (linear_x / self.MAX_LINEAR_VEL) * 100.0
            
        # Clamp value to hardware limits to protect the circuit
        speed_pct = max(-100, min(100, speed_pct))

        # --- 2. PROCESS SERVO STEERING ---
        # Map angular.z (rad/s) to normalized steering (-1.0 to 1.0)
        # Note: If your physical car steers RIGHT when Nav2 commands LEFT, 
        # add a negative sign here to invert it: steering_val = -(angular_z / self.MAX_ANGULAR_VEL)
        if abs(angular_z) < 0.01:
            steering_val = 0.0
        else:
            steering_val = angular_z / self.MAX_ANGULAR_VEL
            
        # Clamp to hardware limits
        steering_val = max(-1.0, min(1.0, steering_val))

        # --- 3. DISPATCH COMMANDS TO HARDWARE ---
        self.motor.set_speed(speed_pct)
        self.servo.set_steering(0, steering_val)

        self.get_logger().debug(f"In: ({linear_x:.2f}m/s, {angular_z:.2f}rad/s) -> Out: (Motor: {speed_pct:.1f}%, Servo: {steering_val:.2f})")

    def destroy_node(self):
        # Always safe-stop the car when the node drops offline
        self.get_logger().warn("Shutting down bridge. Safely stopping vehicle motors...")
        try:
            self.motor.stop()
            self.servo.stop(0)
            self.motor.cleanup()
        except Exception as e:
            self.get_logger().error(f"Error clean up: {e}")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    try:
        node = CarMoveBridge()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Triggers cleanly if you hit Ctrl+C
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()