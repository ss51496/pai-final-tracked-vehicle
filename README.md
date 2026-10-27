# 重量装軌車両の不整地走行を模倣学習（ACT）で再現する

Ignition Gazebo 上に、**44 t 級の重量装軌車両**（多輪スキッドステアで履帯を模擬）を自作し、
操縦経験者のテレオペデモから **ACT** を学習して、**飛びを抑えつつ速度を保つ**操縦を自律的に行わせる。
建設機械・災害対応ロボット・惑星探査ローバーなど、不整地走行ロボットの自律化を想定している。
車両のパラメータ（質量・寸法・動力特性）はすべて架空の値で、実在の車両の情報は使っていない。

重い車両は、段差や溝の縁で宙に浮く（「飛ぶ」）と、着地の衝撃で故障する。かといって、ずっとゆっくり走るだけでは効率が悪い。
**通過の瞬間は速度を抑えて衝撃を和らげ、それ以外では速度を出す**技能を、10 回程度のデモから学習できるかを調べた。

- 車両：総質量 44 t、車体 7.4×2.6×1.0 m、片側 8 輪。最高 80 km/h、加速 1.5 m/s²、減速 3.5 m/s²（仮定の値）。
- 地形（助走 100 m）：**突堤**（高さ 1.5 m、斜面 20°）、**壕**（幅 11 m、深さ 2.2 m、壁 40°）。
- 観測は 8 次元（位置、ピッチ、速度、鉛直速度、ロール角、直前のスロットル指令など）。前方カメラの画像も試した。学習は GPU。
- 「飛び」は、真値の鉛直速度の 0.1 秒間の変化の最大値（**着地衝撃** [m/s]）で測り、**3.0 m/s 未満**を「飛ばずに通過」とする。

## 成果（各 10 試行）

**突堤**：ACT は、人のデモと同じ速さで、跳ねずに通過した。

| 方式 | 通過 | 跳ねずに通過 | 着地衝撃（平均） | 所要時間 |
|---|---|---|---|---|
| 一定スロットル 1.0（全開） | 10/10 | 0/10 | 4.46 m/s | 13.1 s |
| 一定スロットル 0.5 | 10/10 | 10/10 | 2.69 m/s | 15.1 s |
| 一定スロットル 0.25 | 10/10 | 10/10 | 1.48 m/s | 24.5 s |
| 一定スロットル 0.15 | 10/10 | 10/10 | 0.87 m/s | 38.8 s |
| **ACT（観測 8 次元）** | 10/10 | **10/10** | 2.32 m/s | **14.5 s** |
| **ACT（観測 7 次元）** | 10/10 | **10/10** | 2.42 m/s | **14.1 s** |

人のデモ（10 本）は 14.9 s。ただし、この突堤は一定の中速（0.5）でも通れる易しい課題で、ACT の優位は小さい。

**壕**：ACT は人より速く通過したが、入るときの減速が浅く、衝撃が基準をわずかに超えた（速度と飛びの両立は未達）。

| 方式 | 通過 | 飛ばずに通過 | 着地衝撃 入る／出る | 所要時間 |
|---|---|---|---|---|
| 人のデモ 10 本の再生 | 10/10 | 9/10 | 1.87／2.62 m/s | 21.5 s |
| 一定スロットル 0.15 | 10/10 | 10/10 | 1.61／1.80 m/s | 42.4 s |
| 全開のまま | 10/10 | 0/10 | 0.00／7.77 m/s | 13.9 s |
| ルール：x=70 m から 0.15、x=112 m から全開 | 10/10 | 10/10 | 1.60／1.84 m/s | 21.3 s |
| **ACT（数値のみ）** | 10/10 | 2/10 | 3.35／2.58 m/s | **17.5 s** |
| ACT（数値＋画像）1 回目 | 10/10 | 1/10 | 1.09／5.96 m/s | 13.7 s |
| ACT（数値＋画像）2 回目 | 10/10 | 3/10 | 1.17／5.55 m/s | 13.4 s |

