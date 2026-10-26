#!/usr/bin/env python3
"""車両の x を、起動からの経過秒つきで記録する（動画の「早送りにする区間」を決めるため）。
使い方: python3 scripts/xlog.py <出力ファイル> [最大秒]    各行は「経過秒 x」。"""
import sys
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray

rclpy.init()
n = Node('xlog')
t0 = time.time()
f = open(sys.argv[1], 'w')


def cb(m):
    f.write('%.2f %.2f\n' % (time.time() - t0, m.data[0]))
    f.flush()


n.create_subscription(Float32MultiArray, '/tank/state', cb, 10)
end = t0 + (float(sys.argv[2]) if len(sys.argv) > 2 else 150)
while time.time() < end:
    rclpy.spin_once(n, timeout_sec=0.1)
