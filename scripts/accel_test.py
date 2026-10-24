"""加速・減速・旋回の特性を測る（全開→停止、その場旋回）。使い方: python3 scripts/accel_test.py"""
import rclpy, time
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
from nav_msgs.msg import Odometry

class T(Node):
    def __init__(s):
        super().__init__('accel_test', parameter_overrides=[rclpy.parameter.Parameter('use_sim_time', value=True)])
        s.pub = s.create_publisher(Float32MultiArray, '/tank/command', 10)
        s.create_subscription(Odometry, '/odom', s.cb, 10)
        s.v = s.w = s.x = 0.0; s.t = 0.0
    def cb(s, m):
        s.v = m.twist.twist.linear.x; s.w = m.twist.twist.angular.z
        s.x = m.pose.pose.position.x; s.t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9

def run(n, cmd, dur, rows, tag):
    t0 = n.t
    while n.t - t0 < dur:
        n.pub.publish(Float32MultiArray(data=cmd))
        rclpy.spin_once(n, timeout_sec=0.05)
        rows.append((tag, n.t - t0, n.v, n.w, n.x))

rclpy.init(); n = T()
while n.t == 0.0: rclpy.spin_once(n, timeout_sec=0.1)
rows = []
run(n, [1.0, 0, 0], 30, rows, 'accel')
x_brake = n.x; run(n, [0.0, 0, 0], 12, rows, 'brake')
print('停止距離 [m]:', round(n.x - x_brake, 1))
run(n, [0.0, 1.0, 0], 8, rows, 'pivot')
for tag in ('accel', 'brake', 'pivot'):
    r = [x for x in rows if x[0] == tag]
    for sec in (1, 2, 4, 8, 12, 16, 20, 30):
        c = [x for x in r if x[1] >= sec]
        if c: print(tag, f't={sec:>2}s v={c[0][2]:6.2f} m/s ({c[0][2]*3.6:5.1f} km/h) w={c[0][3]:5.2f}')
