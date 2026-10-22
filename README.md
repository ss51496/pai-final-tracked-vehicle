# 装軌車両の不整地走行を模倣学習（ACT）で再現する

Ignition Gazebo 上に、砲塔付きの**装軌車両**（多輪スキッドステアで履帯を模擬）を自作し、
操縦経験者のテレオペデモから **ACT** を学習して、**飛びを抑えつつ速度を保つ**操縦を自律的に行わせる。
建設機械・災害対応ロボット・惑星探査ローバーなど、不整地走行ロボットの自律化を想定している。
車両のパラメータはすべて架空の値で、実在の車両の情報は使っていない。

重い車両は、段差や溝の縁で宙に浮く（「飛ぶ」）と、着地の衝撃で故障する。かといって、ずっとゆっくり走るだけでは効率が悪い。
**通過の瞬間は速度を抑えて衝撃を和らげ、それ以外では速度を出す**技能を、10 回程度のデモから学習できるかを調べた。

| 地形 | 難しさ |
|---|---|
| **突堤**（台形の山） | 全開のまま頂上を越えると車体が跳ねる |
| **壕**（V 字の溝） | 入るときと出るときに飛ぶ。砲塔が前向きのまま進入すると、砲身が向こう側の壁に当たって動けなくなるので、走りながら砲塔を 90° 回す操作も必要 |

## 成果（各 10 試行）

**突堤**：学習した方策は、全開と同程度の速さで、跳ねずに通過した。

| 方式 | 通過 | 跳ねずに通過 | 所要時間（平均） |
|---|---|---|---|
| ルールベース：全開 | 10/10 | 0/10 | 3.8 s |
| ルールベース：0.5 一定 | 10/10 | 10/10 | 7.2 s |
| ルールベース：0.25 一定 | 10/10 | 10/10 | 13.7 s |
| ACT（`n_action_steps=1`） | 10/10 | 0/10 | 3.0 s |
| **ACT（`n_action_steps=8`）** | 10/10 | **10/10** | **3.1 s** |
| ACT（`n_action_steps=16`） | 10/10 | 7/10 | 4.1 s |

**壕**：方策は、砲塔を回す操作を含めて再現し、熟練者のデモと同程度の飛びで、約 26% 速く通過した。

| 方式 | 通過 | 接触せずに通過 | 空中：入る／出る／合計 | 所要時間 |
|---|---|---|---|---|
| 熟練者のデモ（操作指令を再生） | 10/10 | 10/10 | 0.35／0.48／0.83 s | 5.0 s |
| ルールベース：砲塔 90°・0.25 一定 | 10/10 | 10/10 | 0.22／0.04／0.26 s | 13.1 s |
| ルールベース：砲塔 90°・全開一定 | 10/10 | 10/10 | 0.52／0.48／1.00 s | 3.6 s |
| ルールベース：砲塔 0°（前向き）・0.5 一定 | 10/10 | **0/10** | 0.35／0.25／0.60 s | 6.8 s |
| ACT（`n_action_steps=8`） | 10/10 | 10/10 | 0.46／0.51／0.96 s | 3.3 s |
| **ACT（`n_action_steps=16`）** | 10/10 | 10/10 | **0.37／0.48／0.85 s** | **3.7 s** |

全条件の記録は `results/`、図は `docs/`、作業の経緯・失敗と原因の分析は `WORKLOG.md`、レポートは `report/`。
シミュレーションはほぼ決定的で毎回同じ初期位置から始めるため、10 試行は独立ではない（詳細はレポートの「限界」）。

## 構成

