#!/bin/bash
# コンテナ内で ubuntu ユーザーとして ROS 2 環境つきでコマンドを実行する
# 使い方: scripts/dx.sh "ros2 topic list"
src="source /opt/ros/humble/setup.bash"
[ -f "$(dirname "$0")/../ros2_ws/install/setup.bash" ] && src="$src && source /workspace/ros2_ws/install/setup.bash"
docker exec -u ubuntu -w /workspace pai_ros2 bash -lc "$src && $*"
