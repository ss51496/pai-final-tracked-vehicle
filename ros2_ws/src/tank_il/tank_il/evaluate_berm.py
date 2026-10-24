"""突堤の通過を複数回試行して、結果を記録する評価ノード。

  ros2 run tank_il evaluate_berm --mode const --throttle 1.0 --trials 10   # ルールベース（一定スロットル）
  ros2 run tank_il evaluate_berm --mode policy --trials 10                 # 方策（policy_node を別に起動しておく）

1 回の試行: 車両をリセット → 走行 → x が GOAL_X に達する（または TIMEOUT 秒）まで。
記録: 通過したか、最高の z、空中の時間（IMU の加速度の大きさが小さい時間）、通過までの時間。

「跳ねずに通過」の判定:  通過した  かつ  最高の z < HOP_Z  かつ  空中の時間 < HOP_AIR_SEC
閾値は、熟練者のデモ（最高の z が 1.40〜1.61 m）と、全開（約 1.8 m）の測定値から決めた。
"""
import argparse
import csv
import math
import subprocess
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import Imu
from std_msgs.msg import Empty, Float32MultiArray

from tank_il.impact_meter import ImpactMeter

GOAL_X = 13.0          # 山（x=6〜9.5 m）を越えた先
TIMEOUT = 40.0         # [s]
HOP_Z = 1.70           # [m] これ以上高く跳ね上がったら「跳ねた」
HOP_AIR_SEC = 0.60     # [s] これ以上空中にいたら「跳ねた」
AIR_ACC = 3.0          # [m/s^2] IMU の加速度の大きさがこれ未満なら空中とみなす
RESET_SCRIPT = '/workspace/scripts/reset_tank.sh'


class Evaluator(Node):
    def __init__(self, mode, throttle, goal_x=GOAL_X, timeout=TIMEOUT, impact_thr=0.0):
        # 所要時間はシミュレーション時刻で測る（他の処理で実時間より遅く動いても公平になる）
        super().__init__('evaluate_berm', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.mode = mode
        self.goal_x, self.timeout, self.impact_thr = goal_x, timeout, impact_thr
        self.impact = ImpactMeter(self)
        self.throttle = throttle
        self.state = None
        self.acc = 9.8
        self.air_samples = 0
        self.counting = False
        self.cmd_pub = self.create_publisher(Float32MultiArray, '/tank/command', 10)
        self.reset_pub = self.create_publisher(Empty, '/tank/policy_reset', 10)
        self.hold_pub = self.create_publisher(Empty, '/tank/policy_hold', 10)
        self.create_subscription(Float32MultiArray, '/tank/state', self.on_state, 10)
        self.create_subscription(Imu, '/imu', self.on_imu, 10)

    def on_state(self, msg):
        self.state = list(msg.data)

    def on_imu(self, msg):
        a = msg.linear_acceleration
        self.acc = math.sqrt(a.x ** 2 + a.y ** 2 + a.z ** 2)
        if self.counting and self.acc < AIR_ACC:
            self.air_samples += 1

    def sim_now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def spin_for(self, sec):
        t0 = time.time()
        while time.time() - t0 < sec:
            rclpy.spin_once(self, timeout_sec=0.02)

    def stop(self):
        for _ in range(10):
            self.cmd_pub.publish(Float32MultiArray(data=[0.0, 0.0, 0.0]))
            self.spin_for(0.05)

    def run_trial(self):
        self.counting = False
        self.stop()
        for _ in range(5):                      # リセット中は方策を止める（走り出して先へ進まないように）
            self.hold_pub.publish(Empty())
            self.spin_for(0.1)
        subprocess.run([RESET_SCRIPT], check=True, stdout=subprocess.DEVNULL)
        self.reset_pub.publish(Empty())         # 方策の行動チャンクを空にして再開する
        self.spin_for(1.0)
        self.state = None
        while self.state is None:
            rclpy.spin_once(self, timeout_sec=0.1)
        self.impact.reset()
        self.air_samples = 0
        self.counting = True
        t0 = self.sim_now()
        peak_z = self.state[1]
        reached = False
        while self.sim_now() - t0 < self.timeout:
            if self.mode == 'const':
                self.cmd_pub.publish(Float32MultiArray(data=[self.throttle, 0.0, 0.0]))
            rclpy.spin_once(self, timeout_sec=0.02)
            peak_z = max(peak_z, self.state[1])
            if self.state[0] >= self.goal_x:
                reached = True
                break
        t_end = self.sim_now() - t0
        self.counting = False
        final_x, final_z = self.state[0], self.state[1]
        self.stop()
        air = self.air_samples / 50.0
        if self.impact_thr > 0:                 # v2：着地衝撃（真値の鉛直速度の変化）で判定する
            no_hop = reached and self.impact.peak < self.impact_thr
        else:
            no_hop = reached and peak_z < HOP_Z and air < HOP_AIR_SEC
        return dict(impact=round(self.impact.peak, 2), reached=reached, no_hop_pass=no_hop, peak_z=round(peak_z, 3), air_sec=round(air, 2),
                    time_sec=round(t_end, 1), final_x=round(final_x, 2), final_z=round(final_z, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['const', 'policy'], required=True)
    ap.add_argument('--throttle', type=float, default=1.0, help='const のときの一定スロットル')
    ap.add_argument('--trials', type=int, default=10)
    ap.add_argument('--goal-x', type=float, default=GOAL_X, help='通過とみなす x [m]（既定は v1 の突堤）')
    ap.add_argument('--timeout', type=float, default=TIMEOUT, help='1 試行の上限 [s]')
    ap.add_argument('--impact-thr', type=float, default=0.0, help='0 より大きいと、着地衝撃がこの値 [m/s] 未満を「跳ねずに通過」とする（v2）')
    ap.add_argument('--out', default='', help='結果の CSV の保存先')
    args, ros_args = ap.parse_known_args()
    rclpy.init(args=ros_args)
    node = Evaluator(args.mode, args.throttle, args.goal_x, args.timeout, args.impact_thr)
    label = f'const({args.throttle})' if args.mode == 'const' else 'policy'
    rows = []
    for i in range(args.trials):
        r = node.run_trial()
        r['trial'] = i
        rows.append(r)
        print(f"[{label}] trial {i}: 通過={'○' if r['reached'] else '×'} 跳ねずに通過={'○' if r['no_hop_pass'] else '×'} "
              f"衝撃={r['impact']}m/s 最高z={r['peak_z']:.2f}m 空中={r['air_sec']:.2f}s 所要={r['time_sec']}s 最終x={r['final_x']}", flush=True)
    n_pass = sum(r['reached'] for r in rows)
    n_ok = sum(r['no_hop_pass'] for r in rows)
    print(f"[{label}] {args.trials} 回中: 通過 {n_pass} 回、跳ねずに通過 {n_ok} 回")
    if args.out:
        with open(args.out, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['trial', 'impact', 'reached', 'no_hop_pass', 'peak_z', 'air_sec',
                                              'time_sec', 'final_x', 'final_z'])
            w.writeheader()
            w.writerows(rows)
    node.stop()
    node.destroy_node()
    rclpy.try_shutdown()
