#!/bin/bash
# エピソード間で車両を初期位置・初期姿勢に戻す（砲塔も 0° に戻す）
# 使い方: scripts/reset_tank.sh [x y z yaw_rad]    省略時は 0 0 0.35 0
# world 名は course、モデル名は tank（ign service -s /world/course/set_pose）。
# ホスト（WSL）からでも、コンテナ内からでも実行できる。
X=${1:-0}; Y=${2:-0}; Z=${3:-0.35}; YAW=${4:-0}
QW=$(python3 -c "import math; print(math.cos($YAW/2))")
QZ=$(python3 -c "import math; print(math.sin($YAW/2))")

# PAI_ISOLATED=1 のときは試験用の隔離環境（scripts/test_sim.sh で起動したもの）を対象にする
ENVSET=""
[ -n "$PAI_ISOLATED" ] && ENVSET="export ROS_DOMAIN_ID=77 IGN_PARTITION=pai_test; "
run() {
  if [ -f /.dockerenv ]; then
    bash -c "${ENVSET}source /opt/ros/humble/setup.bash && $1"
  else
    docker exec -u ubuntu pai_ros2 bash -lc "${ENVSET}source /opt/ros/humble/setup.bash && $1"
  fi
}

# 1) 駆動を止め、teleop の指令も 0 に戻し、砲塔を 0° に戻す指令を出す。
#    teleop の指令を戻さないと、teleop が配信し続ける古い砲塔角（例：90°）の指令が、
#    ここで出す 0° を上書きして、砲塔が戻らない。
#    リセット信号は 3 秒間送る（ros2 topic pub は起動直後のメッセージが受信側に届かないことがあるため）。
run "ros2 topic pub --times 5 --rate 20 /cmd_vel geometry_msgs/msg/Twist '{}' > /dev/null; \
     ros2 topic pub --times 15 --rate 5 /tank/teleop_reset std_msgs/msg/Empty '{}' > /dev/null; \
     ros2 topic pub --times 20 --rate 20 /tank/turret_cmd std_msgs/msg/Float64 '{data: 0.0}' > /dev/null"
# 2) 位置姿勢を戻す
run "ign service -s /world/course/set_pose --reqtype ignition.msgs.Pose --reptype ignition.msgs.Boolean \
     --timeout 3000 --req 'name: \"tank\", position: {x: $X, y: $Y, z: $Z}, orientation: {x: 0, y: 0, z: $QZ, w: $QW}'"
# 3) 砲塔が 0° に戻る（|角度| < 0.03 rad）まで待つ（最大 8 秒）。戻らなければ警告する
TURRET_OK=0
PARSE='import re,sys; t=sys.stdin.read(); v=re.findall(r"-?[0-9.]+(?:e-?[0-9]+)?", t.split("[",1)[1]) if "[" in t else []; print(v[4] if len(v)>=5 else "")'
for i in $(seq 1 16); do
  ang=$(run "timeout 3 ros2 topic echo --once /tank/state --field data 2>/dev/null" | python3 -c "$PARSE")
  if [ -n "$ang" ] && python3 -c "import sys; sys.exit(0 if abs(float('$ang')) < 0.03 else 1)"; then TURRET_OK=1; break; fi
  sleep 0.5
done
sleep 1.0
[ $TURRET_OK = 1 ] || echo "警告: 砲塔が 0° に戻りませんでした（/tank/state が来ていない可能性）" >&2
echo "reset: x=$X y=$Y z=$Z yaw=$YAW 砲塔=${ang:-不明} rad"
