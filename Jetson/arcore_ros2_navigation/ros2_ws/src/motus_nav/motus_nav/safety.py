#!/usr/bin/env python3
import time

import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Bool

from .math_utils import euler_to_matrix, make_transform

CAMERA_LINK_FROM_OPTICAL = np.array([
    [0.0, 0.0, 1.0],
    [-1.0, 0.0, 0.0],
    [0.0, -1.0, 0.0],
], dtype=np.float64)


class SafetyNode(Node):
    def __init__(self):
        super().__init__('safety_node')
        self.declare_parameter('input_topic', '/cmd_vel')
        self.declare_parameter('output_topic', '/cmd_vel_safe')
        self.declare_parameter('tracking_timeout_sec', 0.6)
        self.declare_parameter('cloud_timeout_sec', 0.6)
        self.declare_parameter('command_timeout_sec', 0.5)
        self.declare_parameter('jump_hold_sec', 1.5)
        self.declare_parameter('emergency_distance_m', 0.40)
        self.declare_parameter('emergency_min_distance_m', -0.05)
        self.declare_parameter('emergency_half_width_m', 0.30)
        self.declare_parameter('min_obstacle_height_m', 0.04)
        self.declare_parameter('max_obstacle_height_m', 1.20)
        self.declare_parameter('camera_x', 0.20)
        self.declare_parameter('camera_y', 0.0)
        self.declare_parameter('camera_z', 0.15)
        self.declare_parameter('camera_roll', 0.0)
        self.declare_parameter('camera_pitch', 0.0)
        self.declare_parameter('camera_yaw', 0.0)

        qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE)
        sensor_qos = QoSProfile(depth=2, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.output_pub = self.create_publisher(Twist, str(self.get_parameter('output_topic').value), qos)
        self.create_subscription(Twist, str(self.get_parameter('input_topic').value), self._command_callback, qos)
        self.create_subscription(Bool, '/phone/tracking_ok', self._tracking_callback, qos)
        self.create_subscription(Bool, '/phone/pose_jump', self._jump_callback, qos)
        self.create_subscription(PointCloud2, '/phone/points', self._cloud_callback, sensor_qos)
        self.timer = self.create_timer(0.05, self._publish_safe_command)

        self.last_command = Twist()
        self.last_command_time = 0.0
        self.last_tracking_time = 0.0
        self.last_cloud_time = 0.0
        self.jump_until = 0.0
        self.tracking_ok = False
        self.obstacle_close = True
        self.last_reason = ''
        self.last_cloud_empty = False
        self.base_from_optical = self._make_base_from_optical()
        self.get_logger().info('Safety guard started; motor driver should subscribe to /cmd_vel_safe')

    def _make_base_from_optical(self):
        camera_rotation = euler_to_matrix(
            float(self.get_parameter('camera_roll').value),
            float(self.get_parameter('camera_pitch').value),
            float(self.get_parameter('camera_yaw').value),
        )
        base_from_camera = make_transform(
            (
                float(self.get_parameter('camera_x').value),
                float(self.get_parameter('camera_y').value),
                float(self.get_parameter('camera_z').value),
            ),
            rotation=camera_rotation,
        )
        return base_from_camera @ make_transform(rotation=CAMERA_LINK_FROM_OPTICAL)

    def _command_callback(self, message: Twist):
        self.last_command = message
        self.last_command_time = time.monotonic()

    def _tracking_callback(self, message: Bool):
        self.tracking_ok = bool(message.data)
        if self.tracking_ok:
            self.last_tracking_time = time.monotonic()

    def _jump_callback(self, message: Bool):
        if message.data:
            self.jump_until = time.monotonic() + float(self.get_parameter('jump_hold_sec').value)

    def _cloud_callback(self, message: PointCloud2):
        self.last_cloud_time = time.monotonic()
        if message.point_step != 12 or not message.data:
            self.obstacle_close = True
            self.last_cloud_empty = True
            return
        points = np.frombuffer(message.data, dtype='<f4')
        if points.size % 3 != 0:
            self.obstacle_close = True
            self.last_cloud_empty = False
            return
        self.last_cloud_empty = False
        points = points.reshape((-1, 3))
        rotation = self.base_from_optical[:3, :3]
        translation = self.base_from_optical[:3, 3]
        base_points = points @ rotation.T + translation
        distance = float(self.get_parameter('emergency_distance_m').value)
        min_distance = float(self.get_parameter('emergency_min_distance_m').value)
        half_width = float(self.get_parameter('emergency_half_width_m').value)
        min_height = float(self.get_parameter('min_obstacle_height_m').value)
        max_height = float(self.get_parameter('max_obstacle_height_m').value)
        zone = (
            (base_points[:, 0] > min_distance) &
            (base_points[:, 0] < distance) &
            (np.abs(base_points[:, 1]) < half_width) &
            (base_points[:, 2] > min_height) &
            (base_points[:, 2] < max_height)
        )
        self.obstacle_close = bool(np.any(zone))

    def _publish_safe_command(self):
        now = time.monotonic()
        reason = ''
        if not self.tracking_ok or now - self.last_tracking_time > float(self.get_parameter('tracking_timeout_sec').value):
            reason = 'ARCore tracking unavailable'
        elif now - self.last_cloud_time > float(self.get_parameter('cloud_timeout_sec').value):
            reason = 'depth cloud stale'
        elif now - self.last_command_time > float(self.get_parameter('command_timeout_sec').value):
            reason = 'velocity command stale'
        elif now < self.jump_until:
            reason = 'pose jump hold'
        elif self.last_cloud_empty and self.last_command.linear.x > 0.0:
            reason = 'depth cloud empty'
        elif self.obstacle_close and self.last_command.linear.x > 0.0:
            reason = 'obstacle inside emergency zone'

        if reason:
            self.output_pub.publish(Twist())
            if reason != self.last_reason:
                self.get_logger().warning(f'STOP: {reason}')
        else:
            self.output_pub.publish(self.last_command)
            if self.last_reason:
                self.get_logger().info('Safety conditions restored; forwarding commands')
        self.last_reason = reason


def main(args=None):
    rclpy.init(args=args)
    node = SafetyNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.output_pub.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
