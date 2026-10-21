# 装軌車両の不整地走行を模倣学習（ACT）で再現する

Ignition Gazebo 上に、砲塔付きの装軌車両（多輪スキッドステアで履帯を模擬）を自作し、
熟練操縦者のテレオペデモから ACT を学習して、地形に応じた速度の切り替えを自律的に行わせる。
建設機械・災害対応ロボット・惑星探査ローバーなど、不整地走行ロボットの自律化を想定している。

車両のパラメータはすべて架空の値で、実在の車両の情報は使っていない。

## タスク

| 段階 | 内容 |
|---|---|
| 突堤（berm） | 台形の山を、登りは全開、頂上で減速して越える。全開のまま越えると車体が跳ねる |
| 壕（ditch）※予定 | 砲塔を前に向けたまま進入すると砲身が壁に当たる。90° 回して進入する |

## 構成

```
.
├── scripts/                 # コンテナ起動、リセット、試験用スクリプト
├── ros2_ws/src/tank_il/     # 自作 ROS 2 パッケージ（ament_python）
│   ├── tools/               # モデル・地形の生成スクリプト（gen_tank_model.py, gen_berm.py）
│   ├── models/              # tank（車両）, berm（突堤）
│   ├── worlds/              # flat.sdf, berm.sdf（world 名はどれも course）
│   ├── config/bridge.yaml   # ROS ⇔ Gazebo のトピック対応表
│   ├── launch/              # tank_sim.launch.py
│   └── tank_il/             # teleop_tank, tank_driver, state_publisher
└── learning/                # 変換スクリプトと学習設定
```

### トピック

| トピック | 型 | 内容 |
|---|---|---|
| `/tank/command` | Float32MultiArray | `[throttle, steering, turret_angle]`。throttle: -1〜1（後進〜全開）、steering: -1〜1（左〜右）、turret_angle: 砲塔の目標角 [rad]（左回りが正）。**学習の行動** |
| `/tank/state` | Float32MultiArray | `[x, z, pitch, v_forward, turret_angle]`。pitch は機首上げ（登り）が正。**学習の観測** |
| `/cmd_vel` | Twist | `tank_driver` が `/tank/command` から作る（v = throttle × 4 m/s、ω = -steering × 1.5 rad/s） |

teleop と方策ノードはどちらも `/tank/command` に配信するので、差し替えるだけで動く。

## セットアップ

Windows + WSL2（Ubuntu）+ Docker Desktop で、WSL の Ubuntu 側にこのリポジトリを置く。
Docker Desktop の Settings → Resources → WSL integration で、Ubuntu を有効にしておく。

```bash
git clone <このリポジトリ> ~/pai_final && cd ~/pai_final
./scripts/run_container.sh        # 2回目以降は docker start pai_ros2
```

`http://localhost:6080/`（noVNC）を開き、ターミナルでビルドする。

```bash
cd /workspace/ros2_ws && source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select tank_il
```

学習環境（講義の `matsuolab/pai_training`、pixi）は別に用意する。このリポジトリには含めない。

```bash
docker exec -u ubuntu -w /workspace pai_ros2 bash learning/setup_training.sh
```

## シミュレーションと操縦

noVNC 上のターミナルを2つ開く（それぞれ最初に `source /opt/ros/humble/setup.bash` と
`source /workspace/ros2_ws/install/setup.bash`）。

```bash
ros2 launch tank_il tank_sim.launch.py world:=berm    # Gazebo + bridge + tank_driver + state_publisher
ros2 run tank_il teleop_tank                          # もう一方のターミナル
```

GUI のカメラは起動後に横から見る位置に移動する（`side_view:=false` で無効）。

| キー | 操作 |
|---|---|
| `W` / `S` | スロットルを 0.25 上げる / 下げる |
| `E` / `Space` | 全開 / 停止 |
| `D` / `A` | ハンドルを右 / 左に 0.25 切る |
| `X` | ハンドルを中立に戻す |
| `L` / `J` | 砲塔を右 / 左に 5° 回す |
| `I` / `O` / `U` | 砲塔を 0° / 右 90° / 左 90° にする |
| `Q` | 終了 |

## データ収集（突堤）

毎回同じ手順で操縦する。ACT は複数の軌道が混ざったデータが苦手なので、操作をそろえる。

1. 車両を初期位置に戻す（別のターミナルで）。teleop は `Space`・`X`・`I` で初期状態に戻す。
   ```bash
   /workspace/scripts/reset_tank.sh
   ```
2. 記録を始める（エピソード番号 N を毎回変える）。
   ```bash
   ros2 bag record -o /workspace/dataset/rosbags/berm/epN /tank/state /tank/command
   ```
3. **すぐに操縦を始める**。登りは全開（`E`）、頂上の手前で減速して越え、下りは低速で進む。通過したら `Space` で止める。
4. 通過したらすぐ `Ctrl+C` で記録を止める。途中の無駄な停止は「止まる」ことを学習してしまう。
5. 10〜20 エピソード集める。

## 変換・学習

```bash
cd /workspace/pai_training
pixi run python /workspace/learning/rosbag2lerobot_tank.py --config /workspace/learning/conversion_config.yaml
WANDB_MODE=offline pixi run train
```

設定は `learning/conversion_config.yaml`、`learning/train_config.yaml`、`learning/tank_features.py`。

## 参考

- Qiita「gazeboとROS2を連携してロボットを操作する」（N622）：ROS 2 と Gazebo の連携の考え方を参考にした。コードとモデルは自作。
- [matsuolab/pai_training](https://github.com/matsuolab/pai_training)：rosbag から LeRobotDataset への変換と ACT の学習・推論の仕組みを参考にした。
- [LeRobot](https://github.com/huggingface/lerobot)、ACT（Zhao et al., 2023, https://arxiv.org/abs/2304.13705）
