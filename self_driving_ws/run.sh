ros2 launch my_car_nav nav2_vslam_launch2.py
rm -rf build/my_car_nav/ install/my_car_nav/

ros2 run my_car_nav map_loader
ros2 run my_car_nav test_car.py


colcon build --packages-select my_car_nav
source install/setup.bash

source /opt/ros/humble/setup.bash

ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.02}}"
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"