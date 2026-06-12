#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2, PointField
import tf2_ros
import math
import json
import numpy as np

class SimpleSim(Node):
    def __init__(self):
        super().__init__('simple_sim')
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.cloud_pub = self.create_publisher(PointCloud2, 'cloud_points', 10)
        self.sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_callback, 10)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
        with open('../maps/simple_map.json', 'r') as f:
            self.map_data = json.load(f)
        car_initial_pose = self.map_data['car_pose']
        self.x = car_initial_pose[0]
        self.y = car_initial_pose[1]
        self.z = car_initial_pose[2]
        self.th = car_initial_pose[3]
        self.objects = self.map_data['objects']
        self.car_width = self.map_data['car_width']
        self.car_length = self.map_data['car_length']
        self.create_timer(0.1, self.update) # 10Hz

    def find_camera_plane(self):
        normal = np.array([math.cos(self.th), math.sin(self.th), 0])
        d = np.dot(normal, np.array([self.x, self.y, self.z]))
        return normal,d

    def intersect_line_plane(self, p1, p2, normal, d):
        line_vec = p2 - p1
        beta = d - np.dot(normal, p1)
        alpha = line_vec.sum()
        if alpha == 0:
            return None
        t = beta / alpha
        return p1 + t * line_vec
        

    def Sutherland_Hodgman_clip_algorithm(self, polygon, normal, d):
        result = []
        previous = polygon[-1]
        was_inFrontOf_plane = np.dot(normal, previous) >= d
        for current in polygon:
            is_inFrontOf_plane = np.dot(normal, current) >= d
            if is_inFrontOf_plane != was_inFrontOf_plane:
                result.append(self.intersect_line_plane(previous, current, normal, d))
            if is_inFrontOf_plane:
                result.append(current)
            previous = current
            was_inFrontOf_plane = is_inFrontOf_plane
        return np.vstack(result)

    def get_points_along_line(self,p1,p2,step_size=0.05):
        line_vec = p2 - p1
        magnitude = np.linalg.norm(line_vec)
        if magnitude < step_size:
            return None
        norm_vec = line_vec / magnitude
        num_steps = int(np.floor(magnitude / step_size))
        steps = np.arange(1,num_steps+1)*step_size
        points = p1 + steps[:,np.newaxis]*norm_vec
        return points

    def get_obj_vertices(self,object):
        # get the 4 lower vertices of the object at z = height
        x,y = object['point']
        x_width = object['x_width']
        y_width = object['y_width']
        z = object['z']
        vertices = np.array([[x,y,z],
                             [x+x_width,y,z],
                             [x+x_width,y+y_width,z],
                             [x,y+y_width,z]])
        return vertices

    def get_rotation_matrix(self):
        angle = np.pi/2 - self.th
        return np.array([[np.cos(angle), -np.sin(angle), 0],
                         [np.sin(angle), np.cos(angle), 0],
                         [0, 0, 1]])

    def get_cloud_points(self,vertices):
        # first add the upper vertices
        cloud_points = []
        cloud_points.append(vertices)
        # then add the points along the edges
        for i in range(vertices.shape[0]):
            p1 = vertices[i]
            p2 = vertices[(i+1)%vertices.shape[0]]
            points = self.get_points_along_line(p1,p2)
            if points is not None:
                cloud_points.append(points)
        # then add vertices for vertical edges
        vertical_points = vertices.copy()
        vertical_points[:,2] /= 2.0
        cloud_points.append(vertical_points)
        return np.vstack(cloud_points)
        

    def find_objects_inFrontOf_camera(self):
        normal,d = self.find_camera_plane()
        rotation_matrix = self.get_rotation_matrix()
        rotated_car = np.dot(np.array([self.x,self.y,self.z]),rotation_matrix)
        cloud_points = []
        for obj in self.objects:
            vertices = self.get_obj_vertices(obj)
            rotated_vertices = np.dot(vertices,rotation_matrix)
            y_min = np.min(rotated_vertices[:,1])
            y_max = np.max(rotated_vertices[:,1])
            if y_min >= rotated_car[1]:
                # take whole object
                cloud_points.extend(self.get_cloud_points(vertices))
            elif y_max < rotated_car[1]:
                # skip this object
                continue
            else:
                # clip the object
                clipped_vertices = self.Sutherland_Hodgman_clip_algorithm(rotated_vertices,normal,d)
                cloud_points.extend(self.get_cloud_points(clipped_vertices))
        return cloud_points

    def get_translation_vector(self):
        # transform points to car local world coordinate
        return np.array([self.x,self.y,self.z]) * -1

    def publish_cloud_points(self):
        cloud_points = self.find_objects_inFrontOf_camera()
        translation_vector = self.get_translation_vector()
        # make points relative to car pose as vslam will publish
        translated_points = cloud_points + translation_vector
        # prepare message to be published
        try:
            # Create the PointCloud2 message
            msg = PointCloud2()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'map'

            # Define the structure (X, Y, Z)
            msg.height = 1
            msg.width = len(translated_points)
            msg.fields = [
                PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
                PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
                PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            ]
            msg.is_bigendian = False
            msg.point_step = 12
            msg.row_step = msg.point_step * msg.width
            msg.is_dense = True
            msg.data = np.ascontiguousarray(translated_points, dtype=np.float32).tobytes()

            self.cloud_pub.publish(msg)
            self.get_logger().info(f'Published {len(translated_points)} points from file.')
        except Exception as e:
            self.get_logger().error(f'Failed to load file: {e}')
        
                
    def cmd_callback(self, msg):
        # Move the virtual car based on Nav2 commands
        dt = 0.1
        self.x += msg.linear.x * math.cos(self.th) * dt
        self.y += msg.linear.x * math.sin(self.th) * dt
        self.th += msg.angular.z * dt

    def update(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.rotation.z = math.sin(self.th / 2.0)
        t.transform.rotation.w = math.cos(self.th / 2.0)
        self.tf_broadcaster.send_transform(t)

def main():
    rclpy.init()
    rclpy.spin(SimpleSim())
    rclpy.shutdown()