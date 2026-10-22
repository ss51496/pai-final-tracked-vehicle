#!/bin/bash
# 壕の比較映像を自動で録画する（砲塔が前向きだと砲身が壁に当たる／90° 回すと当たらない）。
#   ditch_front   砲塔 0°（前向き）で進入 → 砲身が向こう側の壁に当たって動けなくなる
#   ditch_turn90  砲塔 90° に回してから進入、出口の手前で全開 → 接触せずに通過
#   ditch_full    砲塔 90°・全開のまま通過（飛ぶ）
#   ditch_human   熟練者のデモの再現（記録した操作の再生）
#   ditch_policy  学習した方策（ACT）の自律走行
# 動いているシミュレーションは停止する。出力: videos/<場面>.mp4（字幕つき）と _slow.mp4
set -e
cd "$(dirname "$0")/.."
source scripts/lib_record.sh
start_sim ditch video_gui_ditch.config

scripts/reset_tank.sh > /dev/null
start_rec ditch_front
X 'ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 0 --entry-throttle 0.25 --trials 1 --no-reset > /dev/null' || true
stop_vehicle; stop_rec
finish ditch_front "砲塔が前向きのまま進入：砲身が向こう側の壁に当たって動けない"

scripts/reset_tank.sh > /dev/null
start_rec ditch_turn90
X 'ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 90 --entry-throttle 0.25 --switch-x 8.7 --trials 1 --no-reset > /dev/null' || true
stop_vehicle; stop_rec
finish ditch_turn90 "砲塔を90°回してから進入：砲身が壁に当たらずに通過"

# ---- 場面 3: 全開で通過（飛び越える／飛び出す。接触はしないが、車体が宙に浮く）----
scripts/reset_tank.sh > /dev/null
start_rec ditch_full
X 'ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 90 --entry-throttle 1.0 --trials 1 --no-reset > /dev/null' || true
stop_vehicle; stop_rec
finish ditch_full "砲塔90°・全開のまま通過：入るときも出るときも車体が宙に浮く"

# ---- 場面 4: 熟練者のデモの再現（記録した操作指令をシミュレーション時刻に合わせて再生）----
DEMO_EP=${DEMO_EP:-ep4}
scripts/reset_tank.sh > /dev/null
start_rec ditch_human
X "ros2 run tank_il evaluate_ditch --mode replay --only $DEMO_EP --trials 1 --no-reset > /dev/null" || true
stop_vehicle; stop_rec
finish ditch_human "熟練者のテレオペ：走りながら砲塔を90°に回し、壕の縁で速度を落とす"

# ---- 場面 5: 学習した方策 ----
MODEL=${MODEL:-/workspace/checkpoints/train/tank_ditch_act}
docker exec -d -u ubuntu -w /workspace/pai_training -e DISPLAY=$D pai_ros2 bash -lc   "export PATH=\$HOME/.pixi/bin:\$PATH; source /opt/ros/humble/setup.bash; source /workspace/ros2_ws/install/setup.bash; pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py --model-path $MODEL --n-action-steps 16 --rate 10 --wait-reset > /workspace/logs/policy_video.log 2>&1"
sleep 25
scripts/reset_tank.sh > /dev/null
start_rec ditch_policy
X 'ros2 run tank_il evaluate_ditch --mode policy --trials 1 --no-reset > /dev/null' || true
stop_rec
docker exec pai_ros2 bash -c 'pkill -INT -f "[p]olicy_node.py"'
stop_vehicle
finish ditch_policy "学習した方策（ACT）：砲塔を自ら90°に回し、壕の縁で減速して通過"

scripts/kill_sim.sh > /dev/null
ls -la videos/ditch_*.mp4
