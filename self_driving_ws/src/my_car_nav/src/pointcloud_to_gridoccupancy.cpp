#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp" // New header for car pose
#include "sensor_msgs/point_cloud2_iterator.hpp"
#include <unordered_set>
#include <vector>
#include <tf2_ros/transform_listener.h>
#include <tf2_ros/buffer.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <tf2_sensor_msgs/tf2_sensor_msgs.hpp>

using namespace std::chrono_literals;

class CloudToGrid : public rclcpp::Node {
public:
    CloudToGrid() : Node("cloud_to_grid") {

        // 1. Subscribe to the cloud map
        sub_cloud_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
            "cloud_points", 10, std::bind(&CloudToGrid::cloud_callback, this, std::placeholders::_1));

        // 2. Setup Publisher with Transient Local QoS
        auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local();
        map_pub_ = this->create_publisher<nav_msgs::msg::OccupancyGrid>("map", qos);

        // 3. Setup TF buffer and listener
        tf_buffer_ = std::make_unique<tf2_ros::Buffer>(this->get_clock());
        tf_listener_ = std::make_shared<tf2_ros::TransformListener>(*tf_buffer_);

        // 4. Create a listner to initial map
        sub_initial_map_ = this->create_subscription<nav_msgs::msg::OccupancyGrid>(
            "initial_map", 10, std::bind(&CloudToGrid::initial_map_callback, this, std::placeholders::_1));
        
        RCLCPP_INFO(this->get_logger(), "Converter Node Started.");
        
    }

