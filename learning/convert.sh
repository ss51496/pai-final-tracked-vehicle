#!/bin/bash
# タスクを指定して rosbag を LeRobotDataset に変換する。
#   learning/convert.sh berm | ditch  [--overwrite]
set -e
task=${1:?"使い方: learning/convert.sh <berm|ditch> [--overwrite]"}; shift
case $task in berm) cfg=conversion_config.yaml;; ditch) cfg=conversion_config_ditch.yaml;; *) echo "タスクは berm か ditch"; exit 1;; esac
cd /workspace/pai_training
export PATH=$HOME/.pixi/bin:$PATH
pixi run python /workspace/learning/rosbag2lerobot_tank.py --config /workspace/learning/$cfg "$@"
