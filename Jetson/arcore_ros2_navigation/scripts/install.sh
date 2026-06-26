#!/usr/bin/env bash
set -eo pipefail

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo "ROS 2 Humble is not installed at /opt/ros/humble."
  exit 1
fi

sudo apt update
sudo apt install -y \
  python3-colcon-common-extensions \
  python3-numpy \
  python3-pip \
  python3-rosdep \
  i2c-tools \
  adb \
  ros-humble-rtabmap-ros \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-nav2-rviz-plugins \
  ros-humble-rviz2 \
  ros-humble-tf2-ros \
  ros-humble-teleop-twist-keyboard

python3 -m pip install --user --upgrade Jetson.GPIO adafruit-circuitpython-servokit

echo "Dependencies installed."
