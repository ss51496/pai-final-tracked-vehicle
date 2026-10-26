# v2（44 t 級の車両）の動画撮影の共通関数。lib_record.sh を読み込み、v2 用に起動方法を差し替える。
# 撮影専用の仮想ディスプレイ :99 に、3D ビューだけの Gazebo を表示して録画する。カメラは車両を追う（follow）。
source "$(dirname "${BASH_SOURCE[0]}")/lib_record.sh"

# $1=world（berm_v2_cam など）。車両の側方・やや後ろから追うカメラにする
start_sim() {
  docker exec -d -u ubuntu pai_ros2 bash -lc "DISPLAY=$D xdpyinfo > /dev/null 2>&1 || { rm -f /tmp/.X11-unix/X${D#:} /tmp/.X${D#:}-lock; Xvnc $D -geometry 1280x768 -depth 24 -SecurityTypes None -rfbport 5999 > /workspace/logs/xvnc99.log 2>&1; }"
  sleep 3
  scripts/kill_sim.sh > /dev/null
  docker exec -d -u ubuntu -w /workspace -e DISPLAY=$D pai_ros2 bash -lc "source /opt/ros/humble/setup.bash && source /workspace/ros2_ws/install/setup.bash && ros2 launch tank_il tank_sim.launch.py world:=$1 video:=true gui_config:=${GUI_CFG:-video_gui.config} v_max:=22.22 omega_max:=1.0 extended_state:=true > /workspace/logs/video_sim.log 2>&1"
  sleep 45
  [ -n "$GUI_CFG" ] && return 0   # GUI 設定でカメラを固定した場合は、車両を追わない
  # 車両を追うカメラ（オフセットはワールド座標。車両の -y 側 16 m、後ろ 10 m、上 5 m）
  X "ign service -s /gui/follow --reqtype ignition.msgs.StringMsg --reptype ignition.msgs.Boolean --timeout 3000 --req 'data: \"tank\"' > /dev/null; \
     ign service -s /gui/follow/offset --reqtype ignition.msgs.Vector3d --reptype ignition.msgs.Boolean --timeout 3000 --req 'x: ${FOLLOW_X:--10}, y: ${FOLLOW_Y:--16}, z: ${FOLLOW_Z:-5}' > /dev/null" || true
  sleep 2
}

# 車両をリセットする（$1=砲塔の初期角度 [deg]、既定 0）
reset_v2() { TANK_Z=0.98 TURRET_DEG=${1:-0} scripts/reset_tank.sh > /dev/null; }
