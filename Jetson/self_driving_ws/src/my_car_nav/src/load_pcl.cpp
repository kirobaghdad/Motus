#include <pcl/io/pcd_io.h>
#include <pcl_conversions/pcl_conversions.h>

void load_and_publish() {
    pcl::PointCloud<pcl::PointXYZ>::Ptr cloud(new pcl::PointCloud<pcl::PointXYZ>);
    
    // 1. Load the file
    if (pcl::io::loadPCDFile<pcl::PointXYZ>("your_scan.pcd", *cloud) == -1) {
        RCLCPP_ERROR(this->get_logger(), "Couldn't read file!");
        return;
    }

    // 2. Convert to ROS message type
    sensor_msgs::msg::PointCloud2 output_msg;
    pcl::toROSMsg(*cloud, output_msg);
    
    // 3. Set the header to match your RViz / Map
    output_msg.header.frame_id = "map";
    output_msg.header.stamp = this->now();

    pub_->publish(output_msg);
}

int main(){
    load_and_publish();
    return 0;    
}