全条件の記録は `results/`、図は `docs/`、作業の経緯・失敗と原因の分析は `WORKLOG.md`、レポートは `report/`。
シミュレーションはほぼ決定的で毎回同じ初期位置から始めるため、10 試行は独立ではない。人のデモの再生は、学習に使ったデモと同じ操作である（レポートの「限界」）。

## 構成

```
.
├── scripts/                 # コンテナ起動、リセット、デモの記録、評価、動画の撮影
├── ros2_ws/src/tank_il/     # 自作 ROS 2 パッケージ（ament_python）
│   ├── tools/               # モデル・地形の生成（gen_tank_model.py, gen_berm.py, gen_ditch.py）
│   ├── models/              # tank_v2（44 t 級）, tank_v2_cam（前方カメラつき）, berm_v2, ditch_v2（ほか、参照用の旧モデル）
│   ├── worlds/              # berm_v2.sdf, ditch_v2.sdf（と、_cam つき）, flat_v2.sdf（world 名はどれも course）
│   ├── config/              # bridge.yaml（トピック対応表）、撮影用の GUI 設定
│   ├── launch/              # tank_sim.launch.py
│   └── tank_il/             # teleop_tank, tank_driver, state_publisher, policy_node, hop_monitor,
│                            # impact_meter, evaluate_berm, evaluate_ditch
├── learning/                # 変換・学習・可視化（pai_training と組み合わせて使う）
├── results/                 # 評価結果（CSV と要約）
├── docs/  report/           # 図、最終レポート
└── WORKLOG.md               # 作業ログ（失敗・原因・設計判断・結果）
```

### トピック

| トピック | 型 | 内容 |
|---|---|---|
| `/tank/command` | Float32MultiArray | `[throttle, steering, …]`。throttle: -1〜1（後進〜全開）、steering: -1〜1（左〜右） |
| `/tank/state` | Float32MultiArray | `[x, z, pitch, v_forward, …, vz, roll, throttle_cmd]`（8 次元、`extended_state:=true`）。**学習の観測** |
| `/camera/image` | Image | 前方カメラ（160×120、10 Hz。`tank_v2_cam` のとき） |
| `/cmd_vel` | Twist | `tank_driver` が `/tank/command` から作る（v = throttle × `v_max`、ω = -steering × `omega_max`） |

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

**GPU で学習する場合**：GPU を渡すには、コンテナを作るときに `--gpus all` が要るので、学習用に別のコンテナを作る
（同じイメージ、同じ `/workspace`）。pixi は、`pai_ros2` の `/home/ubuntu/.pixi` をコピーして使う。
使う GPU は 1 枚にする（`CUDA_VISIBLE_DEVICES=0`。pai_training の PyTorch は、新しい世代の GPU に未対応のものがあるため）。

```bash
docker run -d --name pai_train --gpus all -v "$(pwd)":/workspace --entrypoint sleep \
  airobotbook/ros2-desktop-ai-robot-book-humble:latest infinity
docker cp pai_ros2:/home/ubuntu/.pixi /tmp/pixi_home && docker cp /tmp/pixi_home pai_train:/home/ubuntu/.pixi
docker exec -u root pai_train chown -R ubuntu:ubuntu /home/ubuntu/.pixi
```

以降、noVNC のターミナルは、最初に `source /opt/ros/humble/setup.bash` と `source /workspace/ros2_ws/install/setup.bash` を実行しておく。
動かなくなった Gazebo は、`/workspace/scripts/kill_sim.sh` で止められる。

## シミュレーションと操縦

```bash
# ターミナル 1：突堤（前方カメラつきの車両）。壕は world:=ditch_v2_cam
ros2 launch tank_il tank_sim.launch.py world:=berm_v2_cam v_max:=22.22 omega_max:=1.0 extended_state:=true camera_xyz:="105.0 -40.0 6.0"
# ターミナル 2：テレオペ
ros2 run tank_il teleop_tank
# ターミナル 3（任意）：通過のたびに、最高速度と着地衝撃（3.0 m/s 未満が目安）を表示する
ros2 run tank_il hop_monitor --ros-args -p goal_x:=125.0 -p split_x:=109.0 -p impact_thr:=3.0     # 壕は goal_x:=135.0 split_x:=105.5
```

