#!/bin/bash
# 試験用の隔離環境で、方策を評価する（scripts/test_sim.sh berm で起動済みであること）
#   PAI_ISOLATED=1 scripts/eval_policy.sh <モデルのディレクトリ> <n_action_steps> <試行回数> <結果の CSV 名>
model=${1:-/workspace/checkpoints/train/tank_berm_act}; n=${2:-0}; trials=${3:-10}; out=${4:-policy.csv}
docker exec -d -u ubuntu -w /workspace/pai_training pai_ros2 bash -lc "export ROS_DOMAIN_ID=77 IGN_PARTITION=pai_test PATH=\$HOME/.pixi/bin:\$PATH; source /opt/ros/humble/setup.bash; source /workspace/ros2_ws/install/setup.bash; pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py --model-path $model --n-action-steps $n > /workspace/logs/policy.log 2>&1"
sleep 20
"$(dirname "$0")"/dx.sh "ros2 run tank_il evaluate_berm --mode policy --trials $trials --out /workspace/results/$out" 2>&1 | grep -E "^\[policy"
docker exec pai_ros2 bash -c 'pkill -INT -f "[p]olicy_node.py"'
sleep 2
