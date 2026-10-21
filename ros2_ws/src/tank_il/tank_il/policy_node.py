"""学習した ACT 方策の推論ノード。/tank/state を購読し、/tank/command に 10Hz で配信する。

pai_training の pixi 環境（torch と lerobot が入っている）で実行する。ROS 2 を先に source しておくこと。
    source /opt/ros/humble/setup.bash && source /workspace/ros2_ws/install/setup.bash
    cd /workspace/pai_training
    pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py \
        --model-path /workspace/checkpoints/train/tank_berm_act

注意: 推論中は teleop_tank を必ず止めておく（同じ /tank/command に配信して競合するため）。
"""
import argparse
import math

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, Float32MultiArray

PUBLISH_HZ = 10.0     # 学習データの fps と同じ
STATE_TIMEOUT = 1.0   # この秒数 /tank/state が来なければ配信を止める（tank_driver が停止する）


class PolicyNode(Node):
    def __init__(self, model_path, device, n_action_steps=None):
        super().__init__('policy_node')
        # torch と lerobot は pixi 環境にしかないので、ここで読み込む
        import torch
        from lerobot.common.policies.act.modeling_act import ACTPolicy
        self.torch = torch
        self.device = torch.device(device)
        self.policy = ACTPolicy.from_pretrained(model_path)
        self.policy.to(self.device)
        self.policy.eval()
        if n_action_steps:
            # 1 回の推論で得た行動チャンクのうち、先頭から何ステップ分を続けて実行するか
            self.policy.config.n_action_steps = n_action_steps
        self.policy.reset()

        self.state = None
        self.last_rx = None
        self.create_subscription(Float32MultiArray, '/tank/state', self.on_state, 10)
        # 評価で車両をリセットするたびに、行動チャンクのキューを空にする
        self.create_subscription(Empty, '/tank/policy_reset', lambda _: self.policy.reset(), 10)
        self.pub = self.create_publisher(Float32MultiArray, '/tank/command', 10)
        self.create_timer(1.0 / PUBLISH_HZ, self.step)
        self.get_logger().info(f'方策を読み込みました: {model_path}')

    def on_state(self, msg):
        self.state = np.asarray(msg.data, dtype=np.float32)
        self.last_rx = self.get_clock().now()

    def step(self):
        if self.state is None:
            return
        if (self.get_clock().now() - self.last_rx).nanoseconds * 1e-9 > STATE_TIMEOUT:
            return
        s = self.torch.from_numpy(self.state).unsqueeze(0).to(self.device)   # (1, 5)
        obs = {'observation.state': s, 'observation.environment_state': s}
        with self.torch.no_grad():
            action = self.policy.select_action(obs).cpu().numpy().flatten()   # (3,)
        throttle = float(np.clip(action[0], -1.0, 1.0))
        steering = float(np.clip(action[1], -1.0, 1.0))
        turret = float(np.clip(action[2], -math.pi, math.pi))
        self.pub.publish(Float32MultiArray(data=[throttle, steering, turret]))
        self.get_logger().info(
            f'pitch={math.degrees(self.state[2]):+5.1f}deg x={self.state[0]:6.2f} '
            f'-> throttle={throttle:+.2f} steering={steering:+.2f} turret={math.degrees(turret):+5.1f}deg',
            throttle_duration_sec=0.5)


def main():
    ap = argparse.ArgumentParser(description='ACT 方策の推論ノード')
    ap.add_argument('--model-path', required=True, help='学習済みモデルのディレクトリ')
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--n-action-steps', type=int, default=8,
                    help='1 回の推論で得た行動チャンクを何ステップ続けて実行するか（0 なら学習時の設定のまま）。突堤では 8 が最良')
    args, ros_args = ap.parse_known_args()
    rclpy.init(args=ros_args)
    node = PolicyNode(args.model_path, args.device, args.n_action_steps)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # 止まるときは停止指令を送っておく
        node.pub.publish(Float32MultiArray(data=[0.0, 0.0, 0.0]))
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
