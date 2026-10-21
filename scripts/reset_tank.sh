#!/bin/bash
# エピソード間で車両を初期位置・初期姿勢に戻す（砲塔も 0° に戻す）
# 使い方: scripts/reset_tank.sh [x y z yaw_rad]    省略時は 0 0 0.35 0
# world 名は course、モデル名は tank（ign service -s /world/course/set_pose）。
# ホスト（WSL）からでも、コンテナ内からでも実行できる。
X=${1:-0}; Y=${2:-0}; Z=${3:-0.35}; YAW=${4:-0}
QW=$(python3 -c "import math; print(math.cos($YAW/2))")
QZ=$(python3 -c "import math; print(math.sin($YAW/2))")

run() {
  if [ -f /.dockerenv ]; then
    bash -c "source /opt/ros/humble/setup.bash && $1"
  else
    docker exec -u ubuntu pai_ros2 bash -lc "source /opt/ros/humble/setup.bash && $1"
  fi
}

# 1) 駆動を止め、砲塔を 0° に戻す指令を出す
run "ros2 topic pub --times 5 --rate 20 /cmd_vel geometry_msgs/msg/Twist '{}' > /dev/null; \
     ros2 topic pub --once /tank/turret_cmd std_msgs/msg/Float64 '{data: 0.0}' > /dev/null"
# 2) 位置姿勢を戻す
run "ign service -s /world/course/set_pose --reqtype ignition.msgs.Pose --reptype ignition.msgs.Boolean \
     --timeout 3000 --req 'name: \"tank\", position: {x: $X, y: $Y, z: $Z}, orientation: {x: 0, y: 0, z: $QZ, w: $QW}'"
# 3) 車両が落ち着くのを待つ
sleep 1.5
echo "reset: x=$X y=$Y z=$Z yaw=$YAW"
