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
        state_machine = State::SEND_GOAL;
    }
    //void wait_feedback_state(){}
    void wait_user_state(){
        // max wait time is 3 minutes
        if (waiting_time > 1800) {
            RCLCPP_INFO(this->get_logger(), "User not in the car for 3 minutes, ending trip!");
            trip_status_pub_->publish(std_msgs::msg::Bool().set__data(true));
            state_machine = State::IDLE;
            reset_variables();
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
    geometry_msgs::msg::Pose get_nearest_free_cell(geometry_msgs::msg::Pose pose){
        int index = get_index(pose);
        if (index == -1) return pose; // return pose itself and trip will be cancelled
        int ring = 1;
        size_t width = map.info.width;
        size_t height = map.info.height;
        float resolution = map.info.resolution;
        int x_index = index % static_cast<int>(width);
        int y_index = index / static_cast<int>(width);
        while (ring < 21)  {
            // get cells in ring around cell
            int x_start = x_index - ring;
            int x_end = x_index + ring;
            int y_start = y_index - ring;
            int y_end = y_index + ring;
            // two vertical lines
            for (int i = y_start; i <= y_end; i++) {
                int j = x_start;
                if (i >= 0 && i < static_cast<int>(height) && j >= 0 && j < static_cast<int>(width)) {
                    if (map.data[i * width + j] == 0) {
                        geometry_msgs::msg::Pose pose;
                        pose.position.x = (j - 0.5) * resolution + map.info.origin.position.x;
                        pose.position.y = (i - 0.5) * resolution + map.info.origin.position.y;
                        return pose;
                    }
                }
                j = x_end;
                if (i >= 0 && i < static_cast<int>(height) && j >= 0 && j < static_cast<int>(width)) {
                    if (map.data[i * width + j] == 0) {
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
                    if (map.data[i * width + j] == 0) {
                        geometry_msgs::msg::Pose pose;
                        pose.position.x = (j - 0.5) * resolution + map.info.origin.position.x;
                        pose.position.y = (i - 0.5) * resolution + map.info.origin.position.y;
                        return pose;
                    }
                }
                i = y_end;
                if (i >= 0 && i < static_cast<int>(height) && j >= 0 && j < static_cast<int>(width)) {
                    if (map.data[i * width + j] == 0) {
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
    bool isFrontier(size_t index) {
        int x = index % map.info.width;
        int y = index / map.info.width;
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
    geometry_msgs::msg::Pose explore(geometry_msgs::msg::Pose pose){
        // return nearest frontier to the goal
        int nearest_frontier_index = -1;
        int goalIndex = get_index(pose);
        if (goalIndex == -1) return pose;
        int goal_x = goalIndex % static_cast<int>(map.info.width);
        int goal_y = goalIndex / static_cast<int>(map.info.width);
        int min_dist = INT_MAX;
        for (size_t i = 0; i < map.data.size(); i++) {
            if (isFrontier(i)) {
                int frontier_x = i % static_cast<int>(map.info.width);
                int frontier_y = i / static_cast<int>(map.info.width);
                int dist = abs(frontier_x - goal_x) + abs(frontier_y - goal_y);// manhatten distance
                if (dist < min_dist) {
                    min_dist = dist;
                    nearest_frontier_index = i;
                }
            }
        }
        if (nearest_frontier_index == -1) {
            return pose;
        }
        geometry_msgs::msg::Pose frontier_pose;
        frontier_pose.position.x = (nearest_frontier_index % map.info.width - 0.5) * map.info.resolution + map.info.origin.position.x;
        frontier_pose.position.y = (nearest_frontier_index / map.info.width - 0.5) * map.info.resolution + map.info.origin.position.y;
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

        if (path_current_index == user_start_index) {
            state_machine = State::WAIT_USER;
            return;
        }
            
        
        switch (goal_status) {
            case GoalStatus::SUCCEEDED:
                current_sub_goal = path_queue.front();
                resend_flag = false;
                path_current_index++;
                if (isUnkownCell(current_sub_goal.pose)) {
                    geometry_msgs::msg::Pose pose = explore(current_sub_goal.pose);
                    current_sub_goal.pose = pose;
                } else if (isObstacle(current_sub_goal.pose)) {
                    geometry_msgs::msg::Pose pose = get_nearest_free_cell(current_sub_goal.pose);
                    current_sub_goal.pose = pose;
                }
                break;
            case GoalStatus::ABORTED:
                // try resending goal if do it before 1 time end trip
                if (resend_flag) {
                    trip_status_pub_->publish(std_msgs::msg::Bool().set__data(true));
                    reset_variables();
                    return;
                }
                resend_flag = true;
                current_sub_goal = path_queue.front();
                break;
            case GoalStatus::CANCELED:
                if (resend_flag) {
                    trip_status_pub_->publish(std_msgs::msg::Bool().set__data(true));
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
                } else if (isObstacle(current_sub_goal.pose)) {
                    geometry_msgs::msg::Pose pose = get_nearest_free_cell(current_sub_goal.pose);
                    current_sub_goal.pose = pose;
                }
                break;
        }

        // check if goal is valid
        if (get_index(current_sub_goal.pose) == -1) {
            trip_status_pub_->publish(std_msgs::msg::Bool().set__data(true));
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
            trip_status_pub_->publish(std_msgs::msg::Bool().set__data(true));
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
                path_queue.pop();
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
        if (path_queue.empty()) {
            for (const auto& individual_pose : msg->poses) {
        
                geometry_msgs::msg::PoseStamped sub_goal;
        
                sub_goal.header = msg->header;
                sub_goal.pose = individual_pose;

                path_queue.push(sub_goal);
            }
        }
    }

    void map_callback(const nav_msgs::msg::OccupancyGrid::SharedPtr msg) {
        map = *msg;
    }

    void user_state_callback(const std_msgs::msg::Bool::SharedPtr msg) {
        bool user_state = msg->data;
        if (user_state) {
            state_machine = State::SEND_GOAL;
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
    }

    rclcpp_action::Client<nav2_msgs::action::NavigateToPose>::SharedPtr action_client_;
    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::Subscription<nav_msgs::msg::OccupancyGrid>::SharedPtr map_sub_;
    rclcpp::Subscription<geometry_msgs::msg::PoseArray>::SharedPtr backend_poses_sub_;
    rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr trip_status_pub_;
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr user_state_sub_;
    rclcpp::Subscription<std_msgs::msg::Int32>::SharedPtr user_start_sub_;
    std::queue<geometry_msgs::msg::PoseStamped> path_queue;
    nav_msgs::msg::OccupancyGrid map;
    geometry_msgs::msg::PoseStamped current_sub_goal;
    State state_machine = State::IDLE;
    GoalStatus goal_status = GoalStatus::UNKNOWN;
    bool resend_flag = false;
    int path_current_index = 0;
    int user_start_index = -1;
    int waiting_time = 0;
};

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<PathHandler>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}