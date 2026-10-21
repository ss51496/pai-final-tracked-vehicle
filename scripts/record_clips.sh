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
WORLD=${WORLD:-berm}
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
D=:99
mkdir -p videos

X() { docker exec -u ubuntu -w /workspace -e DISPLAY=$D pai_ros2 bash -lc "source /opt/ros/humble/setup.bash && source /workspace/ros2_ws/install/setup.bash && $*"; }

# ---- 撮影専用ディスプレイとシミュレーションの起動 ----
docker exec -d -u ubuntu pai_ros2 bash -lc "[ -e /tmp/.X11-unix/X${D#:} ] || Xvnc $D -geometry 1280x768 -depth 24 -SecurityTypes None -rfbport 5999 > /workspace/logs/xvnc99.log 2>&1"
scripts/kill_sim.sh > /dev/null
docker exec -d -u ubuntu -w /workspace -e DISPLAY=$D pai_ros2 bash -lc "source /opt/ros/humble/setup.bash && source /workspace/ros2_ws/install/setup.bash && ros2 launch tank_il tank_sim.launch.py world:=$WORLD video:=true > /workspace/logs/video_sim.log 2>&1"
sleep 25

# 3D ビューは 1280x768 のウィンドウの上端（ツールバー約 48 px）を除いた 1280x720
start_rec() {
  docker exec -d -u ubuntu -w /workspace -e DISPLAY=$D pai_ros2 bash -lc \
    "ffmpeg -y -loglevel error -f x11grab -framerate 30 -video_size 1280x720 -i $D+0,48 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p videos/$1_raw.mp4"
  sleep 1.5
}
stop_rec() {
  docker exec pai_ros2 bash -c 'pkill -INT -f "[f]fmpeg -y -loglevel error -f x11grab"'
  sleep 2
}
stop_vehicle() { X 'timeout 3 ros2 topic pub -r 20 /tank/command std_msgs/msg/Float32MultiArray "{data: [0.0, 0.0, 0.0]}" > /dev/null' || true; }

# 字幕をつけて通常版とスロー版を作る（$1=場面名 $2=字幕）。動き始めの 1 秒前〜動きが止まった 1.5 秒後に切り出す
finish() {
  docker exec -u ubuntu -w /workspace pai_ros2 bash -lc "
    ts=\$(ffmpeg -hide_banner -loglevel error -i videos/$1_raw.mp4 -vf 'scale=320:-1,select=gt(scene\,0.0003),metadata=print:file=-' -an -f null - 2>&1 | grep -o 'pts_time:[0-9.]*' | cut -d: -f2)
    t0=\$(echo \"\$ts\" | head -1); t1=\$(echo \"\$ts\" | tail -1)
    ss=\$(python3 -c \"print(max(0, \$t0 - 1.0))\"); to=\$(python3 -c \"print(\$t1 + 1.5)\")
    echo \"$1: 動き始め \$t0 s、動き終わり \$t1 s → 切り出し \$ss〜\$to s\"
    box=\"drawbox=y=ih-70:w=iw:h=70:color=black@0.55:t=fill\"
    ffmpeg -y -loglevel error -ss \$ss -to \$to -i videos/$1_raw.mp4 -vf \"\$box,drawtext=fontfile=$FONT:text='$2':fontcolor=white:fontsize=34:x=(w-text_w)/2:y=h-55\" -c:v libx264 -pix_fmt yuv420p -crf 20 videos/$1.mp4
    ffmpeg -y -loglevel error -ss \$ss -to \$to -i videos/$1_raw.mp4 -vf \"setpts=4.0*PTS,\$box,drawtext=fontfile=$FONT:text='$2（4倍スロー）':fontcolor=white:fontsize=34:x=(w-text_w)/2:y=h-55\" -r 30 -c:v libx264 -pix_fmt yuv420p -crf 20 videos/$1_slow.mp4"
}

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
