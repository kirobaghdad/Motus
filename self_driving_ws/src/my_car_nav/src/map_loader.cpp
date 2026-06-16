#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp" // New header for car pose
#include "sensor_msgs/point_cloud2_iterator.hpp"

#include <vector>
#include <algorithm> // For std::fill

class MapLoader : public rclcpp::Node {
public:
    MapLoader() : Node("map_loader") {
        auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local();
        pub_ = this->create_publisher<nav_msgs::msg::OccupancyGrid>("map", qos);
        RCLCPP_INFO(this->get_logger(), "Maploader Node started...");
     
        // Grid Initialization
        grid.info.width = 200;       
        grid.info.height = 200;  
        grid.data.assign(grid.info.width * grid.info.height, 0);
        grid.info.resolution = 0.05; 
        // set bottom left corner of the map to (0,0)
        grid.info.origin.position.x = 0;
        grid.info.origin.position.y = 0;

        grid.header.frame_id = "map"; 
        grid.header.stamp = this->get_clock()->now();

        std::fill(grid.data.begin(), grid.data.end(), 0);
        /*
        // 2. Clear and allocate the exact clean memory space layout directly
        // This builds a clean vector of size 10000 (100x100) filled completely with zeros safely
        grid.data.clear();
        grid.data.resize(grid.info.width * grid.info.height, 0);
        */
        // add objects to the map
        convert_to_occupied(0,0,10,0.5);
        convert_to_occupied(0,9.5,10,0.5);
        convert_to_occupied(0,0.5,0.5,9);
        convert_to_occupied(9.5,0.5,0.5,9);
        convert_to_occupied(4.5,0.5,1,3);
        convert_to_occupied(4.5,6.5,1,3);
        
        pub_->publish(grid);

    }
private:
    void convert_to_occupied(float x,float y, float width,float height){
        // x,y is bottom-left corner
        unsigned int x_start = int(x / grid.info.resolution);
        unsigned int y_start = int(y / grid.info.resolution);
        unsigned int x_end = int((x + width) / grid.info.resolution);
        unsigned int y_end = int((y + height) / grid.info.resolution);
        for (unsigned int i = y_start; i <= y_end; i++) {
            for (unsigned int j = x_start; j <= x_end; j++) {
                size_t index = i * grid.info.width + j;
                if (index < grid.data.size()) {
                    grid.data[index] = 100;
                }
            }
        }
    }
    rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr pub_;
    nav_msgs::msg::OccupancyGrid grid;

};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<MapLoader>());
    rclcpp::shutdown();
    return 0;
}