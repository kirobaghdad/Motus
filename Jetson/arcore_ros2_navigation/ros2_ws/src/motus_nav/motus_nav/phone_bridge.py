#!/usr/bin/env python3
import queue
import socket
import struct
import threading
import time
import zlib
from dataclasses import dataclass
from typing import Optional

import numpy as np
import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image, PointCloud2, PointField
from std_msgs.msg import Bool
from std_srvs.srv import Trigger
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster

from .math_utils import (
    euler_to_matrix,
    invert_transform,
    make_transform,
    matrix_to_quaternion,
    planar_transform,
    wrap_angle,
    yaw_from_matrix,
)

MAGIC = b'ARPK'
PROTOCOL_VERSION = 1
FIXED_FORMAT = '<HHQQB3x7fII4fIII'
FIXED_SIZE = struct.calcsize(FIXED_FORMAT)
AR_TO_ROS_CAMERA = np.array([
    [0.0, 0.0, -1.0],
    [-1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
], dtype=np.float64)
CAMERA_LINK_FROM_OPTICAL = np.array([
    [0.0, 0.0, 1.0],
    [-1.0, 0.0, 0.0],
    [0.0, -1.0, 0.0],
], dtype=np.float64)


@dataclass
class PhonePacket:
    sequence: int
    timestamp_ns: int
    tracking_code: int
    translation: np.ndarray
    quaternion: np.ndarray
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    grayscale: bytes
    points: np.ndarray


class PhoneBridge(Node):
    def __init__(self):
        super().__init__('phone_bridge')
        self.declare_parameter('listen_host', '0.0.0.0')
        self.declare_parameter('listen_port', 5050)
        self.declare_parameter('max_packet_bytes', 64 * 1024 * 1024)
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('camera_frame', 'phone_camera_link')
        self.declare_parameter('optical_frame', 'phone_camera_optical_frame')
        self.declare_parameter('camera_x', 0.20)
        self.declare_parameter('camera_y', 0.0)
        self.declare_parameter('camera_z', 0.15)
        self.declare_parameter('camera_roll', 0.0)
        self.declare_parameter('camera_pitch', 0.0)
        self.declare_parameter('camera_yaw', 0.0)
        self.declare_parameter('odom_scale', 1.12)
        self.declare_parameter('planar_mode', True)
        self.declare_parameter('jump_translation_m', 0.75)
        self.declare_parameter('jump_yaw_rad', 0.80)
        self.declare_parameter('publish_odom_tf', True)

        self.odom_frame = str(self.get_parameter('odom_frame').value)
        self.base_frame = str(self.get_parameter('base_frame').value)
        self.camera_frame = str(self.get_parameter('camera_frame').value)
        self.optical_frame = str(self.get_parameter('optical_frame').value)
        self.odom_scale = float(self.get_parameter('odom_scale').value)
        self.planar_mode = bool(self.get_parameter('planar_mode').value)
        self.publish_odom_tf = bool(self.get_parameter('publish_odom_tf').value)

        sensor_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        state_qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE)
        self.image_pub = self.create_publisher(Image, '/phone/image', sensor_qos)
        self.camera_info_pub = self.create_publisher(CameraInfo, '/phone/camera_info', sensor_qos)
        self.cloud_pub = self.create_publisher(PointCloud2, '/phone/points', sensor_qos)
        self.odom_pub = self.create_publisher(Odometry, '/phone/odom', state_qos)
        self.tracking_pub = self.create_publisher(Bool, '/phone/tracking_ok', state_qos)
        self.connected_pub = self.create_publisher(Bool, '/phone/connected', state_qos)
        self.jump_pub = self.create_publisher(Bool, '/phone/pose_jump', state_qos)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.static_broadcaster = StaticTransformBroadcaster(self)
        self.reset_service = self.create_service(Trigger, '/phone/reset_origin', self._reset_origin)

        self.packet_queue: queue.Queue[PhonePacket] = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.server_socket: Optional[socket.socket] = None
        self.connected = False
        self.reference_pose: Optional[np.ndarray] = None
        self.previous_base_pose: Optional[np.ndarray] = None
        self.previous_ros_time_ns: Optional[int] = None
        self.last_odom_publish_ns: Optional[int] = None
        self._build_extrinsics()
        self._publish_static_transforms()

        self.network_thread = threading.Thread(target=self._server_loop, daemon=True, name='phone_tcp_server')
        self.network_thread.start()
        self.process_timer = self.create_timer(0.01, self._process_latest_packet)
        self.odom_keepalive_timer = self.create_timer(0.10, self._publish_odom_keepalive)
        self.state_timer = self.create_timer(0.25, self._publish_connection_state)
        self.get_logger().info(
            f"Listening for PhoneNav on {self.get_parameter('listen_host').value}:"
            f"{self.get_parameter('listen_port').value}"
        )

    def _build_extrinsics(self):
        translation = (
            float(self.get_parameter('camera_x').value),
            float(self.get_parameter('camera_y').value),
            float(self.get_parameter('camera_z').value),
        )
        rotation = euler_to_matrix(
            float(self.get_parameter('camera_roll').value),
            float(self.get_parameter('camera_pitch').value),
            float(self.get_parameter('camera_yaw').value),
        )
        self.base_from_camera = make_transform(translation, rotation=rotation)
        self.camera_from_base = invert_transform(self.base_from_camera)
        self.ros_from_ar = make_transform(rotation=AR_TO_ROS_CAMERA)
        self.ar_from_ros = invert_transform(self.ros_from_ar)

    def _publish_static_transforms(self):
        now = self.get_clock().now().to_msg()
        base_to_camera = self._matrix_to_transform_stamped(
            self.base_from_camera, now, self.base_frame, self.camera_frame
        )
        camera_to_optical_matrix = make_transform(rotation=CAMERA_LINK_FROM_OPTICAL)
        camera_to_optical = self._matrix_to_transform_stamped(
            camera_to_optical_matrix, now, self.camera_frame, self.optical_frame
        )
        self.static_broadcaster.sendTransform([base_to_camera, camera_to_optical])

    def _server_loop(self):
        host = str(self.get_parameter('listen_host').value)
        port = int(self.get_parameter('listen_port').value)
        maximum = int(self.get_parameter('max_packet_bytes').value)
        while not self.stop_event.is_set():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                    self.server_socket = server
                    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    server.bind((host, port))
                    server.listen(1)
                    server.settimeout(1.0)
                    while not self.stop_event.is_set():
                        try:
                            client, address = server.accept()
                        except socket.timeout:
                            continue
                        self.get_logger().info(f'Phone connected from {address[0]}:{address[1]}')
                        self.connected = True
                        self.reference_pose = None
                        self.previous_base_pose = None
                        self.previous_ros_time_ns = None
                        self.last_odom_publish_ns = None
                        with client:
                            client.settimeout(3.0)
                            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                            try:
                                while not self.stop_event.is_set():
                                    prefix = self._recv_exact(client, 8)
                                    if prefix[:4] != MAGIC:
                                        raise ValueError('Packet magic mismatch')
                                    body_size = struct.unpack_from('<I', prefix, 4)[0]
                                    if body_size < FIXED_SIZE or body_size > maximum:
                                        raise ValueError(f'Invalid packet size {body_size}')
                                    body = self._recv_exact(client, body_size)
                                    packet = self._decode_packet(body)
                                    self._offer_packet(packet)
                            except (ConnectionError, TimeoutError, socket.timeout, OSError, ValueError, zlib.error) as error:
                                if not self.stop_event.is_set():
                                    self.get_logger().warning(f'Phone connection ended: {error}')
                            finally:
                                self.connected = False
                                self.tracking_pub.publish(Bool(data=False))
            except OSError as error:
                if not self.stop_event.is_set():
                    self.get_logger().error(f'TCP server error: {error}; retrying in 1 second')
                    time.sleep(1.0)
            finally:
                self.server_socket = None

    @staticmethod
    def _recv_exact(sock: socket.socket, count: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < count:
            piece = sock.recv(count - len(chunks))
            if not piece:
                raise ConnectionError('peer closed the socket')
            chunks.extend(piece)
        return bytes(chunks)

    def _decode_packet(self, body: bytes) -> PhonePacket:
        values = struct.unpack_from(FIXED_FORMAT, body, 0)
        version, flags, sequence, timestamp_ns, tracking = values[:5]
        if version != PROTOCOL_VERSION:
            raise ValueError(f'Unsupported protocol version {version}')
        pose = values[5:12]
        width, height = values[12:14]
        fx, fy, cx, cy = values[14:18]
        raw_image_size, compressed_size, point_count = values[18:21]
        expected_payload = compressed_size + point_count * 12
        if FIXED_SIZE + expected_payload != len(body):
            raise ValueError('Packet payload size mismatch')
        if raw_image_size != width * height:
            raise ValueError('Image dimensions do not match raw byte count')

        offset = FIXED_SIZE
        compressed = body[offset:offset + compressed_size]
        offset += compressed_size
        grayscale = zlib.decompress(compressed) if (flags & 1) else b''
        if len(grayscale) != raw_image_size:
            raise ValueError('Decompressed image size mismatch')
        if point_count > 0 and (flags & 2):
            points = np.frombuffer(body, dtype='<f4', count=point_count * 3, offset=offset).reshape((-1, 3)).copy()
        else:
            points = np.empty((0, 3), dtype=np.float32)
        return PhonePacket(
            sequence=sequence,
            timestamp_ns=timestamp_ns,
            tracking_code=tracking,
            translation=np.asarray(pose[:3], dtype=np.float64),
            quaternion=np.asarray(pose[3:7], dtype=np.float64),
            width=width,
            height=height,
            fx=fx,
            fy=fy,
            cx=cx,
            cy=cy,
            grayscale=grayscale,
            points=points,
        )

    def _offer_packet(self, packet: PhonePacket):
        try:
            self.packet_queue.put_nowait(packet)
        except queue.Full:
            try:
                self.packet_queue.get_nowait()
            except queue.Empty:
                pass
            self.packet_queue.put_nowait(packet)

    def _process_latest_packet(self):
        packet = None
        while True:
            try:
                packet = self.packet_queue.get_nowait()
            except queue.Empty:
                break
        if packet is None:
            return

        stamp = self.get_clock().now()
        stamp_msg = stamp.to_msg()
        tracking_ok = packet.tracking_code == 2
        self.tracking_pub.publish(Bool(data=tracking_ok))
        self._publish_image_and_info(packet, stamp_msg)
        if not tracking_ok:
            return

        camera_world_pose = make_transform(packet.translation, quaternion=packet.quaternion)
        if self.reference_pose is None:
            self.reference_pose = camera_world_pose
            self.get_logger().info('ARCore odometry origin initialized')

        relative_ar = invert_transform(self.reference_pose) @ camera_world_pose
        relative_camera = self.ros_from_ar @ relative_ar @ self.ar_from_ros
        base_pose = self.base_from_camera @ relative_camera @ self.camera_from_base
        base_pose[:3, 3] *= self.odom_scale
        if self.planar_mode:
            base_pose = planar_transform(
                float(base_pose[0, 3]),
                float(base_pose[1, 3]),
                yaw_from_matrix(base_pose[:3, :3]),
            )

        pose_jump = self._is_pose_jump(base_pose)
        self.jump_pub.publish(Bool(data=pose_jump))
        if pose_jump:
            self.get_logger().warning('Large ARCore pose change detected; safety gate will temporarily stop commands')

        self._publish_odometry(base_pose, stamp.nanoseconds, stamp_msg)
        self._publish_cloud(packet.points, stamp_msg)
        self.previous_base_pose = base_pose
        self.previous_ros_time_ns = stamp.nanoseconds

    def _publish_odom_keepalive(self):
        if not self.publish_odom_tf:
            return
        stamp = self.get_clock().now()
        if (
            self.last_odom_publish_ns is not None
            and (stamp.nanoseconds - self.last_odom_publish_ns) * 1.0e-9 < 0.25
        ):
            return
        pose = self.previous_base_pose
        if pose is None:
            pose = make_transform()
        self._publish_stationary_odometry(pose, stamp.to_msg())

    def _is_pose_jump(self, pose: np.ndarray) -> bool:
        if self.previous_base_pose is None:
            return False
        delta = invert_transform(self.previous_base_pose) @ pose
        translation = float(np.linalg.norm(delta[:3, 3]))
        yaw = abs(wrap_angle(yaw_from_matrix(delta[:3, :3])))
        return (
            translation > float(self.get_parameter('jump_translation_m').value)
            or yaw > float(self.get_parameter('jump_yaw_rad').value)
        )

    def _publish_odometry(self, pose: np.ndarray, now_ns: int, stamp_msg):
        linear_x = linear_y = angular_z = 0.0
        if self.previous_base_pose is not None and self.previous_ros_time_ns is not None:
            dt = (now_ns - self.previous_ros_time_ns) * 1.0e-9
            if 0.001 < dt < 1.0:
                dx = pose[0, 3] - self.previous_base_pose[0, 3]
                dy = pose[1, 3] - self.previous_base_pose[1, 3]
                yaw = yaw_from_matrix(pose[:3, :3])
                linear_x = (np.cos(yaw) * dx + np.sin(yaw) * dy) / dt
                linear_y = (-np.sin(yaw) * dx + np.cos(yaw) * dy) / dt
                previous_yaw = yaw_from_matrix(self.previous_base_pose[:3, :3])
                angular_z = wrap_angle(yaw - previous_yaw) / dt

        quaternion = matrix_to_quaternion(pose[:3, :3])
        message = Odometry()
        message.header.stamp = stamp_msg
        message.header.frame_id = self.odom_frame
        message.child_frame_id = self.base_frame
        message.pose.pose.position.x = float(pose[0, 3])
        message.pose.pose.position.y = float(pose[1, 3])
        message.pose.pose.position.z = float(pose[2, 3])
        message.pose.pose.orientation.x = float(quaternion[0])
        message.pose.pose.orientation.y = float(quaternion[1])
        message.pose.pose.orientation.z = float(quaternion[2])
        message.pose.pose.orientation.w = float(quaternion[3])
        message.twist.twist.linear.x = float(linear_x)
        message.twist.twist.linear.y = float(linear_y)
        message.twist.twist.angular.z = float(angular_z)
        for index, value in zip((0, 7, 14, 21, 28, 35), (0.02, 0.02, 0.10, 0.10, 0.10, 0.05)):
            message.pose.covariance[index] = value
        for index, value in zip((0, 7, 14, 21, 28, 35), (0.05, 0.05, 0.10, 0.10, 0.10, 0.10)):
            message.twist.covariance[index] = value
        self.odom_pub.publish(message)
        if self.publish_odom_tf:
            self.tf_broadcaster.sendTransform(
                self._matrix_to_transform_stamped(pose, stamp_msg, self.odom_frame, self.base_frame)
            )
        self.last_odom_publish_ns = now_ns

    def _publish_stationary_odometry(self, pose: np.ndarray, stamp_msg):
        quaternion = matrix_to_quaternion(pose[:3, :3])
        message = Odometry()
        message.header.stamp = stamp_msg
        message.header.frame_id = self.odom_frame
        message.child_frame_id = self.base_frame
        message.pose.pose.position.x = float(pose[0, 3])
        message.pose.pose.position.y = float(pose[1, 3])
        message.pose.pose.position.z = float(pose[2, 3])
        message.pose.pose.orientation.x = float(quaternion[0])
        message.pose.pose.orientation.y = float(quaternion[1])
        message.pose.pose.orientation.z = float(quaternion[2])
        message.pose.pose.orientation.w = float(quaternion[3])
        for index, value in zip((0, 7, 14, 21, 28, 35), (0.05, 0.05, 0.10, 0.10, 0.10, 0.10)):
            message.pose.covariance[index] = value
            message.twist.covariance[index] = value
        self.odom_pub.publish(message)
        self.tf_broadcaster.sendTransform(
            self._matrix_to_transform_stamped(pose, stamp_msg, self.odom_frame, self.base_frame)
        )
        self.last_odom_publish_ns = self.get_clock().now().nanoseconds

    def _publish_image_and_info(self, packet: PhonePacket, stamp_msg):
        image = Image()
        image.header.stamp = stamp_msg
        image.header.frame_id = self.optical_frame
        image.height = packet.height
        image.width = packet.width
        image.encoding = 'mono8'
        image.is_bigendian = False
        image.step = packet.width
        image.data = packet.grayscale
        self.image_pub.publish(image)

        info = CameraInfo()
        info.header = image.header
        info.height = packet.height
        info.width = packet.width
        info.distortion_model = 'plumb_bob'
        info.d = [0.0, 0.0, 0.0, 0.0, 0.0]
        info.k = [
            float(packet.fx), 0.0, float(packet.cx),
            0.0, float(packet.fy), float(packet.cy),
            0.0, 0.0, 1.0,
        ]
        info.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        info.p = [
            float(packet.fx), 0.0, float(packet.cx), 0.0,
            0.0, float(packet.fy), float(packet.cy), 0.0,
            0.0, 0.0, 1.0, 0.0,
        ]
        self.camera_info_pub.publish(info)

    def _publish_cloud(self, points: np.ndarray, stamp_msg):
        cloud = PointCloud2()
        cloud.header.stamp = stamp_msg
        cloud.header.frame_id = self.optical_frame
        cloud.height = 1
        cloud.width = int(points.shape[0])
        cloud.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
        ]
        cloud.is_bigendian = False
        cloud.point_step = 12
        cloud.row_step = 12 * cloud.width
        cloud.is_dense = False
        cloud.data = np.asarray(points, dtype='<f4').tobytes(order='C')
        self.cloud_pub.publish(cloud)

    def _matrix_to_transform_stamped(self, matrix, stamp_msg, parent, child):
        quaternion = matrix_to_quaternion(matrix[:3, :3])
        transform = TransformStamped()
        transform.header.stamp = stamp_msg
        transform.header.frame_id = parent
        transform.child_frame_id = child
        transform.transform.translation.x = float(matrix[0, 3])
        transform.transform.translation.y = float(matrix[1, 3])
        transform.transform.translation.z = float(matrix[2, 3])
        transform.transform.rotation.x = float(quaternion[0])
        transform.transform.rotation.y = float(quaternion[1])
        transform.transform.rotation.z = float(quaternion[2])
        transform.transform.rotation.w = float(quaternion[3])
        return transform

    def _publish_connection_state(self):
        self.connected_pub.publish(Bool(data=self.connected))

    def _reset_origin(self, _request, response):
        self.reference_pose = None
        self.previous_base_pose = None
        self.previous_ros_time_ns = None
        response.success = True
        response.message = 'The next tracked ARCore frame will become the new odometry origin.'
        return response

    def destroy_node(self):
        self.stop_event.set()
        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PhoneBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
