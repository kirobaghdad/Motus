#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
import struct

class DummyCloud(Node):
    def __init__(self):
        super().__init__('dummy_cloud_pub')
        self.pub = self.create_publisher(PointCloud2, '/cloud_map', 10)
        self.timer = self.create_timer(1.0, self.publish_cloud)

    def publish_cloud(self):
        msg = PointCloud2()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        
        # Define 10 points in a line (a fake wall)
        points = []
        for i in range(10):
            points.append([1.0, i * 0.1, 0.5]) # x=1.0m away, varying y, z=0.5m height

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
        
        buffer = []
        for p in points:
            buffer += struct.pack('fff', *p)
        msg.data = bytes(buffer)
        
        self.pub.publish(msg)

def main():
    rclpy.init()
    rclpy.spin(DummyCloud())
    rclpy.shutdown()

if __name__ == '__main__':
    main()