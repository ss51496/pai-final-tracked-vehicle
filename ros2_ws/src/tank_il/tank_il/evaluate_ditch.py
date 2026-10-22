"""壕の通過を複数回試行して、結果を記録する評価ノード。

  # ルールベース（砲塔の角度と速度を固定した手順）
  ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 90 --entry-throttle 0.25 --switch-x 7.0
  ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 0 --entry-throttle 0.25     # 砲塔が前向き（失敗例）
  # 方策（policy_node を別に起動しておく。砲塔の操作も方策が行う）
  ros2 run tank_il evaluate_ditch --mode policy

1 回の試行: 車両をリセット → 走行 → x が GOAL_X に達する（または TIMEOUT 秒、または 6 秒以上動かない）まで。
記録: 通過したか、砲身が壁などに接触したか（接触センサーのメッセージ数）、最低の z、所要時間（シミュレーション時刻）。

「接触せずに通過」＝通過した  かつ  砲身の接触が 0 件（これが主な評価指標）
参考として「飛ばずに通過」＝接触せずに通過  かつ  空中の時間が HOP_AIR_SEC 未満 も記録する
（壕の出口を全開で登ると、出口の縁から飛び出す。空中＝IMU の加速度の大きさが小さい時間）
"""
import argparse
import csv
import math
import subprocess
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from ros_gz_interfaces.msg import Contacts
from sensor_msgs.msg import Imu
from std_msgs.msg import Empty, Float32MultiArray

GOAL_X = 12.0
TIMEOUT = 40.0          # [s]（シミュレーション時刻）
STUCK_SEC = 6.0         # この秒数 x が進まなければ「動けなくなった」とみなす
RESET_SCRIPT = '/workspace/scripts/reset_tank.sh'
SPLIT_X = 8.4          # 壕の中央。これより手前を「入るとき」、先を「出るとき」とする
HOP_AIR_SEC = 0.6      # [s] これ以上空中にいたら「飛び越えた」とみなす
AIR_ACC = 3.0          # [m/s^2]
CONTACT_TOPIC = '/world/course/model/tank/link/turret/sensor/barrel_contact/contact'


