#!/bin/bash
# 壕の評価をまとめて実行する（試験用の隔離環境）。結果は results/ditch_*.csv と標準出力に残る。
#   scripts/eval_ditch.sh baseline                    ルールベース（砲塔 90°、一定速度、手順）
#   scripts/eval_ditch.sh policy <n_action_steps...>  学習した方策（既定のモデル tank_ditch_act）
# 壕のデモはシミュレーション時刻で記録したので、方策の制御周期は 10 Hz（RATE で変更可）。
export PAI_ISOLATED=1
cd "$(dirname "$0")/.."
mode=${1:-baseline}; shift
MODEL=${MODEL:-/workspace/checkpoints/train/tank_ditch_act}
RATE=${RATE:-10}
scripts/kill_sim.sh > /dev/null; scripts/test_sim.sh ditch > /dev/null
ev() { scripts/dx.sh "ros2 run tank_il evaluate_ditch $*" 2>&1 | grep -aE "回中"; }
case $mode in
  baseline)
    echo "# ルールベース（砲塔 90°）"
    for thr in 0.25 0.5 1.0; do echo -n "一定 $thr : "; ev --mode scripted --turret-deg 90 --entry-throttle $thr --trials 10 --out /workspace/results/ditch_rule_const_$thr.csv; done
    echo -n "0.5 → x=8.7 から全開 : "; ev --mode scripted --turret-deg 90 --entry-throttle 0.5 --switch-x 8.7 --trials 10 --out /workspace/results/ditch_rule_0.5_sw8.7.csv
    echo -n "砲塔 0°（前向き）・一定 0.5 : "; ev --mode scripted --turret-deg 0 --entry-throttle 0.5 --trials 10 --out /workspace/results/ditch_rule_front_0.5.csv ;;
  policy)
    for n in "$@"; do
      docker exec -d -u ubuntu -w /workspace/pai_training pai_ros2 bash -lc "export ROS_DOMAIN_ID=77 IGN_PARTITION=pai_test PATH=\$HOME/.pixi/bin:\$PATH; source /opt/ros/humble/setup.bash; source /workspace/ros2_ws/install/setup.bash; pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py --model-path $MODEL --n-action-steps $n --rate $RATE > /workspace/logs/policy.log 2>&1"
      sleep 20
      echo -n "ACT n_action_steps=$n : "; ev --mode policy --trials 10 --out /workspace/results/ditch_policy_n$n.csv
      docker exec pai_ros2 bash -c 'pkill -INT -f "[p]olicy_node.py"'; sleep 2
    done ;;
esac
scripts/kill_sim.sh > /dev/null
