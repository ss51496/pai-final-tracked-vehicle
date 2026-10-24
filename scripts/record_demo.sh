#!/bin/bash
# デモを 1 エピソード記録する（コンテナ内で実行。noVNC のターミナルから）。
#   scripts/record_demo.sh <タスク> <エピソード番号>        例: scripts/record_demo.sh berm 0
# 記録するトピック（/tank/state, /tank/command, /camera/image）は固定。記録の前に /tank/state が配信されているか確かめ、
# 配信されていなければ記録せずに止まる。記録は Ctrl+C で止める。止めたあと、記録されたトピックの件数を表示する。
# 事前に車両のリセット（TANK_Z=0.98 scripts/reset_tank.sh）をしておくこと。
set -e
task=${1:?"使い方: scripts/record_demo.sh <berm|ditch> <エピソード番号>"}
n=${2:?"エピソード番号が必要です"}
dir=/workspace/dataset/rosbags/v2_$task
out=$dir/ep$n
source /opt/ros/humble/setup.bash
[ -e "$out" ] && { echo "$out は既にあります。別の番号にするか、失敗した記録を消してください"; exit 1; }
mkdir -p "$dir"
echo "/tank/state を確認中..."
timeout 10 ros2 topic echo --once /tank/state --field data > /dev/null 2>&1 || { echo "/tank/state が配信されていません（シミュレーションの起動に extended_state:=true を付けましたか？）"; exit 1; }
echo "記録開始: $out（止めるときは Ctrl+C）"
ros2 bag record --use-sim-time -o "$out" /tank/state /tank/command /camera/image || true
echo "--- 記録の内容 ---"
ros2 bag info "$out" | grep -E "Duration|Topic:|Count" | sed 's/Type:.*Count/Count/'
for t in /tank/state /tank/command /camera/image; do
  ros2 bag info "$out" | grep -q "Topic: $t " || echo "警告: $t が記録されていません。このエピソードは使えません"
done
