from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='pointcloud_to_laserscan',
            executable='pointcloud_to_laserscan_node',
            name='pointcloud_to_laserscan',
            parameters=[{
                'target_frame': 'base_link', # Flatten relative to the car
                'transform_tolerance': 0.01,
                'min_height': 0.1,  # Ignore the floor
                'max_height': 1.0,  # Ignore the ceiling
                'range_min': 0.2,
                'range_max': 10.0,
                'use_inf': True
            }],
            remappings=[('/cloud_in', '/3d_map'), # Your teammate's topic
                      ('/scan', '/vslam_scan')]  # Your new 2D scan topic
        )
    ])