#!/bin/bash
# v2 の提出用動画の下書きを組み立てる（説明カード＋撮影済みのクリップ → videos/final_v2_draft.mp4）。
# 事前に scripts/record_clips_v2.sh でクリップを撮っておくこと。長いクリップを倍速にした場合は、左上に倍速を表示する。
# コンテナ内の ffmpeg で作る（日本語フォント Noto Sans CJK を使う）。
set -e
cd "$(dirname "$0")/.."
docker exec -i -u ubuntu -w /workspace pai_ros2 bash -s <<'EOS'
set -e
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
V=videos; S=$V/seg_v2; rm -rf $S; mkdir -p $S $V/cards_v2
ENC="-r 30 -c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 20 -an"
LIST=$S/list.txt; : > $LIST
n=0
add() { echo "file '$PWD/$1'" >> $LIST; }

# 説明カード: card <秒> <行...>。1 行目は見出し（大きく、色つき）、残りは本文。行ごとに中央寄せで描く
card() {
  n=$((n+1)); local dur=$1; shift
  local total=$#; local lh=64; local y0=$(( (720 - total * lh) / 2 )); local k=0; local vf=""
  for line in "$@"; do
    if [ -n "$line" ]; then
      echo -n "$line" > $V/cards_v2/c${n}_$k.txt
      local fs=38 col=white
      if [ $k = 0 ]; then fs=52; col=0xffe08a; fi
      vf="$vf${vf:+,}drawtext=fontfile=$FONT:textfile=$V/cards_v2/c${n}_$k.txt:expansion=none:fontsize=$fs:fontcolor=$col:x=(w-text_w)/2:y=$((y0 + k * lh))"
    fi
    k=$((k+1))
  done
  ffmpeg -nostdin -y -loglevel error -f lavfi -i "color=c=0x1f4d36:s=1280x720:r=30:d=$dur" -vf "$vf" $ENC $S/s$n.mp4
  add $S/s$n.mp4
}
# クリップ: clip <ファイル> [倍速 1, 2, 4]
clip() {
  n=$((n+1)); local src=$1 sp=${2:-1}
  if [ "$sp" != 1 ]; then
    local label="${sp}倍速"; [ "$(echo "$sp < 1" | bc -l)" = 1 ] && label="スロー（${sp}倍）"
    ffmpeg -nostdin -y -loglevel error -i $src -vf "setpts=PTS/$sp,fps=30,scale=1280:720,drawtext=fontfile=$FONT:text='$label':fontsize=40:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10:x=24:y=24" $ENC $S/s$n.mp4
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

# 速度の指定（環境変数 SP_*。クリップが長いときに 2 や 4 にする）。既定は 1
card 4 "重量装軌車両の不整地走行を" "模倣学習（ACT）で再現する" "" "突堤と壕の通過：飛びを抑えつつ、速度を保つ"
card 8 "課題" "" "重い車両は、段差や溝の縁で宙に浮くと" "着地の衝撃で故障する" "かといって、ずっとゆっくり走るのも非効率" "" "通過の瞬間は速度を抑え、他は速度を出す"
card 7 "車両と地形（シミュレーション）" "" "44 t 級の架空の重量車両（片側 8 輪のスキッドステア＋砲塔）" "最高 80 km/h、加速 1.5 m/s²、減速 3.5 m/s²" "突堤と壕（助走 100 m）" "" "※ 映像は描画の負荷で実時間より遅く再生される"
figure videos/v2_vehicle.png 5 "44 t 級の重量装軌車両（片側 8 輪のスキッドステア）"

card 3 "【突堤】" "" "全開のまま越えると、車体が跳ねる"
clip videos/v2_berm_full.mp4 ${SP_BERM_FULL:-0.5}
card 3 "熟練者のテレオペ（10 本）" "" "助走は全開、山の手前で速度を落とす"
figure docs/v2_berm_demo.png 5 "デモ：約 60〜90 m で段階的に減速し、越えたら再加速"
card 3 "学習した方策（ACT）" "" "山の手前で、自ら減速して通過"
clip videos/v2_berm_policy.mp4 ${SP_BERM_POLICY:-1}
card 6 "突堤の結果（各10試行）" "" "全開：跳ねずに通過 0/10、13.1 秒" "一定 0.5：10/10、15.1 秒" "ACT：10/10、14.1〜14.5 秒（人のデモ 14.9 秒）"

card 4 "【壕】" "" "砲塔が前向きのまま進入すると" "砲身が向こう側の壁に接触する（接触センサーが検出）"
clip videos/v2_ditch_front.mp4 ${SP_DITCH_FRONT:-2}
card 4 "砲塔を 90° にしても" "" "全開のままだと、車体が宙に浮く"
clip videos/v2_ditch_full.mp4 ${SP_DITCH_FULL:-0.5}
card 3 "熟練者のテレオペ（10 本）" "" "壕の手前で減速し、縁でほぼ停止して進入"
clip videos/v2_ditch_human.mp4 ${SP_DITCH_HUMAN:-2}
card 3 "学習した方策（ACT）" "" "砲塔は最初から 90°（砲塔の操作は学習しない）" "壕の手前で減速して通過"
clip videos/v2_ditch_policy.mp4 ${SP_DITCH_POLICY:-1}
figure docs/v2_results.png 7 "結果：ACT は人より速いが、壕に入るときの衝撃が基準をわずかに超える"
card 8 "壕の結果（各10試行）" "" "砲身が壁に当たらずに通過：10/10（砲塔 90° 固定）" "所要 17.5 秒（人のデモ 21.5 秒）" "入るときの着地衝撃 3.35 m/s（基準 3.0、人 1.87）" "→ 飛ばずに通過 2/10：速度と飛びの両立は未達"

card 10 "失敗と学び" "" "・砲塔を回す時刻は観測から決まらず、学習できなかった" "　→ 砲塔は最初から 90° にして、学習から外した" "・ばらつき 0 の入力が方策を壊した → 観測から外した" "・飛びの指標は、IMU から真値の鉛直速度に作り直した" "・画像入力は、10 本のデータでは不安定だった"
card 6 "まとめ" "" "突堤：跳ねずに、人と同じ速さで通過（10/10）" "壕：砲塔を使い分けて通過、減速の深さが課題" "" "シミュレーション：Ignition Gazebo + ROS 2" "学習：LeRobot（ACT、GPU）"

ffmpeg -nostdin -y -loglevel error -f concat -safe 0 -i $LIST -c copy $V/final_v2_draft.mp4
d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $V/final_v2_draft.mp4)
echo "final_v2_draft.mp4: ${d} 秒"
EOS
