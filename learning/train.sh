#!/bin/bash
# タスクを指定して ACT を学習する（コンテナ内で実行、または docker exec 経由）。
#   learning/train.sh berm      突堤（learning/train_config.yaml）
#   learning/train.sh ditch     壕（learning/train_config_ditch.yaml）
# pai_training の scripts/train.py は設定を configs/train_config.yaml から固定で読むので、
# そこへのシンボリックリンクを、指定のタスクの設定に付け替えてから学習する。
set -e
task=${1:?"使い方: learning/train.sh <berm|ditch>"}
case $task in berm) cfg=train_config.yaml;; ditch) cfg=train_config_ditch.yaml;; *) echo "タスクは berm か ditch"; exit 1;; esac
ln -sf /workspace/learning/$cfg /workspace/pai_training/configs/train_config.yaml
cd /workspace/pai_training
export PATH=$HOME/.pixi/bin:$PATH WANDB_MODE=${WANDB_MODE:-offline}
echo "学習: $task（設定 $cfg）"
pixi run train
