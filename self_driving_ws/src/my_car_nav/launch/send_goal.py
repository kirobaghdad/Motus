import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction

def generate_launch_description():

    # The command to send the goal
    # Note: We use a single string for 'cmd' when 'shell=True' is used
    send_goal_cmd = (
        'ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose '
        '"{pose: {header: {frame_id: \'map\'}, '
        'pose: {position: {x: 5.0, y: 2.0, z: 0.0}, '
        'orientation: {w: 1.0}}}}"'
    )

    send_goal = ExecuteProcess(
        cmd=[send_goal_cmd],
        shell=True,
        output='screen'
    )

    # Delay the goal by 10 seconds to give Nav2/VSLAM time to start
    delayed_goal = TimerAction(
        period=10.0,
        actions=[send_goal]
    )

    return LaunchDescription([
        delayed_goal
    ])