```
.
├── scripts/                 # コンテナ起動、リセット、評価、動画の撮影
├── ros2_ws/src/tank_il/     # 自作 ROS 2 パッケージ（ament_python）
│   ├── tools/               # モデル・地形の生成（gen_tank_model.py, gen_berm.py, gen_ditch.py）
│   ├── models/              # tank（突堤用）, tank_long（壕用）, berm, ditch
│   ├── worlds/              # flat.sdf, berm.sdf, ditch.sdf（world 名はどれも course）
│   ├── config/              # bridge.yaml（トピック対応表）、撮影用の GUI 設定
│   ├── launch/              # tank_sim.launch.py
│   └── tank_il/             # teleop_tank, tank_driver, state_publisher, policy_node,
│                            # hop_monitor, evaluate_berm, evaluate_ditch
├── learning/                # 変換・学習・可視化（pai_training と組み合わせて使う）
├── results/                 # 評価結果（CSV と要約）
├── docs/  report/           # 図、最終レポート
└── WORKLOG.md               # 作業ログ（失敗・原因・設計判断・結果）
```

### トピック

| トピック | 型 | 内容 |
|---|---|---|
| `/tank/command` | Float32MultiArray | `[throttle, steering, turret_angle]`。throttle: -1〜1（後進〜全開）、steering: -1〜1（左〜右）、turret_angle: 砲塔の目標角 [rad]（左回りが正）。**学習の行動** |
| `/tank/state` | Float32MultiArray | `[x, z, pitch, v_forward, turret_angle]`。pitch は機首上げ（登り）が正。**学習の観測** |
| `/cmd_vel` | Twist | `tank_driver` が `/tank/command` から作る（v = throttle × 4 m/s、ω = -steering × 1.5 rad/s） |

teleop と方策ノードはどちらも `/tank/command` に配信するので、差し替えるだけで動く（推論中は teleop を止めておく）。

## セットアップ

Windows + WSL2（Ubuntu）+ Docker Desktop。Docker Desktop の Settings → Resources → WSL integration で Ubuntu を有効にし、
WSL の Ubuntu 側にこのリポジトリを置く（コンテナの `/workspace` にマウントされる）。

```bash
git clone <このリポジトリ> ~/pai_final && cd ~/pai_final
./scripts/run_container.sh        # 2回目以降は docker start pai_ros2
```

`http://localhost:6080/`（noVNC）を開き、ターミナルでビルドする。

```bash
cd /workspace/ros2_ws && source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select tank_il
```

学習環境（講義の `matsuolab/pai_training`、pixi）は別に用意する。このリポジトリには含めない。依存パッケージの取得に 20〜30 分かかる。

```bash
docker exec -u ubuntu -w /workspace pai_ros2 bash learning/setup_training.sh
```

以降、noVNC のターミナルは、最初に `source /opt/ros/humble/setup.bash` と `source /workspace/ros2_ws/install/setup.bash` を実行しておく。
動かなくなった Gazebo は、`/workspace/scripts/kill_sim.sh` で止められる。

## シミュレーションと操縦

```bash
ros2 launch tank_il tank_sim.launch.py world:=berm      # または world:=ditch（Gazebo + bridge + tank_driver + state_publisher）
ros2 run tank_il teleop_tank                            # もう一方のターミナル
```

GUI のカメラは、起動後に横から見る位置に移動する（`side_view:=false` で無効）。

| キー | 操作 |
|---|---|
| `W` / `S` | スロットルを 0.25 上げる / 下げる |
| `E` / `Space` | 全開 / 停止 |
| `D` / `A` | ハンドルを右 / 左に 0.25 切る |
| `X` | ハンドルを中立に戻す |
| `L` / `J` | 砲塔を右 / 左に 5° 回す |
| `I` / `O` / `U` | 砲塔を 0° / 右 90° / 左 90° にする |
| `Q` | 終了 |

操縦中に「飛び」を確かめるには、別のターミナルで `ros2 run tank_il hop_monitor` を動かす。
壕を 1 回通過するたびに、入るとき・出るときの空中の時間（0.3 秒未満が目安）、所要時間、砲身の接触を表示する。

## データ収集

毎回同じ手順で操縦する（ACT は複数の軌道が混ざったデータが苦手）。ターミナルは 3〜4 つ使う（シミュレーション、操縦、リセットと記録、飛びの表示）。

