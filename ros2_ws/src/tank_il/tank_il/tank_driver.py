"""/tank/command を /cmd_vel と砲塔の関節指令に変換するノード。

/tank/command: Float32MultiArray [throttle, steering, turret_angle]
  throttle      -1.0〜1.0（後進〜全開）
  steering      -1.0〜1.0（左〜右）
  turret_angle  砲塔の目標角度 [rad]（正が左回り）
"""
import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, Float64


class TankDriver(Node):
    def __init__(self):
        super().__init__('tank_driver')
        self.declare_parameter('v_max', 4.0)        # 全開時の速度 [m/s]
        self.declare_parameter('omega_max', 1.5)    # ハンドル全切り時の角速度 [rad/s]
        self.declare_parameter('timeout', 0.5)      # 指令が途絶えたら停止するまでの時間 [s]
        self.v_max = self.get_parameter('v_max').value
        self.omega_max = self.get_parameter('omega_max').value
        self.timeout = self.get_parameter('timeout').value

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.turret_pub = self.create_publisher(Float64, '/tank/turret_cmd', 10)
        self.create_subscription(Float32MultiArray, '/tank/command', self.on_command, 10)
        self.last_rx = None
        self.stopped = True
        self.create_timer(0.1, self.watchdog)

    def on_command(self, msg):
        if len(msg.data) < 3:
            self.get_logger().warn('/tank/command は3次元 [throttle, steering, turret_angle] が必要')
            return
        throttle = max(-1.0, min(1.0, msg.data[0]))
        steering = max(-1.0, min(1.0, msg.data[1]))
        turret = max(-math.pi, min(math.pi, msg.data[2]))

        twist = Twist()
        twist.linear.x = throttle * self.v_max
        # ROS の角速度は左回りが正。ハンドルは右が正なので符号を反転する。
        # スロットルが 0 のままハンドルを切るとその場旋回になる。
        twist.angular.z = -steering * self.omega_max
        self.cmd_pub.publish(twist)
        self.turret_pub.publish(Float64(data=float(turret)))
        self.last_rx = self.get_clock().now()
        self.stopped = False

    def watchdog(self):
        """teleop や方策ノードが落ちたときに暴走しないよう、指令が途絶えたら停止する"""
        if self.last_rx is None or self.stopped:
            return
        if (self.get_clock().now() - self.last_rx).nanoseconds * 1e-9 > self.timeout:
            self.cmd_pub.publish(Twist())
            self.stopped = True
            self.get_logger().warn('/tank/command が途絶えたため停止指令を送信')


def main():
    rclpy.init()
    node = TankDriver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
