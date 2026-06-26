#include <memory>
#include <rclcpp/rclcpp.hpp>
#include "geometry_msgs/msg/pose_array.hpp"
#include "nav_msgs/msg/occupancy_grid.hpp"
#include "nav2_msgs/action/navigate_to_pose.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "std_msgs/msg/bool.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "std_msgs/msg/int32.hpp"
#include <queue>
#include <string>
#include <tf2_ros/transform_listener.h>
#include <tf2_ros/buffer.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <tf2_sensor_msgs/tf2_sensor_msgs.hpp>

using namespace std::chrono_literals;

class PathHandler : public rclcpp::Node {
public:
    
    enum class State {
        IDLE = 0,
        SEND_GOAL = 1,
        WAIT_FEEDBACK = 2,
        WAIT_USER = 3
    };

    enum class GoalStatus {
        SUCCEEDED = 0,
        ABORTED = 1,
        CANCELED = 2,
        UNKNOWN = 3
    };
        
    PathHandler() : Node("path_handler") {
        // declare parameters for node 
        this->declare_parameter<double>("max_window_size", 16.0);
        this->declare_parameter<int>("max_wait_minutes", 3);
        this->declare_parameter<float>("max_distance_from_obstacle", 1);
        this->declare_parameter<float>("car_width", 0.3);
        // Create a subscriber to the map topic
        map_sub_ = this->create_subscription<nav_msgs::msg::OccupancyGrid>(
            "map", 10, std::bind(&PathHandler::map_callback, this, std::placeholders::_1));
        // Create subscriber to backend_poses topic
        backend_poses_sub_ = this->create_subscription<geometry_msgs::msg::PoseArray>(
            "backend_poses", 10, std::bind(&PathHandler::backend_poses_callback, this, std::placeholders::_1));
        // Create a client for the NavigateToPose action
        action_client_ = rclcpp_action::create_client<nav2_msgs::action::NavigateToPose>(this, "navigate_to_pose");

        // Create a timer to send goals periodically
        timer_ = this->create_wall_timer(100ms, std::bind(&PathHandler::finite_state_machine, this));

        // Create a subscriber to the user_state topic
        user_state_sub_ = this->create_subscription<std_msgs::msg::Bool>("user_state", 10, std::bind(&PathHandler::user_state_callback, this, std::placeholders::_1));
        // Create a Subscriber to the user_start topic
        user_start_sub_ = this->create_subscription<std_msgs::msg::Int32>("user_start", 10, std::bind(&PathHandler::user_start_callback, this, std::placeholders::_1));
        // Create a Publisher to tell backend if trip finished or canceled in both cases it is ended
        trip_status_pub_ = this->create_publisher<std_msgs::msg::Bool>("trip_status", 10);

        tf_buffer_ = std::make_unique<tf2_ros::Buffer>(this->get_clock());
        tf_listener_ = std::make_shared<tf2_ros::TransformListener>(*tf_buffer_);
    }

private:
    void finite_state_machine(){
        switch (state_machine) {
            case State::IDLE:
                idle_state();
                break;
            case State::SEND_GOAL:
                send_goal_state();
                break;
            case State::WAIT_FEEDBACK:
                //wait_feedback_state();
                break;
            case State::WAIT_USER:
                wait_user_state();
                break;
            default:
                break;
        }
    }
    void idle_state(){
        if (user_start_index == -1 || path_queue.empty()) {
            return;
        }
        path_current_index = 0;
        resend_flag = false;
        goal_status = GoalStatus::UNKNOWN;
        waiting_time = 0;
        user_state = false;
        state_machine = State::SEND_GOAL;
    }
    //void wait_feedback_state(){}
    void wait_user_state(){
        int max_wait_time = 3;
        this->get_parameter("max_wait_minutes", max_wait_time);
        if (user_state) {
            RCLCPP_INFO(this->get_logger(), "User confirmed presence! Advancing to next waypoint.");
            user_state = false; // Reset toggle
            state_machine = State::SEND_GOAL;
            return;
        }
        // max wait time is 3 minutes
        if (waiting_time > max_wait_time * 600) {
            RCLCPP_INFO(this->get_logger(), "User not in the car for %d minutes, ending trip!", max_wait_time);
            trip_status_pub_->publish(std_msgs::msg::Bool().set__data(false));
            state_machine = State::IDLE;
            reset_variables();
            return;
        }
        waiting_time++;
    }
    int get_index(geometry_msgs::msg::Pose pose){
        float x = pose.position.x;
        float y = pose.position.y;
        size_t width = map.info.width;
        size_t height = map.info.height;
        float resolution = map.info.resolution;
        int x_index = (x - map.info.origin.position.x) / resolution;
        int y_index = (y - map.info.origin.position.y) / resolution;
        if (x_index < 0 || x_index >= static_cast<int>(width) || y_index < 0 || y_index >= static_cast<int>(height)) {  
            return -1;
        }
        return y_index * width + x_index;
    }
        