1. 車両を初期位置に戻す。**車両の位置・teleop の指令・砲塔の角度（0° に戻るまで待つ）がすべて初期状態に戻る。**
   ```bash
   /workspace/scripts/reset_tank.sh
   ```
2. 記録を始める。**必ず `--use-sim-time` を付ける**（エピソード番号 N は毎回変える）。
   ```bash
   ros2 bag record --use-sim-time -o /workspace/dataset/rosbags/ditch/epN /tank/state /tank/command   # 突堤は .../berm/epN
   ```
3. **すぐに操縦を始める**。壕では、走りながら砲塔を 90° に回し（`O` / `U`）、壕に進入して通過する（ハンドルは切らない）。通過したら `Space` で止める。
4. `Ctrl+C` で記録を止める。**失敗したエピソードは、そのフォルダを削除して、同じ番号で撮り直す**（`rm -rf .../epN`）。
5. 10〜20 エピソード集める。

**時間の基準が重要**：rosbag を実時間で記録すると、シミュレーションの速さ（RTF）によって、データの時間の刻みが変わる。
推論時の制御周期（シミュレーション時刻）と合わなくなり、結果が不安定になる（WORKLOG 参照）。
この README の同梱結果のうち、突堤のデモだけは実時間で記録したため、推論の制御周期を 13.3 Hz にしている（`--rate 13.3`）。
新しく集めるデモは `--use-sim-time` で記録して、`--rate 10` で動かす。

**操作のコツ（壕）**：壕の外では速く走り、壕の縁（入るとき・出るとき）でアクセルを緩める。
ルールベースの探索では、縁の手前だけ 0.25 に落とし、ほかは全開にすると、飛びを 0.32 秒に抑えつつ 7.4 秒で通過できた（レポート 4.3 節）。

## 変換・学習

```bash
docker exec -u ubuntu -w /workspace pai_ros2 bash learning/convert.sh ditch --overwrite    # rosbag → LeRobotDataset（突堤は berm）
docker exec -u ubuntu -w /workspace pai_ros2 bash learning/train.sh ditch                  # ACT の学習（WANDB_MODE=offline、CPU で約 30 分）
```

設定は `learning/` の `conversion_config*.yaml`、`train_config*.yaml`、`tank_features*.py`。
変換では、操縦の前後の停止区間を切り詰める（`trim_idle`）。切り詰めないと、開始前の観測が毎回同じなのに動き出す時刻だけが違うため、方策が「止まったまま」と出力して動き出せない。

loss の推移と、学習データ上の予測と正解の比較は、次で図にできる（`pai_training` の pixi 環境で実行）。

```bash
cd /workspace/pai_training
pixi run python /workspace/learning/plot_loss.py /workspace/logs/train_ditch.log /workspace/docs/loss_ditch.png
pixi run python /workspace/learning/debug_policy_tank.py --dataset-root /workspace/dataset/lerobot_dataset/tank_ditch \
    --repo-id tank_ditch --policy-path /workspace/checkpoints/train/tank_ditch_act --episodes 0 4 9 --out /workspace/docs/debug_policy_ditch.png
pixi run python /workspace/learning/plot_demos.py --root /workspace/dataset/lerobot_dataset/tank_ditch --out /workspace/docs/ditch_demo2.png
```

## 推論と評価

```bash
ros2 launch tank_il tank_sim.launch.py world:=ditch                         # シミュレーション
cd /workspace/pai_training                                                  # 方策（pixi の環境、teleop は止める）
pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py \
    --model-path /workspace/checkpoints/train/tank_ditch_act --n-action-steps 16 --rate 10
```

`--n-action-steps`（1 回の推論で得た行動チャンクを何ステップ続けて実行するか）が結果を大きく左右する（1 では動けない／跳ねる。8〜16 が良い）。

