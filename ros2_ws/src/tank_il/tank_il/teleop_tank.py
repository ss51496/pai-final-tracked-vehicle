"""アクセル＋ハンドル方式のキーボードテレオペ。/tank/command を 20Hz で配信し続ける。

  W / S      スロットルを 0.05 上げる / 下げる（細かい刻み）
  R / F      スロットルを 0.25 上げる / 下げる（大きい刻み）
  E / Space  全開 / 停止
  D / A      ハンドルを右 / 左へ 0.25 切る
  X          ハンドルを中立に戻す
  L / J      砲塔を右 / 左へ 5° 回す
  I / O / U  砲塔を 0° / 右90° / 左90° にする
  Q          終了
"""
import math
import select
import sys
import termios
import tty

import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, Float32MultiArray

THROTTLE_STEP = 0.05      # W / S（細かい刻み）。v2 は 1.0 が 80 km/h なので 0.05 が約 4 km/h
THROTTLE_STEP_COARSE = 0.25   # R / F
STEERING_STEP = 0.25
TURRET_STEP = math.radians(5.0)
PUBLISH_HZ = 20.0

HELP = __doc__


class TeleopTank(Node):
    def __init__(self):
        super().__init__('teleop_tank')
        self.declare_parameter('v_max', 22.22)   # スロットル 1.0 のときの速度 [m/s]（表示用。tank_driver の v_max と同じ値にする）
        self.v_max = self.get_parameter('v_max').value
        self.speed = 0.0
        self.create_subscription(Float32MultiArray, '/tank/state', lambda m: setattr(self, 'speed', m.data[3]), 10)
        self.pub = self.create_publisher(Float32MultiArray, '/tank/command', 10)
        self.throttle = 0.0
        self.steering = 0.0
        self.turret = 0.0
        # reset_tank.sh が /tank/teleop_reset を送ると、teleop の指令も 0 に戻る
        # （戻さないと、teleop が配信し続ける古い砲塔角の指令が、リセットの 0° を上書きしてしまう）
        self.create_subscription(Empty, '/tank/teleop_reset', self.on_reset, 10)
        self.create_timer(1.0 / PUBLISH_HZ, self.publish)

    def on_reset(self, _):
        self.throttle = self.steering = self.turret = 0.0

    def publish(self):
        msg = Float32MultiArray()
        msg.data = [self.throttle, self.steering, self.turret]
        self.pub.publish(msg)

    def handle_key(self, key):
        """キーを処理する。終了なら False を返す"""
        k = key.lower()
        if k == 'w':
            self.throttle = round(min(1.0, self.throttle + THROTTLE_STEP), 2)
        elif k == 's':
            self.throttle = round(max(-1.0, self.throttle - THROTTLE_STEP), 2)
        elif k == 'r':
            self.throttle = round(min(1.0, self.throttle + THROTTLE_STEP_COARSE), 2)
        elif k == 'f':
            self.throttle = round(max(-1.0, self.throttle - THROTTLE_STEP_COARSE), 2)
        elif k == 'e':
            self.throttle = 1.0
        elif k == ' ':
            self.throttle = 0.0
        elif k == 'd':
            self.steering = min(1.0, self.steering + STEERING_STEP)
        elif k == 'a':
            self.steering = max(-1.0, self.steering - STEERING_STEP)
        elif k == 'x':
            self.steering = 0.0
        elif k == 'l':   # 右へ = 角度を減らす（正が左回り）
            self.turret = max(-math.pi, self.turret - TURRET_STEP)
        elif k == 'j':
            self.turret = min(math.pi, self.turret + TURRET_STEP)
        elif k == 'i':
            self.turret = 0.0
        elif k == 'o':
            self.turret = -math.pi / 2
        elif k == 'u':
            self.turret = math.pi / 2
        elif k == 'q' or key == '\x03':
            return False
        return True

    def status(self):
        return (f'\rthrottle={self.throttle:+.2f}  steering={self.steering:+.2f}  '
                f'turret={math.degrees(self.turret):+6.1f} deg   ')


def main():
    if not sys.stdin.isatty():
        print('teleop_tank はターミナル（tty）から実行してください')
        return
    rclpy.init()
    node = TeleopTank()
    old = termios.tcgetattr(sys.stdin)
    print(HELP)
    try:
        tty.setcbreak(sys.stdin.fileno())
        running = True
        while running and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.0)
            if select.select([sys.stdin], [], [], 0.02)[0]:
                running = node.handle_key(sys.stdin.read(1))
            sys.stdout.write(node.status())
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        # 終了時は停止指令を数回送ってから止める
        node.throttle = 0.0
        node.steering = 0.0
        for _ in range(3):
            node.publish()
        print('\n終了')
        node.destroy_node()
        rclpy.try_shutdown()
