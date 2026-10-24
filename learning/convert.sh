#!/bin/bash
# タスクを指定して rosbag を LeRobotDataset に変換する。
#   learning/convert.sh berm | ditch  [--overwrite]
set -e
task=${1:?"使い方: learning/convert.sh <berm|ditch> [--overwrite]"}; shift
case $task in berm) cfg=conversion_config.yaml;; ditch) cfg=conversion_config_ditch.yaml;;
  v2_berm) cfg=conversion_config_v2_berm.yaml; export TANK_TASK=berm;; v2_ditch) cfg=conversion_config_v2_ditch.yaml; export TANK_TASK=ditch;;
  *) echo "タスクは berm, ditch, v2_berm, v2_ditch（v2 で throttle_cmd を除くときは TANK_STATE_CMD=0）"; exit 1;; esac
cd /workspace/pai_training
export PATH=$HOME/.pixi/bin:$PATH
pixi run python /workspace/learning/rosbag2lerobot_tank.py --config /workspace/learning/$cfg "$@"
