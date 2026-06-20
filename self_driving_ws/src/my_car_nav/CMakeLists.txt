cmake_minimum_required(VERSION 3.8)
project(my_car_nav)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rclpy REQUIRED)
find_package(tf2_msgs REQUIRED)
find_package(map_msgs REQUIRED)
find_package(nav2_msgs REQUIRED)
find_package(tf2_sensor_msgs REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(tf2_ros REQUIRED)

add_executable(pointcloud_to_gridoccupancy src/pointcloud_to_gridoccupancy.cpp)

add_executable(path_planner src/path_planner.cpp)
add_executable(path_handler src/path_handler.cpp)
add_executable(map_loader src/map_loader.cpp)

ament_target_dependencies(path_handler
  rclcpp
  nav_msgs
  geometry_msgs
  nav2_msgs
  rclcpp_action
  tf2_geometry_msgs
  tf2_sensor_msgs
  tf2_ros
)

ament_target_dependencies(path_planner
  rclcpp
  nav_msgs
  nav2_msgs
  geometry_msgs
)

ament_target_dependencies(map_loader
  rclcpp
  nav_msgs
  sensor_msgs
  geometry_msgs
)

ament_target_dependencies(pointcloud_to_gridoccupancy
  rclcpp
  nav_msgs
  sensor_msgs
  geometry_msgs
  tf2_geometry_msgs
  tf2_sensor_msgs
  tf2_ros
)

install(TARGETS
  map_loader
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS
  src/path_planner2.py
  DESTINATION lib/${PROJECT_NAME}
)

# 4. Install C++ executable
install(TARGETS
  pointcloud_to_gridoccupancy
  DESTINATION lib/${PROJECT_NAME}
)

# 5. Install Python scripts
install(PROGRAMS
  src/dummy_cp.py
  DESTINATION lib/${PROJECT_NAME}
)

# 6. Install Python scripts
install(PROGRAMS
  src/load_cp.py
  DESTINATION lib/${PROJECT_NAME}
)

# 7. Install Python scripts
install(PROGRAMS
  src/test_car.py
  DESTINATION lib/${PROJECT_NAME}
)
# 8. Install Python scripts
install(PROGRAMS
  src/backend_communication.py
  DESTINATION lib/${PROJECT_NAME}
)
# 9. Install Launch, Maps, and Params folders
install(DIRECTORY
  launch
  maps
  params
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
