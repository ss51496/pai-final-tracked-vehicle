#!/bin/bash
# v2 の動画用の場面を自動で録画する（突堤 3 場面、壕 4 場面）。カメラは車両を追う。
#   v2_berm_full     全開のまま通過（跳ねる）
#   v2_berm_policy   学習した方策（ACT、突堤）
#   v2_ditch_front   砲塔が前向きのまま進入（砲身が壁に当たる）
#   v2_ditch_full    砲塔 90°・全開のまま通過（飛ぶ）
#   v2_ditch_human   人のデモ（記録した操作の再生）
#   v2_ditch_policy  学習した方策（ACT、壕。砲塔は最初から 90°）
# 動いているシミュレーションは停止する。出力: videos/<場面>.mp4（字幕つき）、_slow.mp4、_sheet.png（確認用のコマ）
set -e
cd "$(dirname "$0")/.."
export FOLLOW_X=${FOLLOW_X:--3} FOLLOW_Y=${FOLLOW_Y:--9} FOLLOW_Z=${FOLLOW_Z:-6}
source scripts/lib_record_v2.sh
BERM_MODEL=${BERM_MODEL:-/workspace/checkpoints/train/tank_v2_berm_act}
DITCH_MODEL=${DITCH_MODEL:-/workspace/checkpoints/train/tank_v2_ditch_t90_nocmd_act}
DEMO_EP=${DEMO_EP:-ep4}
sheet() { docker exec -u ubuntu -w /workspace pai_ros2 bash -lc "ffmpeg -y -loglevel error -i videos/$1.mp4 -vf 'fps=0.5,scale=480:-1,tile=4x3' -frames:v 1 videos/$1_sheet.png"; }
xlog_start() {   # $1=場面名。録画の開始（start_rec の直後）に呼ぶ。videos/<場面>.xlog に「経過秒 x」を書く
  docker exec -d -u ubuntu -w /workspace pai_ros2 bash -lc "source /opt/ros/humble/setup.bash && python3 scripts/xlog.py videos/$1.xlog 150"
}
xlog_stop() { docker exec pai_ros2 bash -c 'pkill -f "[x]log.py"' > /dev/null 2>&1 || true; }
policy_start() {   # $1=モデル $2=追加の引数
  docker exec -d -u ubuntu -w /workspace/pai_training -e DISPLAY=$D pai_ros2 bash -lc "export PATH=\$HOME/.pixi/bin:\$PATH; source /opt/ros/humble/setup.bash; source /workspace/ros2_ws/install/setup.bash; pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py --model-path $1 --n-action-steps 8 --rate 10 --wait-reset $2 > /workspace/logs/policy_video.log 2>&1"
  sleep 25
}
policy_stop() { docker exec pai_ros2 bash -c 'pkill -INT -f "[p]olicy_node.py"'; }

# ---- 突堤 ----（ONLY=ditch なら飛ばす）
if [ "${ONLY:-all}" != ditch ]; then
GUI_CFG=video_gui_v2_berm.config start_sim berm_v2
reset_v2 0
start_rec v2_berm_full; xlog_start v2_berm_full
X 'timeout 22 ros2 topic pub -r 20 /tank/command std_msgs/msg/Float32MultiArray "{data: [1.0, 0.0, 0.0]}" > /dev/null' || true
stop_vehicle; stop_rec; xlog_stop
finish v2_berm_full "全開のまま通過：山の頂上で車体が宙に浮く"; sheet v2_berm_full

policy_start $BERM_MODEL ""
reset_v2 0
start_rec v2_berm_policy; xlog_start v2_berm_policy
X 'ros2 topic pub -t 3 -r 2 /tank/policy_reset std_msgs/msg/Empty "{}" > /dev/null'
sleep 40
stop_rec; xlog_stop; policy_stop; stop_vehicle
finish v2_berm_policy "学習した方策（ACT）：山の手前で自ら減速して通過"; sheet v2_berm_policy

fi

# ---- 壕 ----（ONLY=berm なら飛ばす）
if [ "${ONLY:-all}" != berm ]; then
GUI_CFG=video_gui_v2_ditch.config start_sim ditch_v2
reset_v2 0
start_rec v2_ditch_front; xlog_start v2_ditch_front
X 'ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 0 --profile 0:1.0,70:0.15,115:1.0 --goal-x 128 --split-x 105.5 --timeout 90 --trials 1 --no-reset > /dev/null' || true
stop_vehicle; stop_rec; xlog_stop
finish v2_ditch_front "砲塔が前向きのまま進入：砲身が向こう側の壁に当たる"; sheet v2_ditch_front

reset_v2 90
start_rec v2_ditch_full; xlog_start v2_ditch_full
X 'ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 90 --entry-throttle 1.0 --goal-x 135 --split-x 105.5 --timeout 90 --trials 1 --no-reset > /dev/null' || true
stop_vehicle; stop_rec; xlog_stop
finish v2_ditch_full "砲塔90°・全開のまま通過：入るときも出るときも車体が宙に浮く"; sheet v2_ditch_full

reset_v2 90
start_rec v2_ditch_human; xlog_start v2_ditch_human
X "ros2 run tank_il evaluate_ditch --mode replay --only $DEMO_EP --bag-dir /workspace/dataset/rosbags/v2_ditch --goal-x 135 --split-x 105.5 --timeout 90 --trials 1 --no-reset > /dev/null" || true
stop_vehicle; stop_rec; xlog_stop
finish v2_ditch_human "人のテレオペ：壕の手前で減速し、縁でほぼ停止してから進入"; sheet v2_ditch_human

policy_start $DITCH_MODEL "--state-dims 0,1,2,3,5,6"
reset_v2 90
start_rec v2_ditch_policy; xlog_start v2_ditch_policy
X 'ros2 run tank_il evaluate_ditch --mode policy --goal-x 135 --split-x 105.5 --timeout 90 --trials 1 --no-reset > /dev/null' || true
stop_rec; xlog_stop; policy_stop; stop_vehicle
finish v2_ditch_policy "学習した方策（ACT）：壕の手前で自ら減速して通過"; sheet v2_ditch_policy

fi

scripts/kill_sim.sh > /dev/null
ls -la videos/v2_*.mp4
echo ALLDONE
