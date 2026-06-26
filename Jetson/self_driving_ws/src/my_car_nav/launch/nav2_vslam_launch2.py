import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Paths to packages and assets
    my_car_nav_dir = get_package_share_directory('my_car_nav')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    
    # 2. Configurations
    params_file = LaunchConfiguration('params_file', default=os.path.join(my_car_nav_dir, 'params', 'nav2_params3.yaml'))
    
    # 3. Launch Core Nav2 (Bypassing default AMCL and default Map Server validations)
    nav2_bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')), # <-- Change this line!
        launch_arguments={
            'use_sim_time': 'False',
            'params_file': params_file,
            'autostart': 'True'
        }.items()
    )

    # 4. Launch your lightweight simulator Node
    sim_node = Node(
        package='my_car_nav',
        executable='test_car.py', # Ensure chmod +x was run on this script!
        name='test_car',
        output='screen'
    )

    # 5. Launch your C++ MapLoader Node
    map_loader_node = Node(
        package='my_car_nav',
        executable='map_loader',
        name='map_loader',
        output='screen'
    )

    # 6. Optional: Spin up RViz2 preconfigured to show the map and point clouds
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', os.path.join(nav2_bringup_dir, 'rviz', 'nav2_default_view.rviz')],
        output='screen'
    )

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=params_file, description='Full path to the ROS2 parameters file to use for all launched nodes'),
        sim_node,
        map_loader_node,
        nav2_bringup_launch,
        rviz_node
    ])