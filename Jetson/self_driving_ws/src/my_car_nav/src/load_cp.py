#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import numpy as np
from sensor_msgs.msg import PointCloud2, PointField
import std_msgs.msg

class VirtualSensor(Node):
    def __init__(self):
        super().__init__('virtual_sensor')
        self.publisher_ = self.create_publisher(PointCloud2, 'cloud_point', 10)
        self.timer = self.create_timer(1.0, self.publish_cloud)
        self.declare_parameter('file_path', '')
        # --- CONFIGURATION ---
        # Replace with your actual text file path
        self.file_path = self.get_parameter('file_path').get_parameter_value().string_value

    def publish_cloud(self):
        try:
            # 1. Load data from text file
            data = np.loadtxt(self.file_path)
            points = data[:, :3].astype(np.float32)

            # 2. Create the PointCloud2 message
            msg = PointCloud2()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'map'

            # 3. Define the structure (X, Y, Z)
            msg.height = 1
            msg.width = len(points)
            msg.fields = [
                PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
                PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
                PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            ]
            msg.is_bigendian = False
            msg.point_step = 12
            msg.row_step = msg.point_step * msg.width
            msg.is_dense = True
            msg.data = points.tobytes()

            self.publisher_.publish(msg)
            self.get_logger().info(f'Published {len(points)} points from file.')
        except Exception as e:
            self.get_logger().error(f'Failed to load file: {e}')

def main():
    rclpy.init()
    node = VirtualSensor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()