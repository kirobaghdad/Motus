import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction

def generate_launch_description():

    set_initial_pose = ExecuteProcess(
    cmd=['ros2', 'topic', 'pub', '--once', '/initialpose', 'geometry_msgs/msg/PoseWithCovarianceStamped',
         '"{header: {stamp: {sec: 0, nanosec: 0}, frame_id: \'map\'}, '
         'pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, '
         'orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}}}"'],
    shell=True
    )

    return LaunchDescription([
        set_initial_pose
    ])
