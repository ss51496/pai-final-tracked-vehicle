#!/bin/bash
# コンテナ内で ubuntu ユーザーとして ROS 2 環境つきでコマンドを実行する
# 使い方: scripts/dx.sh "ros2 topic list"
# PAI_ISOLATED=1 を付けると、ROS ドメインと Gazebo パーティションを分けた試験用の環境で実行する
# （noVNC 上でユーザーが動かしているシミュレーションに干渉しないため）
src="source /opt/ros/humble/setup.bash"
[ -f "$(dirname "$0")/../ros2_ws/install/setup.bash" ] && src="$src && source /workspace/ros2_ws/install/setup.bash"
if [ -n "$PAI_ISOLATED" ]; then
  src="export PAI_ISOLATED=1 ROS_DOMAIN_ID=77 IGN_PARTITION=pai_test; $src"
fi
docker exec -u ubuntu -w /workspace pai_ros2 bash -lc "$src && $*"