| キー | 操作 |
|---|---|
| `W` / `S` | スロットルを 0.05 上げる / 下げる（約 4 km/h） |
| `R` / `F` | スロットルを 0.25 上げる / 下げる |
| `E` / `Space` | 全開 / 停止 |
| `D` / `A` | ハンドルを右 / 左に 0.25 切る |
| `X` | ハンドルを中立に戻す |
| `Q` | 終了 |

画面に、スロットル（km/h 換算）と実速度が出る。加速は 1.5 m/s²（全開まで約 15 秒）、減速は 3.5 m/s² なので、早めに操作する。
突堤は x=100 m から登る（通過の目安は x=125 m）。壕は x=100〜111 m（通過の目安は x=135 m）。

## データ収集

毎回同じ手順で操縦する（ACT は複数の軌道が混ざったデータが苦手）。ターミナルは 4 つ使う（シミュレーション、操縦、リセットと記録、飛びの表示）。
1 エピソードごとに、次の 2 つを実行して、操縦する。

```bash
TANK_Z=0.98 /workspace/scripts/reset_tank.sh        # 1. 車両を初期位置に戻す（位置、teleop の指令）
/workspace/scripts/record_demo.sh berm 0            # 2. 記録を開始（タスク berm か ditch、番号は 0, 1, 2 ...）。操縦して、通過したら Ctrl+C
```

`record_demo.sh` は、`/tank/state`・`/tank/command`・`/camera/image` を `--use-sim-time` で記録する。記録の前に `/tank/state` が配信されているかを確かめ、
止めたあとに 3 つのトピックの件数を表示する（足りなければ警告する）。記録先は `dataset/rosbags/v2_<タスク>/ep<番号>`。
**失敗したエピソードは、そのフォルダを削除して、同じ番号で撮り直す**。10〜20 エピソード集める。

**操作の目安**：突堤は、助走は全開、約 60〜90 m でスロットルを段階的に落とし、越えたら再加速する。
壕は、助走は全開、約 55〜90 m で段階的に 0.25 まで落とし、縁でほぼ停止してから進入し、出たら全開に戻す。
壕を跳ばずに通すには、約 12 km/h 以下に落とす必要がある（一定スロットルでの測定：0.15 で 1.6〜1.9 m/s、0.2 で 3.1〜3.7 m/s）。
**時間の基準が重要**：rosbag は `--use-sim-time` で記録し、推論の制御周期もシミュレーション時刻（10 Hz）で動かす。

## 変換・学習

```bash
# 学習用コンテナ（pai_train）で実行する
docker exec -u ubuntu -w /workspace pai_train bash learning/convert.sh v2_berm --overwrite     # rosbag → LeRobotDataset
docker exec -u ubuntu -w /workspace pai_train bash learning/train.sh v2_berm                   # ACT の学習（GPU、約 3 分）
docker exec -u ubuntu -w /workspace pai_train bash -c 'TANK_STATE_CMD=0 bash learning/convert.sh v2_ditch_t90 --overwrite'
docker exec -u ubuntu -w /workspace pai_train bash -c 'TANK_STATE_CMD=0 bash learning/train.sh v2_ditch_t90'
```

- 突堤は `v2_berm`、壕は `v2_ditch_t90`（観測から砲塔角を除いた 6 次元）。画像つきは `v2_ditch_t90_img`。
- `TANK_STATE_CMD=0` は、観測から throttle_cmd（直前のスロットル指令）を除く。行動の写しになる危険があるため、あり・なしを比べられる。
- 学習のステップ数は `TRAIN_STEPS=7000` のように変えられる。設定は `learning/` の `conversion_config_v2_*.yaml`、`train_config_v2_*.yaml`、`tank_features_v2.py`。
- 変換では、操縦の前後の停止区間を切り詰める（`trim_idle`）。

デモのグラフ（スロットル、速度、高さ、鉛直速度、ピッチ）と要約は、次で出せる（`pai_training` の pixi 環境）。

```bash
cd /workspace/pai_training
pixi run python /workspace/learning/plot_demos_v2.py --root /workspace/dataset/lerobot_dataset/tank_v2_ditch --out /workspace/docs/v2_ditch_demo2.png --span 100 111
```

