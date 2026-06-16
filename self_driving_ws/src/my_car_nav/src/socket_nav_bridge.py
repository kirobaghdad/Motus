import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
import socket
import threading
import json

class SocketNavBridge(Node):
    def __init__(self):
        super().__init__('socket_nav_bridge')
        
        # Initialize Nav2 Action Client
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Configure Socket Server (Listens on all interfaces, port 5000)
        self.host = '0.0.0.0'
        self.port = 5000
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        self.get_logger().info(f"Socket Navigation Bridge Started on port {self.port}. Waiting for laptop connection...")
        
        # Start a background thread to listen for network data without blocking ROS
        self.bridge_thread = threading.Thread(target=self.socket_listener_loop, daemon=True)
        self.bridge_thread.start()

    def socket_listener_loop(self):
        while rclpy.ok():
            try:
                client_socket, addr = self.server_socket.accept()
                self.get_logger().info(f"Connected to laptop at {addr}")
                
                while True:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break
                    
                    self.get_logger().info(f"Received raw data: {data}")
                    try:
                        # Expecting JSON string like: {"x": 2.5, "y": -1.0}
                        goal_data = json.loads(data)
                        x = float(goal_data['x'])
                        y = float(goal_data['y'])
                        
                        self.get_logger().info(f"Sending Nav2 goal to X: {x}, Y: {y}")
                        self.send_nav2_goal(x, y)
                        client_socket.send(b"Goal accepted by Nav2\n")
                    except Exception as e:
                        client_socket.send(f"Error parsing goal: {str(e)}\n".encode())
                        
            except Exception as e:
                self.get_logger().error(f"Socket error: {str(e)}")

    def send_nav2_goal(self, x, y):
        # Wait for action server to be available
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 Action Server not available!")
            return

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        
        # Fill coordinates
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.orientation.w = 1.0 # Default facing forward

        self._action_client.send_goal_async(goal_msg)

def main(args=None):
    rclpy.init(args=args)
    node = SocketNavBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()