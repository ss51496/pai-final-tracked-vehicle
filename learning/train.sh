#!/bin/bash
# タスクを指定して ACT を学習する（コンテナ内で実行、または docker exec 経由）。
#   learning/train.sh berm      突堤（learning/train_config.yaml）
#   learning/train.sh ditch     壕（learning/train_config_ditch.yaml）
#   learning/train.sh v2_berm   v2 の突堤（GPU。観測から throttle_cmd を除くときは TANK_STATE_CMD=0 を付ける）
#   learning/train.sh v2_ditch  v2 の壕
# pai_training の scripts/train.py は設定を configs/train_config.yaml から固定で読むので、
# そこへのシンボリックリンクを、指定のタスクの設定に付け替えてから学習する。
set -e
task=${1:?"使い方: learning/train.sh <berm|ditch>"}
case $task in berm) cfg=train_config.yaml;; ditch) cfg=train_config_ditch.yaml;;
  v2_berm) cfg=train_config_v2_berm.yaml; export TANK_TASK=berm;; v2_ditch) cfg=train_config_v2_ditch.yaml; export TANK_TASK=ditch;;
  v2_ditch_t90) cfg=train_config_v2_ditch_t90.yaml; export TANK_TASK=ditch_t90;;
  *) echo "タスクは berm, ditch, v2_berm, v2_ditch, v2_ditch_t90"; exit 1;; esac
if [ "${TANK_STATE_CMD:-1}" = "0" ] && [[ $task == v2_* ]]; then   # throttle_cmd を除く比較実験：データセットと出力の名前に _nocmd を付ける
  sed -E 's/tank_v2_(berm|ditch(_t90)?)/&_nocmd/g' /workspace/learning/$cfg > /workspace/learning/.generated_$cfg
  cfg=.generated_$cfg
fi
if [ -n "$TRAIN_STEPS" ]; then   # 学習ステップ数を変える（出力先の名前に _s<ステップ数> を付けて、既存のモデルを残す）
  sed -E "s/training_steps: [0-9]+/training_steps: $TRAIN_STEPS/; s/(output_directory: .*)_act\"/\1_s${TRAIN_STEPS}_act\"/" /workspace/learning/$cfg > /workspace/learning/.generated_steps_$(basename $cfg)
  cfg=.generated_steps_$(basename $cfg)
fi
ln -sf /workspace/learning/$cfg /workspace/pai_training/configs/train_config.yaml
cd /workspace/pai_training
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0} PATH=$HOME/.pixi/bin:$PATH WANDB_MODE=${WANDB_MODE:-offline}
echo "学習: $task（設定 $cfg）"
pixi run train
