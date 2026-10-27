#!/bin/bash
# v2 の動画の追加撮影：(1) 車両の全体像の静止画（videos/v2_vehicle.png）、(2) 壕の人のデモを、遠めのカメラで撮り直す。
set -e
cd "$(dirname "$0")/.."
export FOLLOW_X=0
source scripts/lib_record_v2.sh
# (1) 車両の全体像
GUI_CFG=video_gui_v2_view.config start_sim flat_v2
sleep 5
docker exec -u ubuntu -w /workspace -e DISPLAY=$D pai_ros2 bash -lc "ffmpeg -y -loglevel error -f x11grab -draw_mouse 0 -video_size 1280x720 -i $D+0,48 -frames:v 1 videos/v2_vehicle.png"
[ "$ONLY" = vehicle ] && { scripts/kill_sim.sh > /dev/null; echo ALLDONE; exit 0; }
# (2) 壕の人のデモ（遠めのカメラ）
DEMO_EP=${DEMO_EP:-ep4}
GUI_CFG=video_gui_v2_ditch_far.config start_sim ditch_v2
reset_v2 90
start_rec v2_ditch_human; docker exec -d -u ubuntu -w /workspace pai_ros2 bash -lc "source /opt/ros/humble/setup.bash && python3 scripts/xlog.py videos/v2_ditch_human.xlog 150"
X "ros2 run tank_il evaluate_ditch --mode replay --only $DEMO_EP --bag-dir /workspace/dataset/rosbags/v2_ditch --goal-x 135 --split-x 105.5 --timeout 90 --trials 1 --no-reset > /dev/null" || true
stop_vehicle; stop_rec; docker exec pai_ros2 bash -c 'pkill -f "[x]log.py"' > /dev/null 2>&1 || true
scripts/kill_sim.sh > /dev/null
echo ALLDONE