class Evaluator(Node):
    def __init__(self, args):
        super().__init__('evaluate_ditch', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.args = args
        self.state = None
        self.contacts = 0
        self.counting = False
        self.cmd_pub = self.create_publisher(Float32MultiArray, '/tank/command', 10)
        self.reset_pub = self.create_publisher(Empty, '/tank/policy_reset', 10)
        self.create_subscription(Float32MultiArray, '/tank/state', lambda m: setattr(self, 'state', list(m.data)), 10)
        self.create_subscription(Contacts, CONTACT_TOPIC, self.on_contact, 10)
        self.air_samples = 0
        self.air_in = 0
        self.air_out = 0
        self.create_subscription(Imu, '/imu', self.on_imu, 10)

    def on_contact(self, msg):
        if self.counting and msg.contacts:
            self.contacts += 1

    def on_imu(self, msg):
        a = msg.linear_acceleration
        if self.counting and math.sqrt(a.x ** 2 + a.y ** 2 + a.z ** 2) < AIR_ACC:
            self.air_samples += 1
            if self.state is not None and self.state[0] < SPLIT_X:
                self.air_in += 1
            else:
                self.air_out += 1

    def sim_now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def spin_for(self, sec, cmd=None):
        t0 = time.time()
        while time.time() - t0 < sec:
            if cmd is not None:
                self.cmd_pub.publish(Float32MultiArray(data=cmd))
            rclpy.spin_once(self, timeout_sec=0.02)

    def stop(self):
        self.spin_for(0.5, [0.0, 0.0, 0.0])

    def command(self):
        """scripted モードの指令。砲塔は最初から目標角、速度は switch_x を越えたら全開"""
        a = self.args
        thr = 1.0 if (a.switch_x is not None and self.state[0] >= a.switch_x) else a.entry_throttle
        return [thr, 0.0, math.radians(a.turret_deg)]

    def run_trial(self):
        a = self.args
        self.counting = False
        self.stop()
        subprocess.run([RESET_SCRIPT], check=True, stdout=subprocess.DEVNULL)
        self.reset_pub.publish(Empty())
        self.spin_for(1.0)
        self.state = None
        while self.state is None:
            rclpy.spin_once(self, timeout_sec=0.1)
        if a.mode == 'scripted':
            self.spin_for(3.0, [0.0, 0.0, math.radians(a.turret_deg)])   # 動き出す前に砲塔を回す
        self.contacts = 0
        self.air_samples = 0
        self.air_in = 0
        self.air_out = 0
        self.counting = True
        t0 = self.sim_now()
        min_z = self.state[1]
        last_x, last_move = self.state[0], self.sim_now()
        outcome = 'timeout'
        while self.sim_now() - t0 < TIMEOUT:
            if a.mode == 'scripted':
                self.cmd_pub.publish(Float32MultiArray(data=self.command()))
            rclpy.spin_once(self, timeout_sec=0.02)
            s = self.state
            min_z = min(min_z, s[1])
            if abs(s[0] - last_x) > 0.05:
                last_x, last_move = s[0], self.sim_now()
            if s[0] >= GOAL_X:
                outcome = 'passed'
                break
            if self.sim_now() - last_move > STUCK_SEC:
                outcome = 'stuck'
                break
        t_end = self.sim_now() - t0
        self.counting = False
        final_x = self.state[0]
        turret_deg = math.degrees(self.state[4])
        self.stop()
        air = self.air_samples / 50.0
        ok = outcome == 'passed' and self.contacts == 0
        no_hop = ok and air < HOP_AIR_SEC
        return dict(outcome=outcome, contact_msgs=self.contacts, air_sec=round(air, 2), air_in_sec=round(self.air_in / 50.0, 2), air_out_sec=round(self.air_out / 50.0, 2), no_contact_pass=ok, no_hop_pass=no_hop, min_z=round(min_z, 3),
                    time_sec=round(t_end, 1), final_x=round(final_x, 2), turret_deg=round(turret_deg))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['scripted', 'policy'], required=True)
    ap.add_argument('--turret-deg', type=float, default=90.0)
    ap.add_argument('--entry-throttle', type=float, default=0.25)
    ap.add_argument('--switch-x', type=float, default=None, help='この x を越えたら全開にする（省略時は切り替えない）')
    ap.add_argument('--trials', type=int, default=10)
    ap.add_argument('--out', default='')
    args, ros_args = ap.parse_known_args()
    rclpy.init(args=ros_args)
    node = Evaluator(args)
    label = 'policy' if args.mode == 'policy' else (
        f'scripted(turret={args.turret_deg:.0f}, thr={args.entry_throttle}, switch_x={args.switch_x})')
    rows = []
    for i in range(args.trials):
        r = node.run_trial()
        r['trial'] = i
        rows.append(r)
        print(f"[{label}] trial {i}: {r['outcome']} 接触={r['contact_msgs']} 接触せずに通過={'○' if r['no_contact_pass'] else '×'} 空中={r['air_sec']}s(入{r['air_in_sec']}/出{r['air_out_sec']}) 飛ばずに通過={'○' if r['no_hop_pass'] else '×'} "
              f"所要={r['time_sec']}s 最低z={r['min_z']} 最終x={r['final_x']} 砲塔={r['turret_deg']}deg", flush=True)
    n_pass = sum(r['outcome'] == 'passed' for r in rows)
    n_ok = sum(r['no_contact_pass'] for r in rows)
    n_nohop = sum(r['no_hop_pass'] for r in rows)
    print(f"[{label}] {args.trials} 回中: 通過 {n_pass} 回、接触せずに通過 {n_ok} 回、飛ばずに通過 {n_nohop} 回")
    if args.out:
        with open(args.out, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['trial', 'outcome', 'contact_msgs', 'air_sec', 'air_in_sec', 'air_out_sec', 'no_contact_pass', 'no_hop_pass', 'min_z',
                                              'time_sec', 'final_x', 'turret_deg'])
            w.writeheader()
            w.writerows(rows)
    node.stop()
    node.destroy_node()
    rclpy.try_shutdown()