    bool isUnkownCell(geometry_msgs::msg::Pose pose){
        int index = get_index(pose);
        if (index == -1) {
            return false;
        }
        return map.data[index] == -1;
    }
    bool isObstacle(geometry_msgs::msg::Pose pose){
        int index = get_index(pose);
        if (index == -1) {
            return false;
        }
        return map.data[index] == 100;
    }
    bool isFreeSpace(geometry_msgs::msg::Pose pose) {
        int index = get_index(pose);
        if (index == -1) return false;
        return map.data[index] == 0;
    }
    bool is_no_obstacle_around(int x,int y,int d){
        size_t width = map.info.width;
        int min_x = std::max(x-d,0);
        int max_x = std::min(x+d,static_cast<int>(width - 1));
        int min_y = std::max(y-d,0);
        int max_y = std::min(y+d,static_cast<int>(map.info.height - 1));

        for (int i = min_x; i <= max_x; i++){
            for (int j = min_y; j <= max_y; j++){
                if (map.data[ j * width + i ] == 100){
                    return false;
                }
            }
        }
        return true;

    }
    geometry_msgs::msg::Pose get_nearest_free_cell(geometry_msgs::msg::Pose pose){
        int index = get_index(pose);
        if (index == -1) return pose; // return pose itself and trip will be cancelled
        size_t width = map.info.width;
        size_t height = map.info.height;
        float resolution = map.info.resolution;
        int x_index = index % static_cast<int>(width);
        int y_index = index / static_cast<int>(width);
        float car_width = 0.3;
        this->get_parameter("car_width", car_width);
        int distance_in_cells = std::ceil(car_width / map.info.resolution);
        int ring = distance_in_cells + 1;
        float max_distance_from_obstacle = 1;
        this->get_parameter("max_distance_from_obstacle", max_distance_from_obstacle);
        int max_distance_in_cells = std::ceil(max_distance_from_obstacle / map.info.resolution);
        while (ring <= max_distance_in_cells)  {
            // get cells in ring around cell
            int x_start = x_index - ring;
            int x_end = x_index + ring;
            int y_start = y_index - ring;
            int y_end = y_index + ring;
            // two vertical lines
            for (int i = y_start; i <= y_end; i++) {
                int j = x_start;
                if (i >= 0 && i < static_cast<int>(height) && j >= 0 && j < static_cast<int>(width)) {
                    if (map.data[i * width + j] == 0 && is_no_obstacle_around(j,i,distance_in_cells)) {
                        geometry_msgs::msg::Pose pose;
                        pose.position.x = (j - 0.5) * resolution + map.info.origin.position.x;
                        pose.position.y = (i - 0.5) * resolution + map.info.origin.position.y;
                        return pose;
                    }
                }
                j = x_end;
                if (i >= 0 && i < static_cast<int>(height) && j >= 0 && j < static_cast<int>(width)) {
                    if (map.data[i * width + j] == 0 && is_no_obstacle_around(j,i,distance_in_cells)) {
                        geometry_msgs::msg::Pose pose;
                        pose.position.x = (j - 0.5) * resolution + map.info.origin.position.x;
                        pose.position.y = (i - 0.5) * resolution + map.info.origin.position.y;
                        return pose;
                    }
                }
            }
            // two horizontal lines
            for (int j = x_start + 1; j < x_end; j++) {
                int i = y_start;
                if (i >= 0 && i < static_cast<int>(height) && j >= 0 && j < static_cast<int>(width)) {
                    if (map.data[i * width + j] == 0 && is_no_obstacle_around(j,i,distance_in_cells)) {
                        geometry_msgs::msg::Pose pose;
                        pose.position.x = (j - 0.5) * resolution + map.info.origin.position.x;
                        pose.position.y = (i - 0.5) * resolution + map.info.origin.position.y;
                        return pose;
                    }
                }
                i = y_end;
                if (i >= 0 && i < static_cast<int>(height) && j >= 0 && j < static_cast<int>(width)) {
                    if (map.data[i * width + j] == 0 && is_no_obstacle_around(j,i,distance_in_cells)) {
                        geometry_msgs::msg::Pose pose;
                        pose.position.x = (j - 0.5) * resolution + map.info.origin.position.x;
                        pose.position.y = (i - 0.5) * resolution + map.info.origin.position.y;
                        return pose;
                    }
                }
            }
            ring++;
        }
        return pose; // return pose itself and trip will be cancelled
    }
    bool isFrontier(int index) {
        int x = index % map.info.width;
        int y = index / map.info.width;
        if (index >= int(map.data.size()) || index < 0) {
            return false;
        }
        if (map.data[index] != 0) {
            return false;
        }
        int neighbors[8][2] = {{1,0},{-1,0},{0,1},{0,-1},{1,1},{1,-1},{-1,1},{-1,-1}};
        for (int i = 0; i < 8; i++) {
            int nx = x + neighbors[i][0];
            int ny = y + neighbors[i][1];
            if (nx >= 0 && nx < static_cast<int>(map.info.width) && ny >= 0 && ny < static_cast<int>(map.info.height)) {
                if (map.data[ny * map.info.width + nx] == -1) {
                    return true;
                }
            }
        }
        return false;
    }
    geometry_msgs::msg::Pose explore(geometry_msgs::msg::Pose goal){
        // return nearest frontier to the goal
        int nearest_frontier_index = -1;
        int goalIndex = get_index(goal);
        if (goalIndex == -1) return goal;
        int goal_x = goalIndex % static_cast<int>(map.info.width);
        int goal_y = goalIndex / static_cast<int>(map.info.width);
        // get car pose
        geometry_msgs::msg::TransformStamped car_transform;
        
        try {
            // Look up the transform from the car to the map with a 20ms wait timeout
            car_transform = tf_buffer_->lookupTransform("map", "base_link", tf2::TimePointZero, tf2::durationFromSec(0.02));
    
        } catch (const tf2::TransformException &ex) {
            // Throttling the warning ensures your terminal isn't flooded if a frame drops under heavy CPU load
            RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 5000, 
                         "Syncing car frames... Transform lag: %s", ex.what());
            return goal;
        }
        
