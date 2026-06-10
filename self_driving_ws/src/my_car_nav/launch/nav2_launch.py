import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Paths to your files
    pkg_share = get_package_share_directory('my_car_nav')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    
    params_file = os.path.join(pkg_share, 'params', 'nav2_params.yaml')

    # 2. Include the standard Nav2 Bringup (but without the map_server)
    # We set 'use_sim_time' to False since you are on a real car
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'params_file': params_file,
            'use_sim_time': 'False'
        }.items()
    )
    '''
    # 3. Your custom Motor Driver node
    motor_driver_node = Node(
        package='my_car_nav',
        executable='motor_driver', # The name from your CMakeLists.txt
        name='motor_driver',
        output='screen'
    )
    '''

    pointcloud_to_gridoccupancy = Node(
    package='my_car_nav',
    executable='pointcloud_to_gridoccupancy',
    name='pointcloud_to_gridoccupancy',
    output='screen'
    )

    # 4. Automatically set the initial pose (Home position)
    # This fires 5 seconds after startup to ensure Nav2 is ready
    set_initial_pose = TimerAction(
        period=5.0,
        actions=[
            ExecuteProcess(
                cmd=['ros2', 'topic', 'pub', '--once', '/initialpose', 
                     'geometry_msgs/msg/PoseWithCovarianceStamped',
                     '"{header: {frame_id: \'map\'}, pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}"'],
                shell=True
            )
        ]
    )

    dummy_data = Node(
        package='my_car_nav',
        executable='dummy_cp.py',
        name='dummy_cloud_publisher',
        output='screen'
    )

    test_car = Node(
        package='my_car_nav',
        executable='test_car.py',
        name='test_car',
        output='screen'
    )

    static_map_to_odom = Node(
    package='tf2_ros',
    executable='static_transform_publisher',
    arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom']
    )

    return LaunchDescription([
        nav2_launch,
        set_initial_pose,
        #pointcloud_to_gridoccupancy,
        #dummy_data,
        test_car,
        static_map_to_odom,
    ])