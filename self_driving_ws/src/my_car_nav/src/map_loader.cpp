#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp" // New header for car pose
#include "sensor_msgs/point_cloud2_iterator.hpp"

class MapLoader : public rclcpp::Node {
public:
    MapLoader() : Node("map_loader") {
       auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local();
       pub_ = this->create_publisher<nav_msgs::msg::OccupancyGrid>("map", qos);
       RCLCPP_INFO(this->get_logger(), "Maploader Node started...");
     
       // Grid Initialization
        grid.info.width = 100;       
        grid.info.height = 100;  
        grid.data.assign(grid.info.width * grid.info.height, 0);
        grid.info.resolution = 0.05; 
    
        grid.info.origin.position.x = -2.5;
        grid.info.origin.position.y = -2.5;

        grid.header.frame_id = "map"; 
        grid.header.stamp = this->get_clock()->now();

        std::fill(grid.data.begin(), grid.data.end(), 0);
        // make a square occupied in the middle
        for (int x = 40; x < 60; ++x) {
            for (int y = 40; y < 60; ++y) {
                grid.data[y * grid.info.width + x] = 100;
            }
        }
        pub_->publish(grid);

    }

}