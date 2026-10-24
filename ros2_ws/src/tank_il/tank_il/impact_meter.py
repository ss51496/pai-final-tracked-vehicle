"""着地衝撃の測定。/odom_gt の z から鉛直速度を求め、0.1 秒間の鉛直速度の変化の最大値 [m/s] を測る。

IMU の加速度の大きさ（空中の判定・最大値）は、長い車体が縁で前のめりになるだけでも反応し、衝撃の最大値も
測るたびに 1〜500 G とばらついた。真値の z から求めたこの量は、同じ条件で繰り返してもほぼ同じ値になる
（突堤、全開で 3.6 m/s、スロットル 0.2 で 1.2 m/s）。値は、落ちた高さ h との間に dv ≒ sqrt(2 g h) の関係がある。
"""
from nav_msgs.msg import Odometry


class ImpactMeter:
    def __init__(self, node, split_x=None):
        self.split_x = split_x          # 指定すると、この x より手前を「入るとき」、先を「出るとき」に分けて測る
        self.zs = []
        self.x = 0.0
        self.reset()
        node.create_subscription(Odometry, '/odom_gt', self._on_gt, 50)

    def reset(self):
        self.zs = []
        self.peak = 0.0
        self.peak_in = 0.0
        self.peak_out = 0.0

    def _on_gt(self, m):
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        self.x = m.pose.pose.position.x
        self.zs = [p for p in self.zs if t - p[0] <= 0.12] + [(t, m.pose.pose.position.z)]
        pts = self.zs
        if len(pts) < 5:
            return
        h = len(pts) // 2
        v1 = (pts[h][1] - pts[0][1]) / max(pts[h][0] - pts[0][0], 1e-3)
        v2 = (pts[-1][1] - pts[h][1]) / max(pts[-1][0] - pts[h][0], 1e-3)
        dv = v2 - v1
        self.peak = max(self.peak, dv)
        if self.split_x is not None:
            if self.x < self.split_x:
                self.peak_in = max(self.peak_in, dv)
            else:
                self.peak_out = max(self.peak_out, dv)
