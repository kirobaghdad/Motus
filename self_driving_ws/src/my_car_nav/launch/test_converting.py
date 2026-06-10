from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    # 1. Define the name of the argument
    path_arg = DeclareLaunchArgument(
        'map_path',
        default_value='/home/ali/self_driving_ws/src/my_car_nav/maps/biwi_hotel_train.txt',
        description='Full path to the pointcloud text file'
    )

    # 2. Create a configuration variable to hold the value
    map_path_config = LaunchConfiguration('map_path')
    return LaunchDescription([
        # 1. The C++ Converter Node
        Node(
            package='my_car_nav',
            executable='pointcloud_to_gridoccupancy',
            name='converter_node',
            output='screen'
        ),



        # 2. The Python Dummy Producer
        Node(
            package='my_car_nav',
            executable='load_cp.py',
            name='virtual_publisher',
            parameters=[{'file_path': map_path_config}],
            output='screen'
        ),
        
        # 3. Static TF (Crucial for RViz to work)
        # This links the 'map' frame to the 'base_link' frame
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments=['0', '0', '0', '0', '0', '0', 'map', 'base_link']
        )
    ])