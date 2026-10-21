#!/bin/bash
# シミュレーション関連のプロセスをすべて止める（コンテナ内で実行される）
# パターンの先頭文字を [] で囲むのは、pkill が自分自身のコマンドラインに一致して
# 途中で終了するのを避けるため。
docker exec pai_ros2 bash -c '
for p in "[r]os2 launch" "[i]gn gazebo" "[r]uby" "[p]arameter_bridge" "[t]ank_driver" "[s]tate_publisher" "[t]eleop_tank"; do
  pkill -f "$p"
done
sleep 2
echo "残りのプロセス数: $(ps aux | grep -E "[i]gn gazebo|[r]uby|[p]arameter_bridge|[t]ank_driver|[s]tate_publisher" | wc -l)"
'
