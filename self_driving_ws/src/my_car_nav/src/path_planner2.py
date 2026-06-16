import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path, OccupancyGrid
import math
import heapq

class CustomPathPlanner(Node):
    def __init__(self):
        super().__init__('custom_path_planner')
        
        # Grid Map Metadata (Matches your Map Loader)
        self.resolution = 0.05
        self.origin_x = -2.5
        self.origin_y = -2.5
        self.grid_data = None
        
        # 1. Subscribers
        self.map_sub = self.create_subscription(OccupancyGrid, '/map', self.map_callback, 10)
        self.pose_sub = self.create_subscription(PoseStamped, '/car_pose', self.pose_callback, 10)
        self.goal_sub = self.create_subscription(PoseStamped, '/goal_pose', self.goal_callback, 10)
        
        # 2. Publisher
        self.path_pub = self.create_publisher(Path, '/path_to_follow', 10)
        
        # State Variables
        self.current_pose = None
        self.goal_pose = None

    def map_callback(self, msg):
        # Save the map array internally to check for obstacles
        self.grid_data = msg.data
        self.get_logger().info("Map received successfully!")

    def pose_callback(self, msg):
        self.current_pose = msg.pose.position

    def goal_callback(self, msg):
        self.goal_pose = msg.pose.position
        # Trigger planning whenever a new goal is selected
        if self.current_pose and self.grid_data:
            self.plan_path()

    def world_to_grid(self, world_x, world_y):
        grid_x = int((world_x - self.origin_x) / self.resolution)
        grid_y = int((world_y - self.origin_y) / self.resolution)
        return grid_x, grid_y

    def grid_to_world(self, grid_x, grid_y):
        world_x = (grid_x * self.resolution) + self.origin_x + (self.resolution / 2.0)
        world_y = (grid_y * self.resolution) + self.origin_y + (self.resolution / 2.0)
        return world_x, world_y

    def plan_path(self):
        # 1. Convert real world meters to grid indices
        start_grid = self.world_to_grid(self.current_pose.x, self.current_pose.y)
        goal_grid = self.world_to_grid(self.goal_pose.x, self.goal_pose.y)
        
        self.get_logger().info(f"Planning from grid {start_grid} to {goal_grid}")
        
        # 2. RUN YOUR PATH PLANNING ALGORITHM HERE (e.g., A*)
        # For now, let's assume 'grid_path' returns a list of grid tuples: [(x1,y1), (x2,y2)...]
        grid_path = self.a_star_search(start_grid, goal_grid)
        
        # 3. Create the ROS 2 Path Message
        path_msg = Path()
        path_msg.header.stamp = self.get_clock().now().to_msg()
        path_msg.header.frame_id = "map"
        
        for cell in grid_path:
            # Convert grid index back to real world meters
            wx, wy = self.grid_to_world(cell[0], cell[1])
            
            pose = PoseStamped()
            pose.header.frame_id = "map"
            pose.pose.position.x = wx
            pose.pose.position.y = wy
            pose.pose.position.z = 0.0
            
            path_msg.poses.append(pose)
            
        # 4. Publish the final path
        self.path_pub.publish(path_msg)
        self.get_logger().info("Path published on /path_to_follow!")

    def a_star_search(self, start, goal):
        # helper function
        def heuristic(a, b):
            return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)
        def get_neighbors(self, node):
            neighbors = []
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
                neighbor = (node[0] + dx, node[1] + dy)
                if is_valid(neighbor):
                    neighbors.append(neighbor)
            return neighbors
        def is_valid(self, node):
            x, y = node
            if x < 0 or x >= self.grid_data.info.width or y < 0 or y >= self.grid_data.info.height:
                return False
            if self.grid_data.data[y * self.grid_data.info.width + x] == 100:
                return False
            return True
        def reconstruct_path(came_from, start, goal):
            path = []
            current = goal
            while current != start:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path
        frontier = []
        explored = set()
        heapq.heappush(frontier, (0, start))
        came_from = {}
        cost_so_far = {}
        came_from[start] = None
        cost_so_far[start] = 0
        while frontier:
            current = heapq.heappop(frontier)[1]
            if current == goal:
                break
            for neighbor in get_neighbors(current):
                new_cost = cost_so_far[current] + 1
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    priority = new_cost + heuristic(neighbor, goal)
                    heapq.heappush(frontier, (priority, neighbor))
                    came_from[neighbor] = current
        return reconstruct_path(came_from, start, goal)

def main(args=None):
    rclpy.init(args=args)
    node = CustomPathPlanner()
    rclpy.spin(node)
    rclpy.shutdown()