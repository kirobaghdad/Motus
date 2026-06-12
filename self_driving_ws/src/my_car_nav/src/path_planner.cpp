#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp" // New header for car pose
#include "nav2_msgs/action/navigate_to_pose.hpp"
#include "nav_msgs/msg/path.hpp"

using namespace std::chrono_literals;

class PathPlanner : public rclcpp::Node {
public:
    PathPlanner() : Node("path_planner") {
        RCLCPP_INFO(this->get_logger(), "PathPlanner Node started...");
        
    }
}