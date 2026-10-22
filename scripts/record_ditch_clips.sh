#!/bin/bash
# 壕の比較映像を自動で録画する（砲塔が前向きだと砲身が壁に当たる／90° 回すと当たらない）。
#   ditch_front   砲塔 0°（前向き）で進入 → 砲身が向こう側の壁に当たって動けなくなる
#   ditch_turn90  砲塔 90° に回してから進入、出口の手前で全開 → 接触せずに通過
# 動いているシミュレーションは停止する。出力: videos/<場面>.mp4（字幕つき）と _slow.mp4
set -e
cd "$(dirname "$0")/.."
source scripts/lib_record.sh
start_sim ditch video_gui_ditch.config

scripts/reset_tank.sh > /dev/null
start_rec ditch_front
X 'ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 0 --entry-throttle 0.25 --trials 1 > /dev/null' || true
stop_vehicle; stop_rec
finish ditch_front "砲塔が前向きのまま進入：砲身が向こう側の壁に当たって動けない"

scripts/reset_tank.sh > /dev/null
start_rec ditch_turn90
X 'ros2 run tank_il evaluate_ditch --mode scripted --turret-deg 90 --entry-throttle 0.25 --switch-x 8.7 --trials 1 > /dev/null' || true
stop_vehicle; stop_rec
finish ditch_turn90 "砲塔を90°回してから進入：砲身が壁に当たらずに通過"

scripts/kill_sim.sh > /dev/null
ls -la videos/ditch_*.mp4
