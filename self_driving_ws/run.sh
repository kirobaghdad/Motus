ros2 launch my_car_nav nav2_vslam_launch2.py
rm -rf build/my_car_nav/ install/my_car_nav/

ros2 run my_car_nav map_loader
ros2 run my_car_nav test_car.py
ros2 run my_car_nav create_map.py

sudo systemctl start mongod
sudo systemctl stop mongod

mongosh
use CarService



colcon build --packages-select my_car_nav
source install/setup.bash

source /opt/ros/humble/setup.bash

ros2 run nav2_map_server map_saver_cli -f my_custom_map

ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.02}}"
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"


ros2 topic pub -1 /user_start std_msgs/msg/Int32 "{data: 0}"

ros2 topic pub -1 /user_state std_msgs/msg/Bool "{data: true}"

ros2 topic pub -1 /backend_poses geometry_msgs/msg/PoseArray "{header: {stamp: {sec: 0, nanosec: 0}, frame_id: 'map'}, poses: [{position: {x: 2.5, y: 2.5, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}},{position: {x: 2.5, y: 2.5, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}, {position: {x: 7.5, y: 7.5, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}]}"