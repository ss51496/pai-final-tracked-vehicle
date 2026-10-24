#!/bin/bash
# v2 の突堤の評価（試験用の隔離環境）。条件ごとにシミュレーションを起動し直して 10 試行する。結果は results/v2_berm_*.csv。
#   scripts/eval_v2_berm.sh [条件...]
#   条件: const1.0 const0.5 const0.25 const0.15（ルールベース。一定スロットル）
#         cmd_n<N> / nocmd_n<N>（方策。throttle_cmd あり / なし、n_action_steps=N。例 cmd_n8）
# 着地衝撃が 3.0 m/s 未満なら「跳ねずに通過」。通過の目安は x=125 m。方策の制御周期はシミュレーション時刻で 10 Hz。
export PAI_ISOLATED=1 TANK_Z=0.98
cd "$(dirname "$0")/.."
conds=${@:-const1.0 const0.5 const0.25 const0.15 cmd_n8 nocmd_n8}
EVAL="--goal-x 125 --timeout 60 --impact-thr 3.0 --trials 10"
for c in $conds; do
  scripts/kill_sim.sh > /dev/null; scripts/test_sim.sh berm_v2_cam "v_max:=22.22 omega_max:=1.0 extended_state:=true" > /dev/null; sleep 10
  case $c in
    const*) thr=${c#const}
      echo "##### rule-based const throttle $thr"
      scripts/dx.sh "TANK_Z=0.98 ros2 run tank_il evaluate_berm --mode const --throttle $thr $EVAL --out /workspace/results/v2_berm_const_$thr.csv" 2>&1 | grep -E "^\[const" ;;
    cmd_n*|nocmd_n*)
      n=${c##*_n}; dims=""; model=/workspace/checkpoints/train/tank_v2_berm_act
      if [[ $c == nocmd* ]]; then dims="--state-dims 0,1,2,3,4,5,6"; model=/workspace/checkpoints/train/tank_v2_berm_nocmd_act; fi
      echo "##### policy $c"
      docker exec -d -u ubuntu -w /workspace/pai_training pai_ros2 bash -lc "export ROS_DOMAIN_ID=77 IGN_PARTITION=pai_test PATH=\$HOME/.pixi/bin:\$PATH; source /opt/ros/humble/setup.bash; source /workspace/ros2_ws/install/setup.bash; pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py --model-path $model --n-action-steps $n --rate 10 $dims > /workspace/logs/policy.log 2>&1"
      sleep 20
      scripts/dx.sh "TANK_Z=0.98 ros2 run tank_il evaluate_berm --mode policy $EVAL --out /workspace/results/v2_berm_policy_$c.csv" 2>&1 | grep -E "^\[policy"
      docker exec pai_ros2 bash -c 'pkill -INT -f "[p]olicy_node.py"'; sleep 2 ;;
  esac
done
scripts/kill_sim.sh > /dev/null
