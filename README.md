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
   # （突堤のデモは GUI 付きで実時間のタイムスタンプで記録した。以後は --use-sim-time を付けること）
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
変換では、操縦を始める前と終えた後の停止区間を切り詰める（`trim_idle`）。切り詰めないと、開始前の観測が毎回同じで動き出す時刻だけが違うため、方策が「止まったまま」と出力して動き出せない。

学習の loss の推移と、学習データ上の予測と正解の比較（`debug-policy` 相当）は、次の図にできる。

```bash
cd /workspace/pai_training
pixi run python /workspace/learning/plot_loss.py /workspace/logs/train_berm.log /workspace/docs/loss_berm.png
pixi run python /workspace/learning/debug_policy_tank.py --episodes 0 5 9 --out /workspace/docs/debug_policy_berm.png
```

## 推論と評価

推論中は teleop を必ず止める（同じ `/tank/command` に配信して競合するため）。

```bash
ros2 launch tank_il tank_sim.launch.py world:=berm        # シミュレーション
cd /workspace/pai_training                                # 方策（pixi の環境）
pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py     --model-path /workspace/checkpoints/train/tank_berm_act --n-action-steps 8 --rate 13.3
```

評価は 10 試行（車両のリセット → 走行 → x ≥ 13 m まで）を記録する。
「跳ねずに通過」は、通過かつ最高 z < 1.70 m かつ空中 < 0.6 s（IMU の加速度の大きさが 3 m/s² 未満の時間）。

```bash
ros2 run tank_il evaluate_berm --mode const --throttle 1.0 --trials 10   # ルールベース（一定スロットル）
ros2 run tank_il evaluate_berm --mode policy --trials 10                 # 方策（policy_node を起動しておく）
```

## 動画の撮影

3 つの場面（全開のまま通過／熟練者のデモの再現／方策の自律走行）を自動で録画する。
撮影専用の仮想ディスプレイ（:99）に、3D ビューだけの Gazebo を表示して録画するので、画面に他のウィンドウが重なっても影響しない。
実行すると、動いているシミュレーションは停止する。

```bash
./scripts/record_clips.sh      # videos/<場面>.mp4（字幕つき）と videos/<場面>_slow.mp4（4 倍スロー）ができる
```

動き始めの 1 秒前〜動きが止まった 1.5 秒後に自動で切り出す。録画のシミュレーションは
`ros2 launch tank_il tank_sim.launch.py world:=berm video:=true`（撮影用の GUI 設定 `config/video_gui.config`）。

## 壕（段階3）

壕（上端の幅 4.8 m、深さ 1.0 m、壁 40°、底はほぼ平ら）の world は `worlds/ditch.sdf`。
全開（4 m/s）でも飛び越えられず、底まで落ちる広さにしてある。
壕では、砲身を 2.0 m（車体の長さと同じ）にした車両 `models/tank_long` を使う（モデル名は `tank` のまま）。
**砲塔が前向きだと、砲身が向こう側の壁に当たる**（速度にかかわらず）。砲塔を 90° 回すと、砲身は壕に沿って横を向くので、壁に当たらない。
壁との接触は、砲身と車体の接触センサーで検出する。突堤の車両 `models/tank`（砲身 1.3 m、センサーなし）とは別のモデルにしてある
（砲身の長さが突堤の方策の結果を変えるため）。

```bash
ros2 launch tank_il tank_sim.launch.py world:=ditch
# ルールベースの手順で試す（砲塔 90° → 0.25 で進入 → x=8.7 m から全開）
ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 90 --entry-throttle 0.25 --switch-x 8.7 --trials 3
./scripts/record_ditch_clips.sh    # 比較映像（前向きでつかえる／90° 回して通過）
```

壕の寸法は `tools/gen_ditch.py`（環境変数 `DITCH_TOP_W`、`DITCH_DEPTH`、`DITCH_SLOPE`）、砲身の長さは `tools/gen_tank_model.py`（`BARREL_LEN`）で変える。
`scripts/scan_ditch.sh` で寸法を変えながら、接触と通過を調べられる。

