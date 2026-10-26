#!/bin/bash
# v2 の壕の評価（試験用の隔離環境）。条件ごとにシミュレーションを起動し直して 10 試行する。結果は results/v2_ditch_*.csv。
#   scripts/eval_v2_ditch.sh [条件...]
#   条件: front015  砲塔 0° のまま一定 0.15（壕の手前で砲身が壁に当たる失敗例）
#         const015  砲塔 90°、一定 0.15（飛ばないが遅い）
#         full      砲塔 90°、全開のまま（飛ぶ）
#         slowzone  砲塔 90°、x=70 m から 0.15、x=112 m から全開（ルールベースの目安）
#         t90nocmd_n<N>  砲塔を最初から 90° にして始める方策（throttle_cmd なし、砲塔の操作は学習しない）
#         cmd_n<N> / nocmd_n<N>  方策（throttle_cmd あり / なし、n_action_steps=N）
# 判定：通過し、砲身の接触がなく、入るとき・出るときの着地衝撃がともに 3.0 m/s 未満なら「飛ばずに通過」。通過の目安は x=135 m。
export PAI_ISOLATED=1 TANK_Z=0.98
cd "$(dirname "$0")/.."
conds=${@:-front015 const015 full slowzone cmd_n8 nocmd_n8}
EVAL="--goal-x 135 --split-x 105.5 --timeout 90 --impact-thr 3.0 --trials ${TRIALS:-10}"
for c in $conds; do
  scripts/kill_sim.sh > /dev/null; scripts/test_sim.sh ditch_v2_cam "v_max:=22.22 omega_max:=1.0 extended_state:=true" > /dev/null; sleep 10
  case $c in
    front015) args="--mode scripted --turret-deg 0 --entry-throttle 0.15" ;;
    const015) args="--mode scripted --turret-deg 90 --entry-throttle 0.15" ;;
    full)     args="--mode scripted --turret-deg 90 --entry-throttle 1.0" ;;
    slowzone) args="--mode scripted --turret-deg 90 --profile 0:1.0,70:0.15,112:1.0" ;;
  esac
  case $c in
    front015|const015|full|slowzone)
      echo "##### rule-based $c"
      scripts/dx.sh "TANK_Z=0.98 ros2 run tank_il evaluate_ditch $args $EVAL --out /workspace/results/v2_ditch_$c.csv" 2>&1 | grep -E "^\[scripted" ;;
    cmd_n*|nocmd_n*|t90nocmd_n*)
      n=${c##*_n}; dims=""; model=/workspace/checkpoints/train/tank_v2_ditch_act; turret=0
      if [[ $c == nocmd* ]]; then dims="--state-dims 0,1,2,3,4,5,6"; model=/workspace/checkpoints/train/tank_v2_ditch_nocmd_act; fi
      # t90nocmd：砲塔を最初から 90° にして始め、砲塔の操作を学習しない方策（learning/train.sh v2_ditch_t90）
      if [[ $c == t90nocmd* ]]; then dims="--state-dims 0,1,2,3,5,6"; model=/workspace/checkpoints/train/tank_v2_ditch_t90_nocmd${MODEL_TAG:-}_act; turret=90; fi
      echo "##### policy $c"
      docker exec -d -u ubuntu -w /workspace/pai_training pai_ros2 bash -lc "export ROS_DOMAIN_ID=77 IGN_PARTITION=pai_test PATH=\$HOME/.pixi/bin:\$PATH; source /opt/ros/humble/setup.bash; source /workspace/ros2_ws/install/setup.bash; pixi run python /workspace/ros2_ws/src/tank_il/tank_il/policy_node.py --model-path $model --n-action-steps $n --rate 10 $dims > /workspace/logs/policy.log 2>&1"
      sleep 20
      scripts/dx.sh "TANK_Z=0.98 TURRET_DEG=$turret ros2 run tank_il evaluate_ditch --mode policy $EVAL --out /workspace/results/v2_ditch_policy_${c}${TAG:-}.csv" 2>&1 | grep -E "^\[policy"
      docker exec pai_ros2 bash -c 'pkill -INT -f "[p]olicy_node.py"'; sleep 2 ;;
  esac
done
scripts/kill_sim.sh > /dev/null
