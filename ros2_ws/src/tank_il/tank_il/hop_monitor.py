"""操縦中に、壕を 1 回通過するたびに「飛び」を表示するモニタ（テレオペの練習・デモの確認用）。

  ros2 run tank_il hop_monitor

通過（x が GOAL_X に達する）、または動きが止まるたびに、次の 1 行を表示する。
  入るとき／出るときの空中の時間（IMU の加速度の大きさが小さい時間）、最高の高さ、砲身の接触、所要時間
飛びを抑えつつ速く通過するための目安にする。車両をリセットして x が小さくなると、次の回を始める。
空中の時間が長いほど車体が飛んでおり、衝撃が大きい（目安は 0.3 秒未満）。
"""
import math

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from ros_gz_interfaces.msg import Contacts
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32MultiArray

SPLIT_X = 8.4          # 壕の中央。これより手前を「入るとき」、先を「出るとき」とする
GOAL_X = 12.0
AIR_ACC = 3.0          # [m/s^2]
GOOD_AIR = 0.3         # [s] これ未満なら「飛びなし」の目安
CONTACT_TOPIC = '/world/course/model/tank/link/turret/sensor/barrel_contact/contact'


class HopMonitor(Node):
    def __init__(self):
        super().__init__('hop_monitor', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.create_subscription(Float32MultiArray, '/tank/state', self.on_state, 10)
        self.create_subscription(Imu, '/imu', self.on_imu, 10)
        self.create_subscription(Contacts, CONTACT_TOPIC, self.on_contact, 10)
        self.reset()
        self.get_logger().info('hop_monitor 起動。壕を通過するたびに結果を表示します')

    def reset(self):
        self.moving = False
        self.done = False
        self.t_start = 0.0
        self.air_in = self.air_out = 0
        self.contacts = 0
        self.peak_z = 0.0
        self.x = 0.0
        self.last_move = 0.0

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_state(self, msg):
        x, z, _, v, _ = msg.data[:5]
        self.x = x
        if self.done:
            if x < 1.0:       # 車両がリセットされたので次の回へ
                self.reset()
            return
        if not self.moving:
            if abs(v) > 0.2:
                self.moving = True
                self.t_start = self.now()
                self.last_move = self.now()
            return
        self.peak_z = max(self.peak_z, z)
        if abs(v) > 0.1:
            self.last_move = self.now()
        if x >= GOAL_X or (self.now() - self.last_move > 3.0 and self.now() - self.t_start > 3.0):
            self.finish(x >= GOAL_X)

    def on_imu(self, msg):
        if not self.moving or self.done:
            return
        a = msg.linear_acceleration
        if math.sqrt(a.x ** 2 + a.y ** 2 + a.z ** 2) < AIR_ACC:
            if self.x < SPLIT_X:
                self.air_in += 1
            else:
                self.air_out += 1

    def on_contact(self, msg):
        if self.moving and not self.done and msg.contacts:
            self.contacts += 1

    def finish(self, passed):
        self.done = True
        t = self.now() - self.t_start
        ai, ao = self.air_in / 50.0, self.air_out / 50.0
        mark = lambda s: '飛びなし' if s < GOOD_AIR else '飛んだ'
        verdict = '通過' if passed else f'停止（x={self.x:.1f} m）'
        contact = f'砲身の接触 {self.contacts} 件' if self.contacts else '砲身の接触なし'
        self.get_logger().info(
            f'[{verdict}] 所要 {t:.1f} 秒 ／ 空中：入るとき {ai:.2f} 秒（{mark(ai)}）、出るとき {ao:.2f} 秒（{mark(ao)}） ／ '
            f'最高の高さ z={self.peak_z:.2f} m ／ {contact}')


def main():
    rclpy.init()
    node = HopMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
