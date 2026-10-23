# 動画撮影の共通関数（record_clips.sh と record_ditch_clips.sh から source する）
# 撮影専用の仮想ディスプレイ :99 に、3D ビューだけの Gazebo を表示して録画する。
D=:99
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
mkdir -p videos

X() { docker exec -u ubuntu -w /workspace -e DISPLAY=$D pai_ros2 bash -lc "source /opt/ros/humble/setup.bash && source /workspace/ros2_ws/install/setup.bash && $*"; }

# 撮影用ディスプレイとシミュレーションを起動する（$1=world、$2=GUI 設定のファイル名）。動いているシミュレーションは停止する
start_sim() {
  # 起動済みかは、実際に接続できるかで判定する（コンテナの再起動後は、古いソケットとロックだけが残るため）
  docker exec -d -u ubuntu pai_ros2 bash -lc "DISPLAY=$D xdpyinfo > /dev/null 2>&1 || { rm -f /tmp/.X11-unix/X${D#:} /tmp/.X${D#:}-lock; Xvnc $D -geometry 1280x768 -depth 24 -SecurityTypes None -rfbport 5999 > /workspace/logs/xvnc99.log 2>&1; }"
  sleep 3
  scripts/kill_sim.sh > /dev/null
  docker exec -d -u ubuntu -w /workspace -e DISPLAY=$D pai_ros2 bash -lc "source /opt/ros/humble/setup.bash && source /workspace/ros2_ws/install/setup.bash && ros2 launch tank_il tank_sim.launch.py world:=$1 video:=true gui_config:=${2:-video_gui.config} > /workspace/logs/video_sim.log 2>&1"
  sleep 25
}

# 3D ビューは 1280x768 のウィンドウの上端（ツールバー約 48 px）を除いた 1280x720
start_rec() {
  docker exec -d -u ubuntu -w /workspace -e DISPLAY=$D pai_ros2 bash -lc \
    "ffmpeg -y -loglevel error -f x11grab -draw_mouse 0 -framerate 30 -video_size 1280x720 -i $D+0,48 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p videos/$1_raw.mp4"
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
