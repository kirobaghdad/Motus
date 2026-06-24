import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Locate your configuration package paths
    # Change 'my_robot_package' to match your actual ROS 2 workspace package name!
    pkg_share = get_package_share_directory('my_robot_package')
    nav2_bringup_share = get_package_share_directory('nav2_bringup')
    
    # Path to your calibrated nav2 parameters file containing your adjusted velocities
    nav2_params_file = os.path.join(pkg_share, 'config', 'nav2_params.yaml')

    # =========================================================================
    # NODE 1: Static Transform Publisher (Camera to Base Link)
    # =========================================================================
    # Parameters: x y z yaw pitch roll frame_id child_frame_id
    # Calibrate these values based on where the camera is physically mounted on your chassis:
    # e.g., if camera is 20cm forward and 15cm high from the center of axle: x=0.2, z=0.15
    static_tf_node = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='camera_to_base_link_tf',
        arguments=['0.2', '0.0', '0.15', '0.0', '0.0', '0.0', 'base_link', 'camera_frame']
    )

    # =========================================================================
    # NODE 2: Cloud to Grid Map Converter
    # =========================================================================
    cloud_to_grid_node = Node(
        package='my_robot_package',
        executable='cloud_to_grid_converter',  # Name of your compiled binary node
        name='cloud_to_grid_converter',
        output='screen'
    )

    # =========================================================================
    # NODE 3: State Machine Path Handler
    # =========================================================================
    path_handler_node = Node(
        package='my_robot_package',
        executable='path_handler',             # Your C++ compiled state machine binary
        name='path_handler',
        output='screen'
    )

    # =========================================================================
    # NODE 4: Real Car Hardware Bridge (Substitutes Sim/Test Code)
    # =========================================================================
    car_move_bridge_node = Node(
        package='my_robot_package',
        executable='car_move_bridge.py',       # Your Python bridge script
        name='car_move_bridge',
        output='screen'
    )

    # =========================================================================
    # INCLUSION 5: Official Nav2 Bringup Launch
    # =========================================================================
    # This includes the full Nav2 navigation system (Planner, Controller, Recoveries)
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_share, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'params_file': nav2_params_file,
            'use_sim_time': 'False'            # FORCED TO FALSE: running on physical hardware
        }.items()
    )

    # Build Launch Description structure
    return LaunchDescription([
        static_tf_node,
        cloud_to_grid_node,
        path_handler_node,
        car_move_bridge_node,
        nav2_launch
    ])