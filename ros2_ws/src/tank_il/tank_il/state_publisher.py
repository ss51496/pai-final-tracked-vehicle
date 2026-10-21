"""観測ベクトルをまとめて /tank/state に配信するノード。

/tank/state: Float32MultiArray [x, z, pitch, v_forward, turret_angle]
  x, z          /odom_gt（OdometryPublisher）の真値（world 座標 [m]）
  pitch         IMU から求めたピッチ角 [rad]。機首上げ（登り）が正
  v_forward     オドメトリの並進速度 [m/s]
  turret_angle  /joint_states の砲塔角 [rad]
"""
import math

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Imu, JointState
from std_msgs.msg import Float32MultiArray


def pitch_from_quaternion(q):
    """クォータニオンから ROS 規約(REP-103)のピッチを求める。機首下げが正になるので、
    人間に分かりやすいよう符号を反転して「機首上げ（登り）が正」にして返す。"""
    sinp = 2.0 * (q.w * q.y - q.z * q.x)
    sinp = max(-1.0, min(1.0, sinp))
    return -math.asin(sinp)


class StatePublisher(Node):
    def __init__(self):
        super().__init__('state_publisher')
        self.declare_parameter('rate', 20.0)

        self.x = self.z = 0.0
        self.pitch = 0.0
        self.v = 0.0
        self.turret = 0.0
        self.got = {'pose': False, 'imu': False, 'odom': False, 'joint': False}

        self.create_subscription(Odometry, '/odom_gt', self.on_pose, 10)
        self.create_subscription(Imu, '/imu', self.on_imu, 10)
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.create_subscription(JointState, '/joint_states', self.on_joint, 10)
        self.pub = self.create_publisher(Float32MultiArray, '/tank/state', 10)
        self.create_timer(1.0 / self.get_parameter('rate').value, self.publish)

    def on_pose(self, msg):
        self.x = msg.pose.pose.position.x
        self.z = msg.pose.pose.position.z
        self.got['pose'] = True

    def on_imu(self, msg):
        self.pitch = pitch_from_quaternion(msg.orientation)
        self.got['imu'] = True

    def on_odom(self, msg):
        self.v = msg.twist.twist.linear.x
        self.got['odom'] = True

    def on_joint(self, msg):
        if 'turret_joint' in msg.name:
            self.turret = msg.position[msg.name.index('turret_joint')]
            self.got['joint'] = True

    def publish(self):
        if not all(self.got.values()):
            return  # 全部そろうまでは配信しない（0 で埋めた偽の観測を記録しないため）
        msg = Float32MultiArray()
        msg.data = [float(v) for v in (self.x, self.z, self.pitch, self.v, self.turret)]
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = StatePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
