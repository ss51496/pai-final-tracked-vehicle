#!/bin/bash
# 突堤の評価をまとめて実行する（試験用の隔離環境）。結果は results/*.csv と logs/eval_all.log に残る。
# 長時間リセットを繰り返すと Gazebo が落ちることがあったため、条件ごとに起動し直す。
#   scripts/eval_all_berm.sh [モデル] [条件...]   条件: const1.0 const0.5 const0.25 n1 n8 n16（省略時は全部）
export PAI_ISOLATED=1
cd "$(dirname "$0")/.."
model=${1:-/workspace/checkpoints/train/tank_berm_act}; shift
conds=${@:-const1.0 const0.5 const0.25 n1 n8 n16}
for c in $conds; do
  scripts/kill_sim.sh > /dev/null; scripts/test_sim.sh berm > /dev/null
  case $c in
    const*) thr=${c#const}
      echo "##### rule-based const throttle $thr"
      scripts/dx.sh "ros2 run tank_il evaluate_berm --mode const --throttle $thr --trials 10 --out /workspace/results/rule_const_$thr.csv" 2>&1 | grep -E "^\[const" ;;
    n*) n=${c#n}
      echo "##### policy n_action_steps=$n"
      scripts/eval_policy.sh $model $n 10 policy_act_n$n.csv ;;
  esac
done
scripts/kill_sim.sh > /dev/null
