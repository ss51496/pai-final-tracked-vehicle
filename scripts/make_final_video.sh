#!/bin/bash
# 提出用の動画の下書きを組み立てる（説明カード＋撮影済みのクリップ → videos/final_draft.mp4）。
# 事前に scripts/record_clips.sh と scripts/record_ditch_clips.sh でクリップを撮っておくこと。
# 長いクリップは 2 倍速にして、左上に「2倍速」と表示する（課題の要件：倍速の場合は明記）。
# コンテナ内の ffmpeg で作る（日本語フォント Noto Sans CJK を使う）。
set -e
cd "$(dirname "$0")/.."
docker exec -i -u ubuntu -w /workspace pai_ros2 bash -s <<'EOS'
set -e
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
V=videos; S=$V/seg; rm -rf $S; mkdir -p $S $V/cards
ENC="-r 30 -c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 20 -an"
LIST=$S/list.txt; : > $LIST
n=0
add() { echo "file '$PWD/$1'" >> $LIST; }

# 説明カード: card <秒> <行...>。1 行目は見出し（大きく、色つき）、残りは本文。行ごとに中央寄せで描く
card() {
  n=$((n+1)); local dur=$1; shift
  local total=$#; local lh=66; local y0=$(( (720 - total * lh) / 2 )); local k=0; local vf=""
  for line in "$@"; do
    if [ -n "$line" ]; then
      echo -n "$line" > $V/cards/c${n}_$k.txt
      local fs=40 col=white
      if [ $k = 0 ]; then fs=54; col=0xffe08a; fi
      vf="$vf${vf:+,}drawtext=fontfile=$FONT:textfile=$V/cards/c${n}_$k.txt:expansion=none:fontsize=$fs:fontcolor=$col:x=(w-text_w)/2:y=$((y0 + k * lh))"
    fi
    k=$((k+1))
  done
  ffmpeg -nostdin -y -loglevel error -f lavfi -i "color=c=0x1f4d36:s=1280x720:r=30:d=$dur" -vf "$vf" $ENC $S/s$n.mp4
  add $S/s$n.mp4
}
# クリップ: clip <ファイル> [倍速 1 or 2]
clip() {
  n=$((n+1)); local src=$1 sp=${2:-1}
  if [ "$sp" = 2 ]; then
    ffmpeg -nostdin -y -loglevel error -i $src -vf "setpts=0.5*PTS,fps=30,scale=1280:720,drawtext=fontfile=$FONT:text='2倍速':fontsize=40:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10:x=24:y=24" $ENC $S/s$n.mp4
  else
    ffmpeg -nostdin -y -loglevel error -i $src -vf "fps=30,scale=1280:720" $ENC $S/s$n.mp4
  fi
  add $S/s$n.mp4
}
# 図: figure <画像> <秒> <字幕>
figure() {
  n=$((n+1)); local img=$1 dur=$2 cap=$3
  ffmpeg -nostdin -y -loglevel error -loop 1 -t $dur -r 30 -i $img -vf "scale=1280:640:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:0:color=white,drawbox=y=ih-80:w=iw:h=80:color=black@0.7:t=fill,drawtext=fontfile=$FONT:text='$cap':fontsize=34:fontcolor=white:x=(w-text_w)/2:y=h-58" $ENC $S/s$n.mp4
  add $S/s$n.mp4
}

card 4 "装軌車両の不整地走行を" "模倣学習（ACT）で再現する" "" "突堤と壕の通過：飛びを抑えつつ、速度を保つ"
card 7 "課題" "" "重い車両は、段差や溝の縁で宙に浮くと" "着地の衝撃で故障する" "かといって、ずっとゆっくり走るのも非効率" "" "通過の瞬間は速度を抑え、他は速度を出す"

card 3 "【突堤】" "" "全開のまま越えると、車体が跳ねる"
clip $V/rule_full.mp4
card 3 "熟練者のテレオペ" "" "10 エピソードのデモを収集"
clip $V/human_demo.mp4
figure docs/rollout_n8.png 5 "学習：方策（赤）はデモ（灰）と同様に、頂上で減速する"
card 3 "学習した方策（ACT）" "" "頂上の手前で、自ら減速して通過"
clip $V/policy.mp4
card 6 "突堤の結果（各10試行）" "" "全開：跳ねずに通過 0/10、3.8 秒" "低速一定（0.25）：10/10、13.7 秒" "ACT：10/10、3.1 秒"

card 4 "【壕】" "" "砲塔が前向きのまま進入すると" "砲身が向こう側の壁に当たって動けない"
clip $V/ditch_front.mp4 2
card 4 "砲塔を 90° に回しても" "" "全開のままだと、車体が宙に浮く"
clip $V/ditch_full.mp4
card 3 "熟練者のテレオペ" "" "走りながら砲塔を回し、縁で速度を落とす"
clip $V/ditch_human.mp4
figure docs/debug_policy_ditch.png 5 "学習：予測（緑）は操縦者の操作（赤）を再現する"
card 3 "学習した方策（ACT）" "" "砲塔を自ら 90° に回し、壕の縁で減速"
clip $V/ditch_policy.mp4
card 7 "壕の結果（各10試行）" "" "砲塔前向き：砲身が接触（接触せずに通過 0/10）" "ACT：接触せずに 10/10" "デモと同程度の飛びで、約 26% 速い（5.0 → 3.7 秒）"

card 6 "まとめ" "" "熟練者のデモ 10 回から、速度の切り替えと" "砲塔の操作を学習した" "突堤：全開と同程度の速さで、跳ねずに通過" "壕：デモと同程度の飛びで、約 26% 速く通過" "" "シミュレーション：Ignition Gazebo + ROS 2" "学習：LeRobot（ACT）"

ffmpeg -nostdin -y -loglevel error -f concat -safe 0 -i $LIST -c copy $V/final_draft.mp4
d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $V/final_draft.mp4)
echo "final_draft.mp4: ${d} 秒"
EOS