### 壕のデモ収集

**重要なのは、壕に入るときと出るときの「飛び」を抑えつつ、速度も保つこと**。ゆっくり走るだけでは不十分で、
重い車両が宙に浮くと衝撃で故障するため、通過のときは速度を抑えて衝撃を和らげ、それ以外では速度を出す。
壕の外では速く走り、壕の縁（入るとき・出るとき）ではアクセルを緩める操作を、毎回そろえて行う。

**rosbag はシミュレーション時刻で記録する**（`--use-sim-time`）。実時間で記録すると、シミュレーションの速さ（RTF）によってデータの時間の刻みが変わり、
推論時の制御周期と合わなくなる（突堤で経験した問題。WORKLOG 参照）。

noVNC のターミナルを 4 つ使う（それぞれ最初に `source /opt/ros/humble/setup.bash` と `source /workspace/ros2_ws/install/setup.bash`）。

1. シミュレーション：`ros2 launch tank_il tank_sim.launch.py world:=ditch`
2. 操縦：`ros2 run tank_il teleop_tank`
3. 飛びの表示（任意）：`ros2 run tank_il hop_monitor` — 壕を 1 回通過するたびに、入るとき・出るときの空中の時間（0.3 秒未満が目安）、所要時間、砲身の接触を表示する。操作の調整の目安にする。
4. リセットと記録（エピソードごとに N を 0, 1, 2… と変える）：
   ```bash
   /workspace/scripts/reset_tank.sh
   ros2 bag record --use-sim-time -o /workspace/dataset/rosbags/ditch/epN /tank/state /tank/command
   ```

1 エピソードの流れ：`reset_tank.sh` → teleop で `Space`・`X`・`I` を押して初期状態に → `ros2 bag record` を開始 →
砲塔を 90° に回し（`O`）、壕に進入して通過（ハンドルは切らない）→ 通過したら `Space` で止めて、記録を `Ctrl+C` で止める。
10〜20 エピソード集める。

変換・学習・評価：

```bash
docker exec -u ubuntu -w /workspace pai_ros2 bash learning/convert.sh ditch --overwrite   # rosbag → LeRobotDataset
docker exec -u ubuntu -w /workspace pai_ros2 bash learning/train.sh ditch                 # ACT の学習
```

## 結果（突堤、各 10 試行）

| 方式 | 通過 | 跳ねずに通過 | 所要時間（平均） |
|---|---|---|---|
| ルールベース：全開 | 10/10 | 0/10 | 3.8 s |
| ルールベース：0.5 一定 | 10/10 | 10/10 | 7.2 s |
| ルールベース：0.25 一定 | 10/10 | 10/10 | 13.7 s |
| ACT（`n_action_steps=1`） | 10/10 | 0/10 | 3.0 s |
| **ACT（`n_action_steps=8`）** | 10/10 | **10/10** | **3.1 s** |
| ACT（`n_action_steps=16`） | 10/10 | 7/10 | 4.1 s |

全開と同じ程度の速さで、跳ねずに通過できた。方策の制御周期はシミュレーション時刻で 13.3 Hz（突堤のデモは RTF≈0.75 の GUI で、実時間のタイムスタンプで記録したため。WORKLOG 参照）。詳細と考察は `WORKLOG.md`、図は `docs/`、全記録は `results/`。

## 参考

- Qiita「gazeboとROS2を連携してロボットを操作する」（N622）：ROS 2 と Gazebo の連携の考え方を参考にした。コードとモデルは自作。
- [matsuolab/pai_training](https://github.com/matsuolab/pai_training)：rosbag から LeRobotDataset への変換と ACT の学習・推論の仕組みを参考にした。
- [LeRobot](https://github.com/huggingface/lerobot)、ACT（Zhao et al., 2023, https://arxiv.org/abs/2304.13705）
