#!/bin/bash
# シミュレーション関連のプロセスを止める。ホスト（WSL）からも、コンテナ内（noVNC のターミナル）からも実行できる。
#   scripts/kill_sim.sh                 すべて止める（応答しないものは強制終了する）
#   PAI_ISOLATED=1 scripts/kill_sim.sh  試験用（scripts/test_sim.sh で起動したもの）だけ止める（ホストからのみ）
# パターンの先頭文字を [] で囲むのは、pkill が自分自身のコマンドラインに一致して
# 途中で終了するのを避けるため。
KILL_ALL='
for p in "[r]os2 launch" "[i]gn gazebo" "[r]uby" "[p]arameter_bridge" "[t]ank_driver" "[s]tate_publisher" "[t]eleop_tank"; do
  pkill -f "$p"
done
sleep 2
# 終了しなかった（応答しなくなった）ものは強制終了する。Gazebo のサーバーは SIGTERM で止まらないことがある
for p in "[i]gn gazebo" "[r]uby" "[p]arameter_bridge"; do
  pkill -9 -f "$p"
done
sleep 1
echo "残りのプロセス数: $(ps aux | grep -E "[i]gn gazebo|[r]uby|[p]arameter_bridge|[t]ank_driver|[s]tate_publisher" | wc -l)"'

if [ -f /.dockerenv ]; then
  bash -c "$KILL_ALL"
elif [ -n "$PAI_ISOLATED" ]; then
  docker exec pai_ros2 bash -c '
  pg=$(cat /workspace/logs/test_sim.pgid 2>/dev/null)
  [ -n "$pg" ] && kill -INT -- -$pg 2>/dev/null
  sleep 3
  [ -n "$pg" ] && kill -KILL -- -$pg 2>/dev/null
  rm -f /workspace/logs/test_sim.pgid
  echo "試験用プロセスを停止"'
else
  docker exec pai_ros2 bash -c "$KILL_ALL"
fi
