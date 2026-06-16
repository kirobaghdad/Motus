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
import os
from ament_index_python.packages import get_package_share_directory

class SimpleSim(Node):
    def __init__(self):
        super().__init__('simple_sim')
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.cloud_pub = self.create_publisher(PointCloud2, 'cloud_points', 10)
        self.cmd_vel_sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_callback, 10)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # load map
        try:
            package_share_dir = get_package_share_directory('my_car_nav')
            map_path = os.path.join(package_share_dir, 'maps', 'simple_map.json')
            
            self.get_logger().info(f'Loading map file from: {map_path}')
            with open(map_path, 'r') as f:
                self.map_data = json.load(f)
        except Exception as e:
            self.get_logger().error(f'Failed to open map file! Error: {e}')
            # Stop the node from crashing silently by raising an explicit exception
            raise e

        self.car_initial_pose = self.map_data['car_pose']
        self.x = self.car_initial_pose[0]
        self.y = self.car_initial_pose[1]
        self.z = self.car_initial_pose[2]
        self.th = self.car_initial_pose[3]

        # latest velocities from cmd_vel
        self.linear_x = 0.0
        #self.linear_y = 0.0
        self.angular_z = 0.0
        
        # objects
        self.objects = self.map_data['objects']
        self.car_width = self.map_data['car_width']
        self.car_length = self.map_data['car_length']
        
        # timer
        self.dt = 0.05
        self.create_timer(self.dt, self.update) # 0.1 --> 10hz

    def find_camera_plane(self):
        normal = np.array([math.cos(self.th), math.sin(self.th), 0])
        d = np.dot(normal, np.array([self.x, self.y, self.z]))
        return normal,d

    def intersect_line_plane(self, p1, p2, normal, d):
        line_vec = p2 - p1
        beta = d - np.dot(normal, p1)
        alpha = np.dot(normal, line_vec)
        if alpha == 0:
            return None
        t = beta / alpha
        return p1 + t * line_vec
        

    def Sutherland_Hodgman_clip_algorithm(self, polygon, normal, d):
        result = []
        if len(polygon) == 0:
            return None
        previous = polygon[-1]
        was_inFrontOf_plane = np.dot(normal, previous) >= d
        for current in polygon:
            is_inFrontOf_plane = np.dot(normal, current) >= d
            if is_inFrontOf_plane != was_inFrontOf_plane:
                intersection = self.intersect_line_plane(previous, current, normal, d)
                if intersection is not None:
                    result.append(intersection)
            if is_inFrontOf_plane:
                result.append(current)
            previous = current
            was_inFrontOf_plane = is_inFrontOf_plane
        if len(result) == 0:
            return None
        return np.vstack(result)

    def intersect(self, p1, p2):
        # assumes plane is at x = 0 and normal is (1,0,0)
        # in my case all line points in same plane at constant z 
        line_vec = p2 - p1
        if line_vec[0] == 0: # line is vertical all line intersect at x=0
            return None
        slope = line_vec[1] / line_vec[0]
        y_intercept = p1[1] - slope * p1[0]
        return np.array([0, y_intercept, p1[2]])

    
    def clip(self, polygon):
        # assume all point in local car frame
        result = []
        if len(polygon) == 0:
            return None
        previous = polygon[-1]
        was_inFrontOf_plane = previous[0] >= 0
        for current in polygon:
            is_inFrontOf_plane = current[0] >= 0
            if is_inFrontOf_plane != was_inFrontOf_plane:
                intersection = self.intersect(previous, current)
                if intersection is not None:
                    result.append(intersection)
            if is_inFrontOf_plane:
                result.append(current)
            previous = current
            was_inFrontOf_plane = is_inFrontOf_plane
        if len(result) == 0:
            return None
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
        z = object['height']
        vertices = np.array([[x,y,z],
                             [x+x_width,y,z],
                             [x+x_width,y+y_width,z],
                             [x,y+y_width,z]])
        return vertices

    def get_rotation_matrix(self):
        # rotation matrix from world to car frame
        # although it shoul be - theta but I use it with row vector in its left so instead of transpose the matrix later use + theta
        angle =  self.th
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
        #normal,d = self.find_camera_plane()
        rotation_matrix = self.get_rotation_matrix()
        translation_vector = self.get_translation_vector()
        cloud_points = []
        #self.get_logger().info(f'Car pose: {self.x}, {self.y}, {self.z}, {self.th}')
        for obj in self.objects:
            id = obj['id']
            vertices = self.get_obj_vertices(obj)
            translated_vertices = vertices + translation_vector
            rotated_vertices = np.dot(translated_vertices,rotation_matrix)
            x_min = np.min(rotated_vertices[:,0])
            x_max = np.max(rotated_vertices[:,0])
            if x_min >= 0:
                # take whole object
                cloud_points.extend(self.get_cloud_points(rotated_vertices))
                #self.get_logger().info(f'Taking whole object {id}')
            elif x_max < 0:
                # skip this object
                #self.get_logger().info(f'Skipping object {id}')
                continue
            else:
                # clip the object
                #self.get_logger().info(f'Clipping object {id}')
                clipped_vertices = self.clip(rotated_vertices)
                if clipped_vertices is not None:
                    cloud_points.extend(self.get_cloud_points(clipped_vertices))
        return cloud_points

    def get_translation_vector(self):
        # transform points to car local world coordinate
        return np.array([self.x,self.y,self.z]) * -1

    def publish_cloud_points(self):
        cloud_points = self.find_objects_inFrontOf_camera()
        if len(cloud_points) == 0:
            return
        #translation_vector = self.get_translation_vector()
        # make points relative to car pose as vslam will publish
        #translated_points = cloud_points + translation_vector
        #rotation_matrix = self.get_rotation_matrix()
        #rotated_points = np.dot(translated_points,rotation_matrix)
        # prepare message to be published
        try:
            # Create the PointCloud2 message
            msg = PointCloud2()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'base_link'

            # Define the structure (X, Y, Z)
            msg.height = 1
            msg.width = len(cloud_points)
            msg.fields = [
                PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
                PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
                PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            ]
            msg.is_bigendian = False
            msg.point_step = 12
            msg.row_step = msg.point_step * msg.width
            msg.is_dense = True
            msg.data = np.ascontiguousarray(cloud_points, dtype=np.float32).tobytes()

            self.cloud_pub.publish(msg)
            #self.get_logger().info(f'Published {len(rotated_points)} points.')
        except Exception as e:
            self.get_logger().error(f'Failed to publish points: {e}')
        
                
    def cmd_callback(self, msg):
        # Move the virtual car based on Nav2 commands
        self.linear_x = msg.linear.x
        self.angular_z = msg.angular.z

    def update(self):
        # 1. Update kinematics synchronously using steady 10Hz timer steps
        self.x += self.linear_x * math.cos(self.th) * self.dt
        self.y += self.linear_x * math.sin(self.th) * self.dt
        self.th += self.angular_z * self.dt

        # 2. publish geometric point cloud
        self.publish_cloud_points()

        # 3. Broadcast system transformations (Odom -> Base Link)
        tf_odom_base_link = TransformStamped()
        tf_odom_base_link.header.stamp = self.get_clock().now().to_msg()
        tf_odom_base_link.header.frame_id = 'odom'
        tf_odom_base_link.child_frame_id = 'base_link'
        tf_odom_base_link.transform.translation.x = self.x - self.car_initial_pose[0]
        tf_odom_base_link.transform.translation.y = self.y - self.car_initial_pose[1]
        tf_odom_base_link.transform.translation.z = self.z - self.car_initial_pose[2]
        tf_odom_base_link.transform.rotation.z = math.sin((self.th - self.car_initial_pose[3]) / 2.0)
        tf_odom_base_link.transform.rotation.w = math.cos((self.th - self.car_initial_pose[3]) / 2.0)
        self.tf_broadcaster.sendTransform(tf_odom_base_link)

        # 4. Broadcast system transformations (map -> odom)
        tf_map_odom = TransformStamped()
        tf_map_odom.header.stamp = self.get_clock().now().to_msg()
        tf_map_odom.header.frame_id = 'map'
        tf_map_odom.child_frame_id = 'odom'
        tf_map_odom.transform.translation.x = self.car_initial_pose[0]
        tf_map_odom.transform.translation.y = self.car_initial_pose[1]
        tf_map_odom.transform.translation.z = self.car_initial_pose[2]
        tf_map_odom.transform.rotation.z = math.sin(self.car_initial_pose[3] / 2.0)
        tf_map_odom.transform.rotation.w = math.cos(self.car_initial_pose[3] / 2.0)
        self.tf_broadcaster.sendTransform(tf_map_odom)

        # 5. Publish Odometry
        odom_msg = Odometry()
        odom_msg.header.stamp = self.get_clock().now().to_msg()
        odom_msg.header.frame_id = 'odom'
        odom_msg.child_frame_id = 'base_link'
        
        # Set the absolute position (Pose)
        odom_msg.pose.pose.position.x = self.x
        odom_msg.pose.pose.position.y = self.y
        odom_msg.pose.pose.position.z = self.z
        odom_msg.pose.pose.orientation.z = math.sin(self.th / 2.0)
        odom_msg.pose.pose.orientation.w = math.cos(self.th / 2.0)

        # Set the local velocities (Twist) local to car frame
        odom_msg.twist.twist.linear.x = self.linear_x
        odom_msg.twist.twist.linear.y = 0.0
        odom_msg.twist.twist.linear.z = 0.0
        odom_msg.twist.twist.angular.z = self.angular_z

        # Publish the topic message
        self.odom_pub.publish(odom_msg)

def main():
    rclpy.init()
    node = SimpleSim()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Check if the node hasn't been destroyed yet before tearing down
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()