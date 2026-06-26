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
    nav2_share = get_package_share_directory('nav2_bringup')

    args = [
        DeclareLaunchArgument('port', default_value='5050'),
        DeclareLaunchArgument('database', default_value='~/.ros/motus_map.db'),
        DeclareLaunchArgument('hardware', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='false'),
        DeclareLaunchArgument('web_nav', default_value='true'),
        DeclareLaunchArgument('web_nav_port', default_value='5001'),
        DeclareLaunchArgument('camera_x', default_value='0.20'),
        DeclareLaunchArgument('camera_y', default_value='0.0'),
        DeclareLaunchArgument('camera_z', default_value='0.15'),
        DeclareLaunchArgument('camera_roll', default_value='0.0'),
        DeclareLaunchArgument('camera_pitch', default_value='0.0'),
        DeclareLaunchArgument('camera_yaw', default_value='0.0'),
        DeclareLaunchArgument('odom_scale', default_value='1.12'),
        DeclareLaunchArgument('map_to_odom_x', default_value='0.0'),
        DeclareLaunchArgument('map_to_odom_y', default_value='0.0'),
        DeclareLaunchArgument('map_to_odom_yaw', default_value='0.0'),
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
                'angular_input_mode': 'yaw_rate',
                'allow_reverse': False,
                'minimum_drive_pwm_percent': 50.0,
                'max_pwm_percent': 80.0,
                'motor_ramp_step_percent': 5.0,
                'motor_ramp_interval_sec': 0.04,
            },
        ],
    )
    rtabmap_args = (
        '--Grid/FromDepth false --Grid/3D false '
        '--Grid/CellSize 0.05 --Grid/RangeMax 3.0 '
        '--Grid/MinGroundHeight -0.10 --Grid/MaxGroundHeight 0.18 '
        '--Grid/MaxObstacleHeight 1.20 --Grid/MinClusterSize 25 '
        '--Grid/NoiseFilteringRadius 0.12 --Grid/NoiseFilteringMinNeighbors 5 '
        '--Grid/FlatObstacleDetected false --Grid/RayTracing true '
        '--RGBD/CreateOccupancyGrid true '
        '--Reg/Strategy 2 --Reg/Force3DoF true --Optimizer/Slam2D true '
        '--Mem/IncrementalMemory false --Mem/InitWMWithAllNodes true '
        '--Mem/LocalizationDataSaved false'
    )
    rtabmap = Node(
        package='rtabmap_slam', executable='rtabmap', namespace='rtabmap',
        name='rtabmap', output='screen', emulate_tty=True,
        parameters=[{
            'subscribe_depth': False,
            'subscribe_rgbd': False,
            'subscribe_rgb': True,
            'subscribe_stereo': False,
            'subscribe_scan': False,
            'subscribe_scan_cloud': True,
            'subscribe_user_data': False,
            'subscribe_odom_info': False,
            'frame_id': 'base_link',
            'map_frame_id': 'map',
            'publish_tf': False,
            'database_path': LaunchConfiguration('database'),
            'approx_sync': True,
            'approx_sync_max_interval': 0.12,
            'topic_queue_size': 10,
            'sync_queue_size': 20,
            'qos_image': 2,
            'qos_scan': 2,
            'qos_odom': 1,
            'qos_camera_info': 2,
            'wait_for_transform': 0.2,
            'map_always_update': True,
            'map_empty_ray_tracing': False,
            'Mem/IncrementalMemory': 'false',
            'Mem/InitWMWithAllNodes': 'true',
            'Mem/LocalizationDataSaved': 'false',
        }],
        remappings=[
            ('map', '/map'),
            ('rgb/image', '/phone/image'),
            ('rgb/camera_info', '/phone/camera_info'),
            ('scan_cloud', '/phone/points'),
            ('odom', '/phone/odom'),
            ('initialpose', '/initialpose'),
            ('goal_out', '/goal_pose'),
        ],
        arguments=[rtabmap_args],
    )
    map_to_odom = Node(
        package='tf2_ros', executable='static_transform_publisher',
        name='map_to_odom', output='screen',
        arguments=[
            '--x', LaunchConfiguration('map_to_odom_x'),
            '--y', LaunchConfiguration('map_to_odom_y'),
            '--z', '0.0',
            '--roll', '0.0',
            '--pitch', '0.0',
            '--yaw', LaunchConfiguration('map_to_odom_yaw'),
            '--frame-id', 'map',
            '--child-frame-id', 'odom',
        ],
    )
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_share, 'launch', 'navigation_launch.py')),
        launch_arguments={
            'use_sim_time': 'false',
            'autostart': 'true',
            'params_file': os.path.join(share, 'config', 'nav2.yaml'),
            'use_composition': 'False',
        }.items(),
    )
    rviz = Node(
        package='rviz2', executable='rviz2', name='rviz2', output='screen',
        condition=IfCondition(LaunchConfiguration('rviz')),
        arguments=['-d', os.path.join(share, 'rviz', 'phone_debug.rviz')],
    )
    web_nav = Node(
        package='motus_nav', executable='web_nav', name='web_nav', output='screen',
        condition=IfCondition(LaunchConfiguration('web_nav')),
        parameters=[{
            'port': ParameterValue(LaunchConfiguration('web_nav_port'), value_type=int),
            'map_topic': '/map',
            'goal_topic': '/goal_pose',
            'map_frame': 'map',
            'base_frame': 'base_link',
        }],
    )
    return LaunchDescription(args + [phone, safety, car, rviz, web_nav, rtabmap, map_to_odom, nav2])
