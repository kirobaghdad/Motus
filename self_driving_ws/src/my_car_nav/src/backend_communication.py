import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseArray
from geometry_msgs.msg import Pose
from std_msgs.msg import Int32
from std_msgs.msg import Bool
import socketio
import threading
import tf2_ros
from rclpy.duration import Duration

# Initialize the Socket.io Client
sio = socketio.Client()

class BackendCommunicationNode(Node):
    def __init__(self):
        super().__init__('backend_communication_node')

        self.declare_parameter('backend_url', 'http://localhost:3000')
        self.backend_url = self.get_parameter('backend_url').value

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.backend_poses_pub = self.create_publisher(PoseArray, 'backend_poses', 10)
        self.user_start_pub = self.create_publisher(Int32, 'user_start', 10)  
        self.trip_status_sub = self.create_subscription(Bool, 'trip_status', self.trip_status_callback, 10)
        self.user_state_pub = self.create_publisher(Bool, 'user_state', 10)

        self.timer = self.create_timer(1.0, self.send_car_pose_to_backend_callback)  
        self.trip_id = None
        self.username = None
        
        # Define Socket.io event handlers inside the node context
        @sio.event
        def connect():
            self.get_logger().info('Successfully connected to Node.js backend!')
            # register car to backend
            payload = {
                "username": "MOTUS",
                "password": "4DF89ER30ES"
            }
            sio.emit('register-user', payload)

        @sio.event
        def disconnect():
            self.get_logger().warn('Disconnected from Node.js backend.')

        # Listen for commands coming from the Node.js Socket.io server
        @sio.on('path')
        def on_received_path(data):
            self.get_logger().info(f"Received path command from backend")
            poses = PoseArray()
            poses.header.frame_id = 'map'
            poses.header.stamp = self.get_clock().now().to_msg()
            start_index = 0
            for index, pose in enumerate(data["poses"]):
                pose_msg = Pose()
                if pose['x'] == data["start"]['x'] and pose['y'] == data["start"]['y']:
                    start_index = index
                pose_msg.position.x = float(pose['x'])
                pose_msg.position.y = float(pose['y'])
                poses.poses.append(pose_msg)
            self.backend_poses_pub.publish(poses)
            self.user_start_pub.publish(Int32(data=start_index-1))
            if "tripId" in data:
                self.trip_id = data["tripId"]
            else:
                self.trip_id = None
            self.username = data["username"]
        
        @sio.on('cancelled-trip')
        def on_received_cancelled_trip(data):
            self.get_logger().info(f"Received cancelled trip from backend: {data}")
            self.trip_id = None
            self.user_state_pub.publish(Bool(data=False))

        # Start the socketio connection in a background thread so it doesn't block ROS 2
        self.sio_thread = threading.Thread(target=self.start_socket)
        self.sio_thread.daemon = True
        self.sio_thread.start()

    def send_car_pose_to_backend_callback(self):

        try:
            timeout_duration = Duration(seconds=0, nanoseconds=20000000)
        
            car_transform = self.tf_buffer.lookup_transform(
                'map', 
                'base_link', 
                rclpy.time.Time(), 
                timeout=timeout_duration
            )
            car_pose = {
                "x": car_transform.transform.translation.x,
                "y": car_transform.transform.translation.y
            }
            if sio.connected:
                sio.emit('car-position', car_pose)
        except tf2_ros.TransformException as e:
            self.get_logger().error(f"Failed to get car pose: {e}")
            

    def start_socket(self):
        try:
            sio.connect(self.backend_url)
            sio.wait()
        except Exception as e:
            self.get_logger().error(f"Socket.io connection failed: {e}")

    def trip_status_callback(self, msg):
        if sio.connected:
            if self.trip_id is not None:
                sio.emit('finished-trips', {'tripId': self.trip_id, 'immediate': False, 'completed': msg.data})
                self.trip_id = None
            else:
                sio.emit('finished-trips', {'tripId': "123455", 'immediate': True, 'completed': msg.data})


def main(args=None):
    rclpy.init(args=args)
    node = BackendCommunicationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if sio.connected:
            sio.disconnect()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()