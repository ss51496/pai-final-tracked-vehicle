"""v2 の地形を一定スロットルで走り、飛び（空中時間・最高の高さ）と砲身の接触を測る。
使い方: python3 scripts/terrain_probe.py <スロットル> <目標x> [砲塔角rad] [切替x 切替後スロットル]
車両は x=0 から出発（reset はしない。先に scripts/reset_tank.sh で戻す）。
"""
import sys, math, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32MultiArray
from ros_gz_interfaces.msg import Contacts
from nav_msgs.msg import Odometry

thr, goal = float(sys.argv[1]), float(sys.argv[2])
turret = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
sw_x, sw_thr = (float(sys.argv[4]), float(sys.argv[5])) if len(sys.argv) > 5 else (1e9, thr)
CT = '/world/course/model/tank/link/turret/sensor/barrel_contact/contact'

class P(Node):
    def __init__(s):
        super().__init__('terrain_probe', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        s.pub = s.create_publisher(Float32MultiArray, '/tank/command', 10)
        s.create_subscription(Float32MultiArray, '/tank/state', s.st, 10)
        s.create_subscription(Imu, '/imu', s.imu, 10)
        s.create_subscription(Contacts, CT, s.ct, 10)
        s.create_subscription(Odometry, '/odom_gt', s.gt, 50)
        s.zs = []; s.dv = 0.0   # 衝撃 = 0.1 秒間の鉛直速度の変化の最大値 [m/s]
        s.acc = 9.8; s.shock = 0.0; s.pitch = 0.0; s.trace = []; s.x = s.z = s.v = 0.0; s.air = 0; s.contacts = 0; s.have = False; s.peak = -9; s.airlog = []
    def st(s, m):
        s.x, s.z, s.pitch, s.v, _ = m.data[:5]; s.have = True; s.peak = max(s.peak, s.z)
        s.trace.append((round(s.x, 1), round(s.z, 2), round(s.pitch, 2), round(s.acc, 1)))
    def imu(s, m):
        a = m.linear_acceleration
        s.acc = math.sqrt(a.x**2 + a.y**2 + a.z**2); s.shock = max(s.shock, s.acc)
        if math.sqrt(a.x**2 + a.y**2 + a.z**2) < 3.0:
            s.air += 1; s.airlog.append(round(s.x, 1))
    def ct(s, m):
        if m.contacts: s.contacts += 1
    def gt(s, m):
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        s.zs.append((t, m.pose.pose.position.z))
        # 0.05 秒間隔の鉛直速度を 2 つ並べて、0.1 秒間の変化を見る
        pts = [p for p in s.zs if t - p[0] <= 0.12]
        s.zs = pts
        if len(pts) >= 5:
            h = len(pts) // 2
            v1 = (pts[h][1] - pts[0][1]) / max(pts[h][0] - pts[0][0], 1e-3)
            v2 = (pts[-1][1] - pts[h][1]) / max(pts[-1][0] - pts[h][0], 1e-3)
            s.dv = max(s.dv, v2 - v1)
    def now(s): return s.get_clock().now().nanoseconds * 1e-9

rclpy.init(); n = P()
while not n.have or n.x > 50: rclpy.spin_once(n, timeout_sec=0.1)
t0 = n.now(); vmax = 0
while n.now() - t0 < 60 and n.x < goal:
    t = sw_thr if n.x >= sw_x else thr
    n.pub.publish(Float32MultiArray(data=[t, 0.0, turret])); rclpy.spin_once(n, timeout_sec=0.02)
    vmax = max(vmax, n.v)
print(f'x={n.x:.1f} 最高z={n.peak:.2f} 最高速度={vmax*3.6:.0f}km/h 空中={n.air/50:.2f}s 着地衝撃={n.dv:.1f}m/s 接触={n.contacts} 時間={n.now()-t0:.1f}s')
import os
if os.environ.get('TRACE'):
    for r in n.trace[::5]:
        if float(os.environ['TRACE']) <= r[0] <= float(os.environ['TRACE']) + 12: print('  x,z,pitch,|a| =', r)
if n.airlog: print('空中のx範囲:', min(n.airlog), '〜', max(n.airlog))
for _ in range(20): n.pub.publish(Float32MultiArray(data=[0.0, 0.0, turret])); rclpy.spin_once(n, timeout_sec=0.05)
