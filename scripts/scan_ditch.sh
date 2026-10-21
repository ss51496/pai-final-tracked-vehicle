#!/bin/bash
# 壕の寸法を変えながら、砲身の接触と通過を調べる（試験用の隔離環境、探索用）
#   scripts/scan_ditch.sh "<幅...>" "<深さ>" "<斜面角>" "<スロットル...>"
export PAI_ISOLATED=1
cd "$(dirname "$0")/.."
widths=${1:-"2.0 2.4"}; depth=${2:-0.6}; slope=${3:-40}; thrs=${4:-0.25}
for w in $widths; do
  scripts/kill_sim.sh > /dev/null
  DITCH_TOP_W=$w DITCH_DEPTH=$depth DITCH_SLOPE=$slope python3 ros2_ws/src/tank_il/tools/gen_ditch.py ros2_ws/src/tank_il/models/ditch 2>&1 | sed "s/^/幅$w 深さ$depth 角度$slope: /"
  scripts/test_sim.sh ditch > /dev/null
  for thr in $thrs; do
    for tur in 0 90; do
      timeout 80 scripts/dx.sh "python3 -u logs/test_ditch.py $tur $thr 30" 2>&1 | tail -1
    done
  done
done
scripts/kill_sim.sh > /dev/null
