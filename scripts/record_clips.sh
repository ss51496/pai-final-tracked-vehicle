#!/bin/bash
# 動画用の 3 つの場面を自動で録画する（シミュレーションの起動から字幕つけまで）。
#   rule_full  ルールベース：全開のまま通過（跳ねる）
#   human_demo 熟練者のデモの再現（rosbag の /tank/command を再生する）
#   policy     学習した方策（ACT）の自律走行
# 撮影専用の仮想ディスプレイ :99 に撮影用の Gazebo（3D ビューだけ）を表示して録画するので、
# 画面に他のウィンドウが重なっても影響しない。実行すると、動いているシミュレーションは停止する。
# 出力: videos/<場面>.mp4（字幕つき）、videos/<場面>_slow.mp4（4 倍のスローモーション）
#   scripts/record_clips.sh              使う rosbag は DEMO_EP（既定 ep3）、モデルは MODEL で変更できる
set -e
cd "$(dirname "$0")/.."
MODEL=${MODEL:-/workspace/checkpoints/train/tank_berm_act}
DEMO_EP=${DEMO_EP:-ep3}
source scripts/lib_record.sh
start_sim berm video_gui.config

# ---- 場面 1: 全開のまま通過 ----
scripts/reset_tank.sh > /dev/null
start_rec rule_full
X 'timeout 7 ros2 topic pub -r 20 /tank/command std_msgs/msg/Float32MultiArray "{data: [1.0, 0.0, 0.0]}" > /dev/null' || true
stop_vehicle; stop_rec
finish rule_full "ルールベース：スロットル全開のまま通過（車体が跳ねる）"

# ---- 場面 2: 熟練者のデモの再現 ----
scripts/reset_tank.sh > /dev/null
start_rec human_demo
X "ros2 bag play dataset/rosbags/berm/$DEMO_EP --topics /tank/command > /dev/null"
stop_vehicle; stop_rec
finish human_demo "熟練者のテレオペ（登りは一定速度、頂上で減速）"

# ---- 場面 3: 学習した方策 ----
docker exec -d -u ubuntu -w /workspace/pai_training -e DISPLAY=$D pai_ros2 bash -lc \
  "export PATH=\$HOME/.pixi/bin:\$PATH; source /opt/ros/humble/setup.bash; source /workspace/ros2_ws/install/setup.bash; pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py --model-path $MODEL --wait-reset > /workspace/logs/policy_video.log 2>&1"
sleep 25
scripts/reset_tank.sh > /dev/null
start_rec policy
X 'ros2 topic pub -t 3 -r 2 /tank/policy_reset std_msgs/msg/Empty "{}" > /dev/null'
sleep 9
stop_rec
docker exec pai_ros2 bash -c 'pkill -INT -f "[p]olicy_node.py"'
stop_vehicle
finish policy "学習した方策（ACT）による自律走行：頂上の手前で自ら減速して通過"

scripts/kill_sim.sh > /dev/null
ls -la videos/*.mp4