        // Calculate map coordinates of car position
        double car_x = car_transform.transform.translation.x;
        double car_y = car_transform.transform.translation.y;
        
        int car_col = (car_x - map.info.origin.position.x) / map.info.resolution;
        int car_row = (car_y - map.info.origin.position.y) / map.info.resolution;

        if (car_col < 0 || car_col >= (int)map.info.width || car_row < 0 || car_row >= (int)map.info.height) {
            RCLCPP_WARN(this->get_logger(), "Car position is outside the grid");
            return goal;
        }

        double max_window_size = 16;
        int window_size = static_cast<int>(std::ceil(max_window_size/map.info.resolution));
        this->get_parameter("max_window_size", max_window_size);
        // get window to search on
        int min_x = std::max(car_col - window_size, 0);
        int max_x = std::min(car_col + window_size, (int)map.info.width - 1);
        int min_y = std::max(car_row - window_size, 0);
        int max_y = std::min(car_row + window_size, (int)map.info.height - 1);
        double min_dist = double(INT_MAX);
        for (int i = min_x; i < max_x; i++) {
            for (int j = min_y; j < max_y; j++) {
                if (isFrontier(j * map.info.width + i)) {
                    double dx = i - goal_x;
                    double dy = j - goal_y;
                    double dist_to_goal = std::sqrt(dx * dx + dy * dy);// euclidian distance
                    double dist_to_car = std::abs(i - car_col) + std::abs(j - car_row);// manhatten distance
                    double dist = dist_to_goal + dist_to_car;
                    if (dist < min_dist) {
                        min_dist = dist;
                        nearest_frontier_index = i * map.info.width + j;
                    }
                }
            }
        }
        if (nearest_frontier_index == -1) {
            return goal;
        }
        geometry_msgs::msg::Pose frontier_pose;
        frontier_pose.position.x = (nearest_frontier_index % map.info.width + 0.5) * map.info.resolution + map.info.origin.position.x;
        frontier_pose.position.y = (nearest_frontier_index / map.info.width + 0.5) * map.info.resolution + map.info.origin.position.y;
        return frontier_pose;   
    }
    void send_goal_state() {
        if (!action_client_->action_server_is_ready()) {
            RCLCPP_WARN(this->get_logger(), "Waiting for Nav2 Action Server to bring up...");
            return;
        }

        if (path_queue.empty()) {
            RCLCPP_WARN(this->get_logger(), "Path completed!");
            trip_status_pub_->publish(std_msgs::msg::Bool().set__data(true));
            state_machine = State::IDLE;
            reset_variables();
            return;
        }
            
        
        switch (goal_status) {
            case GoalStatus::SUCCEEDED:
                if (path_current_index == user_start_index + 1) {
                    state_machine = State::WAIT_USER;
                    waiting_time = 0;
                    goal_status = GoalStatus::UNKNOWN;
                    return;
                }
                current_sub_goal = path_queue.front();
                resend_flag = false;
                if (isUnkownCell(current_sub_goal.pose)) {
                    geometry_msgs::msg::Pose pose = explore(current_sub_goal.pose);
                    current_sub_goal.pose = pose;
                } else if (isObstacle(current_sub_goal.pose)) {
                    geometry_msgs::msg::Pose pose = get_nearest_free_cell(current_sub_goal.pose);
                    current_sub_goal.pose = pose;
                }
                break;
            case GoalStatus::ABORTED:
            case GoalStatus::CANCELED:
                if (resend_flag) {
                    trip_status_pub_->publish(std_msgs::msg::Bool().set__data(false));
                    reset_variables();
                    return;
                }
                resend_flag = true;
                current_sub_goal = path_queue.front();
                break;
            case GoalStatus::UNKNOWN:
                current_sub_goal = path_queue.front();
                if (isUnkownCell(current_sub_goal.pose)) {
                    geometry_msgs::msg::Pose pose = explore(current_sub_goal.pose);
                    current_sub_goal.pose = pose;
                    was_explore = true;
                } else if (isObstacle(current_sub_goal.pose)) {
                    geometry_msgs::msg::Pose pose = get_nearest_free_cell(current_sub_goal.pose);
                    current_sub_goal.pose = pose;
                }
                break;
        }

        // check if goal is valid
        if (get_index(current_sub_goal.pose) == -1) {
            trip_status_pub_->publish(std_msgs::msg::Bool().set__data(false));
            reset_variables();
            return;
        }
        

        // Freeze state machine while we transmit asynchronously
        state_machine = State::WAIT_FEEDBACK; // Transition straight to "wait feedback" state

        auto goal_msg = nav2_msgs::action::NavigateToPose::Goal();
        goal_msg.pose.header.stamp = this->now();
        goal_msg.pose.header.frame_id = "map";
        
        // Pull position from your running tracker variable instead of hardcoding (1.0, 1.0)
        goal_msg.pose.pose = current_sub_goal.pose; 

        RCLCPP_INFO(this->get_logger(), "Sending goal to Nav2...");

        auto send_goal_options = rclcpp_action::Client<nav2_msgs::action::NavigateToPose>::SendGoalOptions();
        
        // 1. Bind the Goal Response Callback (Did Nav2 accept or reject the goal request?)
        send_goal_options.goal_response_callback = 
            std::bind(&PathHandler::goal_response_callback, this, std::placeholders::_1);

        // 2. Bind Live Feedback Callback (Distance remaining, tracking details)
        send_goal_options.feedback_callback = 
            std::bind(&PathHandler::feedback_callback, this, std::placeholders::_1, std::placeholders::_2);

        // 3. Bind Result Callback (Did the car successfully arrive at coordinates?)
        send_goal_options.result_callback = 
            std::bind(&PathHandler::result_callback, this, std::placeholders::_1);

        // Execute the call
        action_client_->async_send_goal(goal_msg, send_goal_options);
    }

    // --- ACTION CLIENT CALLBACK HANDLERS ---

    void goal_response_callback(const rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::SharedPtr& goal_handle) {
        if (!goal_handle) {
            RCLCPP_ERROR(this->get_logger(), "Goal was rejected by Nav2 Action Server!");
            trip_status_pub_->publish(std_msgs::msg::Bool().set__data(false));
            state_machine = State::IDLE;
            reset_variables();
            return;
        } else {
            RCLCPP_INFO(this->get_logger(), "Goal accepted by Nav2, tracking execution...");
        }
    }

    void feedback_callback(
        rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::SharedPtr,
        const std::shared_ptr<const nav2_msgs::action::NavigateToPose::Feedback> feedback) 
    {
        // Here you listen to remaining distance on the move!
        RCLCPP_INFO(this->get_logger(), "Distance remaining: %f meters", feedback->distance_remaining);
    }

    void result_callback(const rclcpp_action::ClientGoalHandle<nav2_msgs::action::NavigateToPose>::WrappedResult& result) {
        switch (result.code) {
            case rclcpp_action::ResultCode::SUCCEEDED:
                RCLCPP_INFO(this->get_logger(), "Goal successfully reached!");
                goal_status = GoalStatus::SUCCEEDED;
                if (was_explore) {
                    was_explore = false;
                } else {
                    path_queue.pop();
                    path_current_index++;
                }
                break;
            case rclcpp_action::ResultCode::ABORTED:
                RCLCPP_ERROR(this->get_logger(), "Goal execution was aborted by Nav2!");
                goal_status = GoalStatus::ABORTED;
                break;
            case rclcpp_action::ResultCode::CANCELED:
                RCLCPP_WARN(this->get_logger(), "Goal execution canceled.");
                goal_status = GoalStatus::CANCELED;
                break;
            default:
                RCLCPP_ERROR(this->get_logger(), "Unknown result code received.");
                goal_status = GoalStatus::UNKNOWN;
                break;
        }
        state_machine = State::SEND_GOAL;
    }

    void backend_poses_callback(const geometry_msgs::msg::PoseArray::SharedPtr msg) {
        RCLCPP_INFO(this->get_logger(), "Path received from backend, processing...");
        if (path_queue.empty()) {
            RCLCPP_INFO(this->get_logger(), "Processing path...");
            for (const auto& individual_pose : msg->poses) {
        
                geometry_msgs::msg::PoseStamped sub_goal;
        
                sub_goal.header = msg->header;
                sub_goal.pose = individual_pose;

                path_queue.push(sub_goal);
            }
        }
        // remove firts car pose
        path_queue.pop();
    }

    void map_callback(const nav_msgs::msg::OccupancyGrid::SharedPtr msg) {
        map = *msg;
    }

    void user_state_callback(const std_msgs::msg::Bool::SharedPtr msg) {

        if (msg->data) {
            if (state_machine == State::WAIT_USER) {
                user_state = true;
            }
        } else {
            RCLCPP_INFO(this->get_logger(), "User cancelled the trip!");
            reset_variables();
        }
    }

    void user_start_callback(const std_msgs::msg::Int32::SharedPtr msg) {
        user_start_index = msg->data;
    }

    void reset_variables() {
        while (!path_queue.empty()) {
            path_queue.pop();
        }
        path_current_index = 0;
        resend_flag = false;
        goal_status = GoalStatus::UNKNOWN;
        state_machine = State::IDLE;
        user_start_index = -1;
        waiting_time = 0;
        user_state = false;
    }

    rclcpp_action::Client<nav2_msgs::action::NavigateToPose>::SharedPtr action_client_;
    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::Subscription<nav_msgs::msg::OccupancyGrid>::SharedPtr map_sub_;
    rclcpp::Subscription<geometry_msgs::msg::PoseArray>::SharedPtr backend_poses_sub_;
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr trip_status_pub_;
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr user_state_sub_;
    rclcpp::Subscription<std_msgs::msg::Int32>::SharedPtr user_start_sub_;
    std::queue<geometry_msgs::msg::PoseStamped> path_queue;
    std::unique_ptr<tf2_ros::Buffer> tf_buffer_;
    std::shared_ptr<tf2_ros::TransformListener> tf_listener_;
    nav_msgs::msg::OccupancyGrid map;
    geometry_msgs::msg::PoseStamped current_sub_goal;
    State state_machine = State::IDLE;
    GoalStatus goal_status = GoalStatus::UNKNOWN;
    bool resend_flag = false;
    int path_current_index = 0;
    int user_start_index = -1;
    int waiting_time = 0;
    bool user_state = false;
    bool was_explore = false;
};

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<PathHandler>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}