private:

    void initial_map_callback(const nav_msgs::msg::OccupancyGrid::SharedPtr msg) {
        grid = *msg;
        initial_map_received = true;
        // send initial map to the publisher do not make nav2 wait untill cloud come
        map_pub_->publish(grid);
    }

    void cloud_callback(const sensor_msgs::msg::PointCloud2::SharedPtr msg) {

        if (!initial_map_received) {
            RCLCPP_WARN(this->get_logger(), "Initial map not received yet, skipping cloud callback");
            return;
        }

        geometry_msgs::msg::TransformStamped car_transform;
        
        try {
            // Look up the transform from the car to the map with a 20ms wait timeout
            car_transform = tf_buffer_->lookupTransform("map", "base_link", tf2::TimePointZero, tf2::durationFromSec(0.02));
    
        } catch (const tf2::TransformException &ex) {
            // Throttling the warning ensures your terminal isn't flooded if a frame drops under heavy CPU load
            RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 5000, 
                         "Syncing car frames... Transform lag: %s", ex.what());
            return;
        }
        
        // Calculate map coordinates of car position
        double car_x = car_transform.transform.translation.x;
        double car_y = car_transform.transform.translation.y;
        
        int car_col = (car_x - grid.info.origin.position.x) / grid.info.resolution;
        int car_row = (car_y - grid.info.origin.position.y) / grid.info.resolution;

        if (car_col < 0 || car_col >= (int)grid.info.width || car_row < 0 || car_row >= (int)grid.info.height) {
            RCLCPP_WARN(this->get_logger(), "Car position is outside the grid");
            return;
        }

        // 2. Transform the incoming point cloud container into the "map" frame
        sensor_msgs::msg::PointCloud2 transformed_cloud;
        try {
            tf_buffer_->transform(*msg, transformed_cloud, "map", tf2::durationFromSec(0.02));
        } catch (const tf2::TransformException &ex) {
            RCLCPP_ERROR_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                                  "Could not transform pointcloud to map: %s", ex.what());
            return;
        }

        grid.header = transformed_cloud.header;

        sensor_msgs::PointCloud2Iterator<float> iter_x(transformed_cloud, "x");
        sensor_msgs::PointCloud2Iterator<float> iter_y(transformed_cloud, "y");
        sensor_msgs::PointCloud2Iterator<float> iter_z(transformed_cloud, "z");

        std::unordered_set<int> occupied_cells;

        for (; iter_x != iter_x.end(); ++iter_x, ++iter_y, ++iter_z) {
            
            if (*iter_z < 0.02 && *iter_z > -0.02) {
                // skip point if it is too close to the ground may be feature in ground itself
                continue; 
            }

            int col = (*iter_x - grid.info.origin.position.x) / grid.info.resolution;
            int row = (*iter_y - grid.info.origin.position.y) / grid.info.resolution;
            // make sure the point is inside the grid
            if (col < 0 || col >= (int)grid.info.width || row < 0 || row >= (int)grid.info.height) {
                continue;
            }
            int index = row * grid.info.width + col;
            occupied_cells.insert(index);
        }
        // loop over occupied cell and ray trace from car to occupied cell
        for (const auto& index : occupied_cells){
            int col = index % grid.info.width;
            int row = index / grid.info.width;
            trace_line(car_col, car_row, col, row, occupied_cells);
        }
        map_pub_->publish(grid);
    }
    // Midpoint Bresenham's Line Drawing algorithm but for tracing line from car to point cloud
    void trace_line(int x1, int y1, int x2, int y2, std::unordered_set<int>& occupied_cells){
        if (abs(x2 - x1) > abs(y2 - y1)){
            trace_line_along_x(x1, y1, x2, y2, occupied_cells);
        } else {
            trace_line_along_y(x1, y1, x2, y2, occupied_cells);
        }
    }
    void trace_line_along_y(int x1, int y1, int x2, int y2, std::unordered_set<int>& occupied_cells){
        // solve problem of swapping direction
        bool swapped = false;
        std::vector<int> indices;
        if (y1 > y2) {
            // swap
            int temp = y1;
            y1 = y2;
            y2 = temp;
            temp = x1;
            x1 = x2;
            x2 = temp;
            swapped = true;
        }
        int dx = x2 - x1;
        int dy = y2 - y1;
        int change = (dx > 0) ? 1 : -1;
        dx *= change;
        int f = dy - 2 * dx;
        int x = x1;
        for (int y = y1; y < y2; y++) {
            indices.push_back(y * grid.info.width + x);
            if (f < 0) {
                x += change;
                f += 2 * dy - 2 * dx;
            } else {
                f += -2 * dx;
            }
        }
        handle_cells(indices, swapped, occupied_cells);
    }
    void trace_line_along_x(int x1, int y1, int x2, int y2, std::unordered_set<int>& occupied_cells){
        // solve problem of swaping direction
        bool swapped = false;
        std::vector<int> indices;
        if (x1 > x2) {
            // swap
            int temp = y1;
            y1 = y2;
            y2 = temp;
            temp = x1;
            x1 = x2;
            x2 = temp;
            swapped = true;
        }
        int dx = x2 - x1;
        int dy = y2 - y1;
        int change = (dy > 0) ? 1 : -1;
        dy *= change;
        int f = dx - 2 * dy;
        int y = y1;
        for (int x = x1; x < x2; x++) {
            indices.push_back(y * grid.info.width + x);
            if (f < 0) {
                y += change;
                f += 2 * dx - 2 * dy;
            } else {
                f += -2 * dy;
            }
        }  
        handle_cells(indices, swapped, occupied_cells);  
    }
    void handle_cells(std::vector<int>& indices, bool swapped, std::unordered_set<int>& occupied_cells){
        size_t start = 0;
        size_t end = indices.size() - 1;
        if (swapped){
            start = indices.size() - 1;
            end = 0;
        }
        size_t i = start;
        while (i != end){
            int index = indices[i];
            if (grid.data[index] == 100 && occupied_cells.count(index) > 0 ){
                // this is not dynamic object, it is static object
                break;
            }
            grid.data[index] = 0;
            if (swapped){
                i--;
            } else {
                i++;
            }
        }
        grid.data[indices[end]] = 100;
    }

    // Subscriptions & Publishers
    // Renamed sub_ to sub_cloud_ for clarity
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr sub_cloud_;
    rclcpp::Publisher<nav_msgs::msg::OccupancyGrid>::SharedPtr map_pub_;
    rclcpp::Subscription<nav_msgs::msg::OccupancyGrid>::SharedPtr sub_initial_map_;
    
    // Internal state variables
    nav_msgs::msg::OccupancyGrid grid;  

    // TF buffer and listener
    std::unique_ptr<tf2_ros::Buffer> tf_buffer_;
    std::shared_ptr<tf2_ros::TransformListener> tf_listener_;
    bool initial_map_received = false;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<CloudToGrid>());
    rclcpp::shutdown();
    return 0;
}