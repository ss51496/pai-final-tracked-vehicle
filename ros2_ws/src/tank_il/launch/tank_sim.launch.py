"""Gazebo・bridge・tank_driver・state_publisher を1つで起動する launch ファイル。

  ros2 launch tank_il tank_sim.launch.py                # 平地 world（GUI あり）
  ros2 launch tank_il tank_sim.launch.py world:=berm    # 他の world
  ros2 launch tank_il tank_sim.launch.py headless:=true # GUI なし（動作確認用）
  ros2 launch tank_il tank_sim.launch.py side_view:=false  # カメラを動かさない
  ros2 launch tank_il tank_sim.launch.py video:=true       # 動画撮影用（3D ビューのみ、1280x720）

GUI のカメラは起動後に横から見る位置へ移動する（side_view:=true、既定）。
"""
import math
import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, TimerAction
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
    elif context.launch_configurations['video'].lower() == 'true':
        gz_cmd += ['--gui-config', os.path.join(pkg, 'config', context.launch_configurations['gui_config'])]
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
    lc = context.launch_configurations
    driver = Node(package='tank_il', executable='tank_driver', output='screen',
                  parameters=[sim_time, {'v_max': float(lc['v_max']), 'omega_max': float(lc['omega_max'])}])
    state = Node(package='tank_il', executable='state_publisher', output='screen',
                 parameters=[sim_time])
    actions = [gazebo, bridge, driver, state]

    video = context.launch_configurations['video'].lower() == 'true'
    if not headless and not video and context.launch_configurations['side_view'].lower() == 'true':
        # カメラの位置 (x y z) とピッチ・ヨー [rad]。ヨー +90° で +y 向き（コースを横から見る）
        x, y, z = (float(v) for v in context.launch_configurations['camera_xyz'].split())
        pitch, yaw = 0.05, math.pi / 2
        cy, sy, cp, sp = math.cos(yaw / 2), math.sin(yaw / 2), math.cos(pitch / 2), math.sin(pitch / 2)
        req = (f'pose: {{position: {{x: {x}, y: {y}, z: {z}}}, '
               f'orientation: {{x: {-sp * sy:.5f}, y: {sp * cy:.5f}, z: {cp * sy:.5f}, w: {cp * cy:.5f}}}}}')
        move_camera = ExecuteProcess(
            cmd=['ign', 'service', '-s', '/gui/move_to/pose',
                 '--reqtype', 'ignition.msgs.GUICamera', '--reptype', 'ignition.msgs.Boolean',
                 '--timeout', '5000', '--req', req],
            output='screen')
        actions.append(TimerAction(period=8.0, actions=[move_camera]))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='flat'),
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('side_view', default_value='true'),
        DeclareLaunchArgument('video', default_value='false'),
        DeclareLaunchArgument('gui_config', default_value='video_gui.config'),
        DeclareLaunchArgument('camera_xyz', default_value='7.0 -17.0 2.0'),
        # tank_driver の上限。v2（80 km/h 級）は v_max:=22.22 omega_max:=1.0
        DeclareLaunchArgument('v_max', default_value='4.0'),
        DeclareLaunchArgument('omega_max', default_value='1.5'),
        OpaqueFunction(function=build),
    ])
