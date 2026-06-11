#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp" // New header for car pose
#include "sensor_msgs/point_cloud2_iterator.hpp"

using namespace std::chrono_literals;

class CloudToGrid : public rclcpp::Node {
public:
    CloudToGrid() : Node("cloud_to_grid") {
        // 1. Declare and get the camera height parameter (default to 0.5 meters if not set)
        this->declare_parameter<double>("camera_height", 0.17);
        this->get_parameter("camera_height", camera_height_);

        // 2. Subscribe to the cloud map
        sub_cloud_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
            "cloud_point", 10, std::bind(&CloudToGrid::cloud_callback, this, std::placeholders::_1));

        // 3. Subscribe to the car's current pose
        sub_pose_ = this->create_subscription<geometry_msgs::msg::PoseStamped>(
            "car_pose", 10, std::bind(&CloudToGrid::pose_callback, this, std::placeholders::_1));

        // 4. Setup Publisher with Transient Local QoS
        auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local();
        pub_ = this->create_publisher<nav_msgs::msg::OccupancyGrid>("map", qos);
        
        RCLCPP_INFO(this->get_logger(), "Converter Node Started. Camera Height Parameter: %.2f meters", camera_height_);
        
        // Grid Initialization
        grid.info.width = 100;       
        grid.info.height = 100;  
        grid.data.assign(grid.info.width * grid.info.height, 0);
        grid.info.resolution = 0.05; 
    
        grid.info.origin.position.x = -2.5;
        grid.info.origin.position.y = -2.5;
        
        // Initialize car pose to 0 until data arrives
        car_z_ = 0.0;
    }

private:
    void pose_callback(const geometry_msgs::msg::PoseStamped::SharedPtr msg) {
        // Track the car's absolute Z position from the localization node
        car_z_ = msg->pose.position.z;
    }

    void cloud_callback(const sensor_msgs::msg::PointCloud2::SharedPtr msg) {
        // Dynamic parameter updates (allows changing height via ros2 param set while running)
        this->get_parameter("camera_height", camera_height_);

        grid.header = msg->header;
        grid.header.frame_id = "map"; 
        grid.header.stamp = this->get_clock()->now();
        
        // Clear old map values back to 0 (free space) before parsing new cloud
        std::fill(grid.data.begin(), grid.data.end(), 0);

        sensor_msgs::PointCloud2Iterator<float> iter_x(*msg, "x");
        sensor_msgs::PointCloud2Iterator<float> iter_y(*msg, "y");
        sensor_msgs::PointCloud2Iterator<float> iter_z(*msg, "z");

        // Calculate the ground level plane based on car pose and camera offset
        // If point cloud is in camera frame, Z points forward/down depending on orientation.
        // Assuming your point cloud is already in map/base_link frame:
        double ground_level = car_z_ - camera_height_;

        for (; iter_x != iter_x.end(); ++iter_x, ++iter_y, ++iter_z) {
            
            // HEIGHT FILTER REVISION:
            // Filter out ground plane reflections and sky/ceiling points relative to your camera setup
            // Adjust threshold boundaries (e.g., 0.05m above ground to 2.0m above ground)
            double relative_height_from_ground = *iter_z - ground_level;
            
            if (relative_height_from_ground < 0.05 || relative_height_from_ground > 1.5) {
                continue; 
            }

            int col = (*iter_x - grid.info.origin.position.x) / grid.info.resolution;
            int row = (*iter_y - grid.info.origin.position.y) / grid.info.resolution;

            if (col >= 0 && col < (int)grid.info.width && row >= 0 && row < (int)grid.info.height) {
                grid.data[row * grid.info.width + col] = 100; // Obstacle detected
            }
        }
        pub_->publish(grid);
    }

    // Subscriptions & Publishers
    // Renamed sub_ to sub_cloud_ for clarity
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr sub_cloud_;
    rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr sub_pose_;
    rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr pub_;
    
    // Internal state variables
    nav_msgs::msg::OccupancyGrid grid;
    double camera_height_;
    double car_z_;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<CloudToGrid>());
    rclcpp::shutdown();
    return 0;
}