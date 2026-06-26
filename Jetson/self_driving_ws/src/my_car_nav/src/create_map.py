#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid, MapMetaData
from tf2_ros import StaticTransformBroadcaster
from geometry_msgs.msg import TransformStamped

import numpy as np

class MapPublisher(Node):
    def __init__(self):
        super().__init__('map_publisher_node')
        
        # 1. Create Latched Publisher for the /map topic
        # QoS (Quality of Service) transient local keeps the last map available for new subscribers
        qos_profile = rclpy.qos.QoSProfile(
            durability=rclpy.qos.QoSDurabilityPolicy.TRANSIENT_LOCAL,
            reliability=rclpy.qos.QoSReliabilityPolicy.RELIABLE,
            depth=1
        )
        self.map_pub = self.create_publisher(OccupancyGrid, '/map', qos_profile)
        
        # 2. Setup Static TF Broadcaster (map -> odom)
        self.tf_broadcaster = StaticTransformBroadcaster(self)
        self.broadcast_static_transform()
        
        # 3. Define Map Properties
        self.resolution = 0.1  # 1 pixel = 10 cm
        self.width = 770       
        self.height = 290
        
        # 4. Generate the Map Data and Publish
        self.publish_map()
        self.get_logger().info("Map and Static Transform successfully published!")

    def broadcast_static_transform(self):
        """Broadcasts the mandatory map -> odom coordinate transform."""
        static_transform = TransformStamped()
        static_transform.header.stamp = self.get_clock().now().to_msg()
        static_transform.header.frame_id = 'map'
        static_transform.child_frame_id = 'odom'
        
        # Assuming odom aligns exactly with map origin initially
        static_transform.transform.translation.x = 0.0
        static_transform.transform.translation.y = 0.0
        static_transform.transform.translation.z = 0.0
        static_transform.transform.rotation.w = 1.0  # No rotation
        
        self.tf_broadcaster.sendTransform(static_transform)

    def publish_map(self):
        """Generates a 2D occupancy grid and publishes it."""
        msg = OccupancyGrid()
        
        # Header
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        
        # Metadata
        msg.info.resolution = self.resolution
        msg.info.width = self.width
        msg.info.height = self.height
        
        # Origin (bottom-left corner of the map in meters)
        msg.info.origin.position.x = 0.0
        msg.info.origin.position.y = 0.0
        msg.info.origin.position.z = 0.0
        msg.info.origin.orientation.w = 1.0

        # Generate Map Data Array (-1: Unknown, 0: Free, 100: Obstacle)
        # Create a 2D grid filled with 0 (Free Space)
        grid = np.full((self.height, self.width), fill_value = -1 ,dtype=np.int8)
        
        # Flatten the 2D array into a 1D list expected by OccupancyGrid
        msg.data = grid.flatten().tolist()
        
        # Publish the map
        self.map_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MapPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()