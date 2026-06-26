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
    params_file = LaunchConfiguration('params_file', default=os.path.join(my_car_nav_dir, 'params', 'nav2_params.yaml'))
    
    # Define absolute path to your baseline map file cleanly
    map_yaml_file = os.path.join(my_car_nav_dir, 'maps','test_map', 'test_map.yaml')
    
    # 3. Launch Core Nav2 (Handles costmaps, planners, controllers)
    nav2_bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')),
        launch_arguments={
            'use_sim_time': 'False',
            'params_file': params_file,
            'autostart': 'True'
        }.items()
    )

    # 4. CRUCIAL FIX: Launch the Nav2 Map Server explicitly to publish 'initial_map'
    map_server_node = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[params_file, {'yaml_filename': map_yaml_file}]
    )

    # Manage lifecycle for map_server since we are not using AMCL
    lifecycle_manager_node = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        output='screen',
        parameters=[{
            'use_sim_time': False,
            'autostart': True,
            'node_names': ['map_server']
        }]
    )

    # 5. Launch your lightweight simulator Node
    sim_node = Node(
        package='my_car_nav',
        executable='test_car.py', # Ensure chmod +x was run on this script in your src/ folder!
        name='test_car',
        output='screen'
    )

    # 6. Launch your C++ Custom Map Converter Node
    cloud_to_grid_node = Node(
        package='my_car_nav',
        executable='pointcloud_to_gridoccupancy',
        name='cloud_to_grid_converter',
        output='screen'
    )

    # 7. Spin up RViz2 preconfigured
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', os.path.join(nav2_bringup_dir, 'rviz', 'nav2_default_view.rviz')],
        output='screen'
    )

    # 8. Launch the pathHandler Node
    path_handler_node = Node(
        package='my_car_nav',
        executable='path_handler',
        name='path_handler',
        parameters=[{
            'max_window_size': 16.0,
            'max_wait_minutes': 3,
            'max_distance_from_obstacle': 1.0,
            'car_width': 0.3,
        }],
        output='screen'
    )

    communication_node = Node(
        package='my_car_nav',
        executable='backend_communication.py',
        name='backend_communication',
        output='screen'
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file', 
            default_value=os.path.join(my_car_nav_dir, 'params', 'nav2_params.yaml'), 
            description='Full path to the ROS2 parameters file to use'
        ),
        sim_node,
        map_server_node,          
        lifecycle_manager_node,   
        cloud_to_grid_node,       
        nav2_bringup_launch,
        rviz_node,
        path_handler_node,
        communication_node
    ])