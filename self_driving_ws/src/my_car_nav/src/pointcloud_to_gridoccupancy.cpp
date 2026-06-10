#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"
#include "sensor_msgs/point_cloud2_iterator.hpp"

// FIX 1: Add this to use '500ms'
using namespace std::chrono_literals;

class CloudToGrid : public rclcpp::Node {
public:
    CloudToGrid() : Node("cloud_to_grid") {
        // Use the new topic name we agreed on: "cloud_map"
        sub_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
            "cloud_map", 10, std::bind(&CloudToGrid::callback, this, std::placeholders::_1));

        // FIX 2: Set QoS to Transient Local so RViz finds the map immediately
        auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local();
        pub_ = this->create_publisher<nav_msgs::msg::OccupancyGrid>("map", qos);
        
        // FIX 3: REMOVED the timer. The Subscriber handles the execution.
        RCLCPP_INFO(this->get_logger(), "Converter Node Started. Waiting for cloud_map...");
        
        grid.info.width = 100;       
        grid.info.height = 100;  
        grid.data.assign(grid.info.width * grid.info.height, 0);
        
        grid.info.resolution = 0.2; 
    
        grid.info.origin.position.x = -2.5;
        grid.info.origin.position.y = -2.5;
        
    }

private:
    void callback(const sensor_msgs::msg::PointCloud2::SharedPtr msg) {
        grid.header = msg->header;
        grid.header.frame_id = "map"; // Ensure this matches Fixed Frame in RViz
        grid.header.stamp = this->get_clock()->now();
        
        sensor_msgs::PointCloud2Iterator<float> iter_x(*msg, "x");
        sensor_msgs::PointCloud2Iterator<float> iter_y(*msg, "y");
        sensor_msgs::PointCloud2Iterator<float> iter_z(*msg, "z");

        for (; iter_x != iter_x.end(); ++iter_x, ++iter_y, ++iter_z) {
            // Filter height: 0.02 to 1.0 meters
            if (*iter_z < 0.01 || *iter_z > 1.0) continue;

            int col = (*iter_x - grid.info.origin.position.x) / grid.info.resolution;
            int row = (*iter_y - grid.info.origin.position.y) / grid.info.resolution;

            if (col >= 0 && col < (int)grid.info.width && row >= 0 && row < (int)grid.info.height) {
                grid.data[row * grid.info.width + col] = 100; 
            }
        }
        pub_->publish(grid);
    }

    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr sub_;
    rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr pub_;
    nav_msgs::msg::OccupancyGrid grid;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<CloudToGrid>());
    rclcpp::shutdown();
    return 0;
}