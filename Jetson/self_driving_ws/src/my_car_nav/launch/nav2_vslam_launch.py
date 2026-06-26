import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Paths to packages and files
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    
    # Launch configurations
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    
    # Create parameter file path for Nav2 (Update this to your custom nav2_params.yaml)
    # By default, we can use Nav2's default navigation parameters
    nav2_params_file = LaunchConfiguration(
        'params_file',
        default=os.path.join(nav2_bringup_dir, 'params', 'nav2_params.yaml')
    )

    # 2. Declare Launch Arguments
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation (Gazebo) clock if true'
    )
    
    declare_params_file = DeclareLaunchArgument(
        'params_file',
        default_value=os.path.join(nav2_bringup_dir, 'params', 'nav2_params.yaml'),
        description='Full path to the ROS2 parameters file to use for all launched nodes'
    )

    # 3. pointcloud_to_laserscan Node
    # Converts your 3D V-SLAM pointcloud into a 2D LaserScan for Nav2 Costmaps
    pointcloud_to_laserscan_node = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        remappings=[
            # CHANGE 'cloud_in' to your actual V-SLAM or Camera pointcloud topic
            ('cloud_point', '/vslam/pointcloud'), 
            ('scan', '/scan')
        ],
        parameters=[{
            'target_frame': 'base_link', # Transform cloud to robot base frame
            'transform_tolerance': 0.01,
            'min_height': 0.1,           # Minimum height of points to consider (meters above ground)
            'max_height': 1.0,           # Maximum height of points to consider
            'angle_min': -3.14159,       # -180 degrees
            'angle_max': 3.14159,        # 180 degrees
            'angle_increment': 0.0087,   # M_PI/360.0 (Resolution)
            'scan_time': 0.3333,
            'range_min': 0.45,
            'range_max': 10.0,
            'use_inf': True,
            'inf_epsilon': 1.0
        }],
        output='screen'
    )

    # 4. Include Nav2 Bringup (SLAM / Exploration mode)
    # We use navigation_launch.py instead of bringup_launch.py because 
    # we don't want the static map_server or AMCL. V-SLAM provides both Map and Odom!
    nav2_navigation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': nav2_params_file,
        }.items()
    )

    # Build Launch Description
    ld = LaunchDescription()
    
    # Add arguments
    ld.add_action(declare_use_sim_time)
    ld.add_action(declare_params_file)
    
    # Add nodes and included launch files
    ld.add_action(pointcloud_to_laserscan_node)
    ld.add_action(nav2_navigation_launch)

    return ld