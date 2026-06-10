#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
import tf2_ros
import math

class SimpleSim(Node):
    def __init__(self):
        super().__init__('simple_sim')
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_callback, 10)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
        self.x, self.y, self.th = 0.0, 0.0, 0.0
        self.create_timer(0.1, self.update) # 10Hz

    def cmd_callback(self, msg):
        # Move the virtual car based on Nav2 commands
        dt = 0.1
        self.x += msg.linear.x * math.cos(self.th) * dt
        self.y += msg.linear.x * math.sin(self.th) * dt
        self.th += msg.angular.z * dt

    def update(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.rotation.z = math.sin(self.th / 2.0)
        t.transform.rotation.w = math.cos(self.th / 2.0)
        self.tf_broadcaster.send_transform(t)

def main():
    rclpy.init()
    rclpy.spin(SimpleSim())
    rclpy.shutdown()