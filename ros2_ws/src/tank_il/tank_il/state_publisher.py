"""観測ベクトルをまとめて /tank/state に配信するノード。

/tank/state: Float32MultiArray [x, z, pitch, v_forward, turret_angle]
  x, z          /odom_gt（OdometryPublisher）の真値（world 座標 [m]）
  pitch         IMU から求めたピッチ角 [rad]。機首上げ（登り）が正
  v_forward     オドメトリの並進速度 [m/s]
  turret_angle  /joint_states の砲塔角 [rad]

extended:=true（v2）のときは、末尾に 3 つ足した 8 次元になる。
  vz            鉛直速度 [m/s]。/odom_gt の z を 0.1 秒の間隔で差分して求める（OdometryPublisher の twist は
                世界座標の鉛直速度と一致しなかったため使わない）。飛んでいるか・落ちているかを直接示す
  roll          IMU から求めたロール角 [rad]（右に傾くと正）。ピッチだけでは斜めの進入を見分けられない
  throttle_cmd  いま出しているスロットル指令（/tank/command の 1 番目）。行動チャンクの切り替えをなめらかにする
                注意：行動の写しになるので、方策が「前回の指令をそのまま出す」近道を覚えるおそれがある
"""
import math
from collections import deque

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Imu, JointState
from std_msgs.msg import Float32MultiArray


def roll_from_quaternion(q):
    """ロール角（x 軸まわり）。右に傾くと正"""
    return math.atan2(2.0 * (q.w * q.x + q.y * q.z), 1.0 - 2.0 * (q.x * q.x + q.y * q.y))


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
        self.declare_parameter('extended', False)   # True で vz・roll・throttle_cmd を足した 8 次元
        self.extended = self.get_parameter('extended').value
        self.vz = self.roll = self.throttle_cmd = 0.0
        self.zs = deque()

        self.x = self.z = 0.0
        self.pitch = 0.0
        self.v = 0.0
        self.turret = 0.0
        self.got = {'pose': False, 'imu': False, 'odom': False, 'joint': False}

        self.create_subscription(Odometry, '/odom_gt', self.on_pose, 10)
        self.create_subscription(Imu, '/imu', self.on_imu, 10)
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.create_subscription(JointState, '/joint_states', self.on_joint, 10)
        self.create_subscription(Float32MultiArray, '/tank/command', self.on_command, 10)
        self.pub = self.create_publisher(Float32MultiArray, '/tank/state', 10)
        self.create_timer(1.0 / self.get_parameter('rate').value, self.publish)

    def on_pose(self, msg):
        self.x = msg.pose.pose.position.x
        self.z = msg.pose.pose.position.z
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.zs.append((t, self.z))
        while len(self.zs) > 1 and t - self.zs[1][0] >= 0.1:    # 0.1 秒以上前の最も新しい点を基準にする
            self.zs.popleft()
        if t - self.zs[0][0] >= 0.05:
            self.vz = (self.z - self.zs[0][1]) / (t - self.zs[0][0])
        self.got['pose'] = True

    def on_command(self, msg):
        if msg.data:
            self.throttle_cmd = float(msg.data[0])

    def on_imu(self, msg):
        self.pitch = pitch_from_quaternion(msg.orientation)
        self.roll = roll_from_quaternion(msg.orientation)
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
        vals = [self.x, self.z, self.pitch, self.v, self.turret]
        if self.extended:
            vals += [self.vz, self.roll, self.throttle_cmd]
        msg.data = [float(v) for v in vals]
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
