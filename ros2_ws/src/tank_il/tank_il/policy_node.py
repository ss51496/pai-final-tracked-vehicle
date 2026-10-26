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
from rclpy.parameter import Parameter
from std_msgs.msg import Empty, Float32MultiArray

PUBLISH_HZ = 10.0     # 学習データの fps と同じ
STATE_TIMEOUT = 1.0   # この秒数 /tank/state が来なければ配信を止める（tank_driver が停止する）


class PolicyNode(Node):
    def __init__(self, model_path, device, n_action_steps=None, wait_reset=False, rate=PUBLISH_HZ, sim_time=True, state_dims=None, use_image=False):
        # sim_time=True なら、制御周期とタイムアウトをシミュレーション時刻で測る（RTF の揺れの影響を受けない）
        overrides = [Parameter('use_sim_time', Parameter.Type.BOOL, True)] if sim_time else []
        super().__init__('policy_node', parameter_overrides=overrides)
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
        self.use_image = use_image   # True なら /camera/image も入力に加える（画像つきで学習したモデル）
        self.image = None
        self.state_dims = state_dims   # /tank/state のうちモデルに入れる添字（v2 で throttle_cmd を除くときなど）
        self.last_rx = None
        self.create_subscription(Float32MultiArray, '/tank/state', self.on_state, 10)
        if use_image:
            from sensor_msgs.msg import Image
            self.create_subscription(Image, '/camera/image', self.on_image, 2)
        # 評価で車両をリセットするたびに、行動チャンクのキューを空にする
        self.enabled = not wait_reset   # True なら /tank/policy_reset を受けるまで動かない（動画の撮影用）
        self.create_subscription(Empty, '/tank/policy_reset', self.on_reset, 10)
        # 評価でリセットを行っている間は、/tank/policy_hold で止めておく（/tank/policy_reset で再開する）。
        # 止めないと、車両が初期位置に戻った直後から走り出し、リセットの間に先へ進んでしまう
        self.create_subscription(Empty, '/tank/policy_hold', lambda _: setattr(self, 'enabled', False), 10)
        self.pub = self.create_publisher(Float32MultiArray, '/tank/command', 10)
        self.create_timer(1.0 / rate, self.step)
        self.get_logger().info(f'方策を読み込みました: {model_path}')

    def on_reset(self, _):
        self.policy.reset()
        self.enabled = True

    def on_image(self, msg):
        # rgb8（高さ×幅×3）→ (1, 3, 高さ, 幅)、0〜1 の float。学習データの画像（LeRobot が 0〜1 の CHW にする）と同じ形
        img = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(msg.height, msg.width, 3)
        self.image = self.torch.from_numpy(img.copy()).permute(2, 0, 1).unsqueeze(0).float().div(255.0)

    def on_state(self, msg):
        self.state = np.asarray(msg.data, dtype=np.float32)
        if self.state_dims is not None:
            self.state = self.state[self.state_dims]
        self.last_rx = self.get_clock().now()

    def step(self):
        if not self.enabled or self.state is None or (self.use_image and self.image is None):
            return
        if (self.get_clock().now() - self.last_rx).nanoseconds * 1e-9 > STATE_TIMEOUT:
            return
        s = self.torch.from_numpy(self.state).unsqueeze(0).to(self.device)   # (1, 状態の次元)
        obs = {'observation.state': s, 'observation.environment_state': s}
        if self.use_image:
            obs['observation.images.front'] = self.image.to(self.device)
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
    ap.add_argument('--rate', type=float, default=PUBLISH_HZ, help='制御周期 [Hz]。デモをシミュレーション時刻で記録したなら 10。突堤のデモは GUI 付き（RTF≈0.75）で実時間のタイムスタンプで記録したため、シミュレーション時刻では 10/0.75≈13.3 が合う')
    ap.add_argument('--wall-time', action='store_true', help='制御周期を実時間で測る（既定はシミュレーション時刻）')
    ap.add_argument('--wait-reset', action='store_true', help='/tank/policy_reset を受けるまで指令を出さない')
    ap.add_argument('--n-action-steps', type=int, default=8,
                    help='1 回の推論で得た行動チャンクを何ステップ続けて実行するか（0 なら学習時の設定のまま）。突堤では 8 が最良')
    ap.add_argument('--image', action='store_true', help='/camera/image も入力に加える（画像つきで学習したモデル）')
    ap.add_argument('--state-dims', default='', help="モデルに入れる /tank/state の添字（例 '0,1,2,3,4,5,6'）。省略時は全部")
    args, ros_args = ap.parse_known_args()
    rclpy.init(args=ros_args)
    node = PolicyNode(args.model_path, args.device, args.n_action_steps, args.wait_reset, args.rate, not args.wall_time,
                      [int(i) for i in args.state_dims.split(',')] if args.state_dims else None, args.image)
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