評価は、車両をリセットして走らせる 10 試行を記録する（結果は CSV に保存）。**操縦者の画面のシミュレーションと干渉しないよう、
試験は隔離環境（ROS ドメインと Gazebo パーティションを分けた環境）で行う。**

```bash
scripts/eval_all_berm.sh /workspace/checkpoints/train/tank_berm_act n8      # 突堤（const1.0 const0.5 const0.25 n1 n8 n16）
scripts/eval_ditch.sh baseline                                              # 壕のルールベース
scripts/eval_ditch.sh policy 8 16                                           # 壕の方策
# 熟練者のデモの操作指令を、シミュレーション時刻に合わせて再生して、同じ指標で測る
ros2 run tank_il evaluate_ditch --mode replay --bag-dir /workspace/dataset/rosbags/ditch
```

指標：突堤の「跳ねずに通過」＝通過かつ最高 z < 1.70 m かつ空中 < 0.6 s（IMU の加速度の大きさが 3 m/s² 未満の時間）。
壕の「接触せずに通過」＝通過かつ砲身の接触センサーが 0 件。空中の時間（入る／出る）と所要時間も併記する（熟練者のデモを基準に比較する）。

## 動画の撮影

撮影専用の仮想ディスプレイ（:99）に、3D ビューだけの Gazebo を表示して録画するので、画面に他のウィンドウが重なっても影響しない。
実行すると、動いているシミュレーションは停止する。

```bash
./scripts/record_clips.sh          # 突堤：全開／熟練者のデモ／方策     → videos/<場面>.mp4（字幕つき）と _slow.mp4（4 倍スロー）
./scripts/record_ditch_clips.sh    # 壕：砲塔前向き／90°／全開／熟練者のデモ／方策
./scripts/make_final_video.sh      # 説明カードと組み合わせて、1 本の動画（videos/final_draft.mp4）にする
```

動き始めの 1 秒前〜動きが止まった 1.5 秒後に、自動で切り出す。

## 壕の設計

壕は、上端の幅 4.8 m、深さ 1.0 m、壁 40°。全開（4 m/s）でも飛び越えられず、底まで落ちる広さにした。
幅を広げると、前向きでも砲身が壁に当たらなくなるので、砲身を 2.0 m（車体の長さと同じ）にして、前向きなら速度にかかわらず壁に当たるようにした。
砲身の長さは突堤の方策の結果を変える（砲塔の重さと重心が変わる）ため、**突堤用の車両 `models/tank`（砲身 1.3 m）と、壕用の車両 `models/tank_long`（砲身 2.0 m、接触センサー付き）を分けている**（モデル名はどちらも `tank`）。

寸法は `tools/gen_ditch.py`（環境変数 `DITCH_TOP_W`、`DITCH_DEPTH`、`DITCH_SLOPE`）、砲身の長さは `tools/gen_tank_model.py`（`BARREL_LEN`）で変える。
`scripts/scan_ditch.sh` で、寸法を変えながら接触と通過を調べられる。

## 既知の限界

- 車輪の駆動力に上限がなく、壁（40°）を速度にかかわらず登れてしまうため、「落ちて壁に激突して動けなくなる」は再現できていない。
- 突堤と壕を 1 本のコースにまとめた通しの学習、本物の履帯（TrackedVehicle プラグイン）、カメラ入力は未実施。
- リポジトリには、デモの rosbag、データセット、学習済みモデルを含めない（`.gitignore`）。再現するには、上の手順でデモを集めて学習する。

## 参考

- Qiita「gazeboとROS2を連携してロボットを操作する」（N622）：ROS 2 と Gazebo の連携の考え方を参考にした。コードとモデルは自作。
- [matsuolab/pai_training](https://github.com/matsuolab/pai_training)：rosbag から LeRobotDataset への変換と ACT の学習・推論の仕組みを参考にした。
- [LeRobot](https://github.com/huggingface/lerobot)、ACT（Zhao et al., 2023, https://arxiv.org/abs/2304.13705）

## ライセンス

MIT（`LICENSE`）。