## 推論と評価

```bash
cd /workspace/pai_training          # 方策（pixi の環境、teleop は止める。シミュレーションは上のターミナル 1）
pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py \
    --model-path /workspace/checkpoints/train/tank_v2_berm_act --n-action-steps 8 --rate 10                 # 突堤
pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py \
    --model-path /workspace/checkpoints/train/tank_v2_ditch_t90_nocmd_act --n-action-steps 8 --rate 10 \
    --state-dims 0,1,2,3,5,6                                                                               # 壕（観測から砲塔角を除く）
```

評価は、車両をリセットして走らせる 10 試行を記録する（結果は `results/*.csv`）。**操縦者の画面のシミュレーションと干渉しないよう、
試験は隔離環境（ROS ドメインと Gazebo パーティションを分けた環境）で、条件ごとにシミュレーションを起動し直して行う。**

```bash
scripts/eval_v2_berm.sh                            # 突堤：const1.0 const0.5 const0.25 const0.15（ルールベース）、cmd_n8 nocmd_n8（ACT）
scripts/eval_v2_ditch.sh                           # 壕：const015 full slowzone（ルールベース）、cmd_n8 nocmd_n8 など（ACT）
scripts/eval_v2_ditch.sh t90nocmd_n8               # 条件を指定して実行（最終の壕の方策）
# 人のデモの操作指令を、シミュレーション時刻に合わせて再生して、同じ指標で測る
ros2 run tank_il evaluate_ditch --mode replay --bag-dir /workspace/dataset/rosbags/v2_ditch --goal-x 135 --split-x 105.5 --impact-thr 3.0
```

指標：**着地衝撃**＝真値（`/odom_gt`）の鉛直速度の、0.1 秒間の変化の最大値（`tank_il/impact_meter.py`）。3.0 m/s 未満を「跳ねずに通過」とする
（落下の高さにして約 0.46 m 相当）。壕は、入るとき（x < 105.5 m）と出るときを分けて測り、どちらも 3.0 m/s 未満を「飛ばずに通過」とする。

## 動画の撮影

撮影専用の仮想ディスプレイ（:99）に、3D ビューだけの Gazebo を表示して録画する。実行すると、動いているシミュレーションは停止する。

```bash
./scripts/record_clips_v2.sh       # 突堤（全開、ACT）、壕（全開、人のデモ、ACT）の録画。障害物の側方に固定したカメラ
./scripts/cut_clips_v2.sh          # 車両が障害物の付近にいる区間だけに切り出し、字幕をつける
./scripts/make_final_video_v2.sh   # 説明カードと図を組み合わせて、1 本の動画（videos/final_v2_draft.mp4）にする
```

## 既知の限界

- 動力特性（最高速度・加速度）と、車両のパラメータは仮定の値。履帯は車輪で模擬し、サスペンションがないので、着地衝撃の絶対値は実機と一致しない。
- 突堤は、一定の中速でも通れる易しい課題で、ACT の優位は小さい。壕の「速度と飛びの両立」は未達（入るときの減速が人より浅い）。
- 前方カメラの画像を加えた学習は、10 本のデータでは不安定だった。
- 初期位置や地形の寸法を変えた汎化、突堤と壕を 1 本にまとめた通しの学習、本物の履帯（TrackedVehicle プラグイン）は未実施。
- リポジトリには、デモの rosbag、データセット、学習済みモデルを含めない（`.gitignore`）。再現するには、上の手順でデモを集めて学習する。

## 参考

- Qiita「gazeboとROS2を連携してロボットを操作する」（N622）：ROS 2 と Gazebo の連携の考え方を参考にした。コードとモデルは自作。
- [matsuolab/pai_training](https://github.com/matsuolab/pai_training)：rosbag から LeRobotDataset への変換と ACT の学習・推論の仕組みを参考にした。
- [LeRobot](https://github.com/huggingface/lerobot)、ACT（Zhao et al., 2023, https://arxiv.org/abs/2304.13705）

## ライセンス

MIT（`LICENSE`）。
