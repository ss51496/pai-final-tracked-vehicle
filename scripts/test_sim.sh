#!/bin/bash
# 試験用（GUI なし・隔離環境）のシミュレーションを起動する。ユーザーの GUI 上のシミュレーションには干渉しない
# 使い方: scripts/test_sim.sh [world]      止めるときは PAI_ISOLATED=1 scripts/kill_sim.sh
# プロセスグループ（setsid）にして PID を記録し、停止時にグループごと止める。
world=${1:-flat}
docker exec -d -u ubuntu -w /workspace pai_ros2 bash -lc "export ROS_DOMAIN_ID=77 IGN_PARTITION=pai_test; \
  source /opt/ros/humble/setup.bash && source /workspace/ros2_ws/install/setup.bash && \
  setsid bash -c 'echo \$\$ > /workspace/logs/test_sim.pgid; exec ros2 launch tank_il tank_sim.launch.py headless:=true world:=$world > /workspace/logs/test_sim.log 2>&1'"
sleep 15
echo "試験用シミュレーション起動: world=$world"
