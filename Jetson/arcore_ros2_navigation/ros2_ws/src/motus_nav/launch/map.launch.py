import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = get_package_share_directory('motus_nav')
    rtabmap_launch = os.path.join(
        get_package_share_directory('rtabmap_launch'), 'launch', 'rtabmap.launch.py'
    )

    args = [
        DeclareLaunchArgument('port', default_value='5050'),
        DeclareLaunchArgument('database', default_value='~/.ros/motus_map.db'),
        DeclareLaunchArgument('hardware', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='false'),
        DeclareLaunchArgument('rtabmap_viz', default_value='false'),
        DeclareLaunchArgument('web_teleop', default_value='false'),
        DeclareLaunchArgument('teleop_port', default_value='5000'),
        DeclareLaunchArgument('camera_x', default_value='0.20'),
        DeclareLaunchArgument('camera_y', default_value='0.0'),
        DeclareLaunchArgument('camera_z', default_value='0.15'),
        DeclareLaunchArgument('camera_roll', default_value='0.0'),
        DeclareLaunchArgument('camera_pitch', default_value='0.0'),
        DeclareLaunchArgument('camera_yaw', default_value='0.0'),
        DeclareLaunchArgument('odom_scale', default_value='1.12'),
    ]

    camera = {
        'camera_x': ParameterValue(LaunchConfiguration('camera_x'), value_type=float),
        'camera_y': ParameterValue(LaunchConfiguration('camera_y'), value_type=float),
        'camera_z': ParameterValue(LaunchConfiguration('camera_z'), value_type=float),
        'camera_roll': ParameterValue(LaunchConfiguration('camera_roll'), value_type=float),
        'camera_pitch': ParameterValue(LaunchConfiguration('camera_pitch'), value_type=float),
        'camera_yaw': ParameterValue(LaunchConfiguration('camera_yaw'), value_type=float),
    }

    phone = Node(
        package='motus_nav', executable='phone_bridge', name='phone', output='screen',
        parameters=[{
            'listen_port': ParameterValue(LaunchConfiguration('port'), value_type=int),
            **camera,
            'odom_scale': ParameterValue(LaunchConfiguration('odom_scale'), value_type=float),
            'planar_mode': True,
            'publish_odom_tf': True,
        }],
    )
    safety = Node(
        package='motus_nav', executable='safety', name='safety', output='screen',
        parameters=[camera],
    )
    car = Node(
        package='motus_nav', executable='car', name='car', output='screen',
        parameters=[
            os.path.join(share, 'config', 'car.yaml'),
            {
                'hardware_enabled': ParameterValue(LaunchConfiguration('hardware'), value_type=bool),
                'angular_input_mode': 'steering',
                'steering_sign': 1.0,
                'minimum_drive_pwm_percent': 35.0,
                'max_pwm_percent': 70.0,
            },
        ],
    )
    rviz = Node(
        package='rviz2', executable='rviz2', name='rviz2', output='screen',
        condition=IfCondition(LaunchConfiguration('rviz')),
        arguments=['-d', os.path.join(share, 'rviz', 'phone_debug.rviz')],
    )
    web_teleop = Node(
        package='motus_nav', executable='web_teleop', name='web_teleop', output='screen',
        condition=IfCondition(LaunchConfiguration('web_teleop')),
        parameters=[{
            'port': ParameterValue(LaunchConfiguration('teleop_port'), value_type=int),
            'output_topic': '/cmd_vel',
            'max_linear_mps': 0.12,
            'default_command_max_linear_mps': 0.10,
        }],
    )
    rtabmap = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(rtabmap_launch),
        launch_arguments={
            'depth': 'false',
            'stereo': 'false',
            'subscribe_rgb': 'true',
            'subscribe_scan_cloud': 'true',
            'scan_cloud_topic': '/phone/points',
            'visual_odometry': 'false',
            'rgb_topic': '/phone/image',
            'camera_info_topic': '/phone/camera_info',
            'odom_topic': '/phone/odom',
            'frame_id': 'base_link',
            'map_frame_id': 'map',
            'map_topic': '/map',
            'database_path': LaunchConfiguration('database'),
            'rtabmap_viz': LaunchConfiguration('rtabmap_viz'),
            'rviz': 'false',
            'approx_sync': 'true',
            'approx_sync_max_interval': '0.12',
            'topic_queue_size': '10',
            'sync_queue_size': '20',
            'qos_image': '2',
            'qos_scan': '2',
            'qos_odom': '1',
            'qos_camera_info': '2',
            'args': (
                '-d --Grid/FromDepth false --Grid/3D false '
                '--Grid/CellSize 0.05 --Grid/RangeMax 3.0 '
                '--Grid/MinGroundHeight -0.10 --Grid/MaxGroundHeight 0.18 '
                '--Grid/MaxObstacleHeight 1.20 --Grid/MinClusterSize 25 '
                '--Grid/NoiseFilteringRadius 0.12 --Grid/NoiseFilteringMinNeighbors 5 '
                '--Grid/FlatObstacleDetected false --Grid/RayTracing true '
                '--RGBD/CreateOccupancyGrid true '
                '--Reg/Strategy 2 --Reg/Force3DoF true --Optimizer/Slam2D true '
                '--RGBD/LinearUpdate 0.10 '
                '--RGBD/AngularUpdate 0.10 --RGBD/NeighborLinkRefining true '
                '--Vis/MinInliers 15'
            ),
        }.items(),
    )
    return LaunchDescription(args + [phone, safety, car, rviz, web_teleop, rtabmap])
