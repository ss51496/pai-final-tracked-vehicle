"""Gazebo・bridge・tank_driver・state_publisher を1つで起動する launch ファイル。

  ros2 launch tank_il tank_sim.launch.py                # 平地 world（GUI あり）
  ros2 launch tank_il tank_sim.launch.py world:=berm    # 他の world
  ros2 launch tank_il tank_sim.launch.py headless:=true # GUI なし（動作確認用）
"""
import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch_ros.actions import Node


def build(context):
    pkg = get_package_share_directory('tank_il')
    world = context.launch_configurations['world']
    headless = context.launch_configurations['headless'].lower() == 'true'

    resource_path = os.pathsep.join([
        os.path.join(pkg, 'models'),
        os.path.join(pkg, 'worlds'),
        os.environ.get('IGN_GAZEBO_RESOURCE_PATH', ''),
    ])
    gz_cmd = ['ign', 'gazebo', '-r', os.path.join(pkg, 'worlds', world + '.sdf')]
    if headless:
        gz_cmd.insert(2, '-s')
    gazebo = ExecuteProcess(
        cmd=gz_cmd, output='screen',
        additional_env={'IGN_GAZEBO_RESOURCE_PATH': resource_path})

    # config/bridge.yaml を parameter_bridge の引数 'topic@ROS型[Gz型' 形式に展開する
    with open(os.path.join(pkg, 'config', 'bridge.yaml')) as f:
        entries = yaml.safe_load(f)
    sep = {'ros_to_gz': ']', 'gz_to_ros': '[', 'bidirectional': '@'}
    args = [f"{e['topic']}@{e['ros_type']}{sep[e['direction']]}{e['gz_type']}" for e in entries]
    bridge = Node(package='ros_gz_bridge', executable='parameter_bridge',
                  arguments=args, output='screen')

    sim_time = {'use_sim_time': True}
    driver = Node(package='tank_il', executable='tank_driver', output='screen',
                  parameters=[sim_time])
    state = Node(package='tank_il', executable='state_publisher', output='screen',
                 parameters=[sim_time])
    return [gazebo, bridge, driver, state]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='flat'),
        DeclareLaunchArgument('headless', default_value='false'),
        OpaqueFunction(function=build),
    ])
