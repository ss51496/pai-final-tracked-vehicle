#!/bin/bash
# 撮影した v2 のクリップ（_raw.mp4）を、車両が障害物の付近を走る区間だけに切り出し、字幕をつける（videos/<場面>.mp4 を作り直す）。
# 切り出す区間は、xlog（録画の開始からの経過秒と x）から決める。車両が x=START に着く 1 秒前から、x=END に着く 1.5 秒後まで。
# 録画の開始と xlog の開始のずれ（約 1.8 秒）は OFF で補正する。
#   scripts/cut_clips_v2.sh              （コンテナ内で実行。または docker exec 経由）
set -e
cd "$(dirname "$0")/.."
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
OFF=${OFF:-1.8}
cut_one() {   # $1=場面名 $2=START x $3=END x $4=字幕
  python3 - "$1" "$2" "$3" "$OFF" <<'PY'
import sys
name, xs, xe, off = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
log = [tuple(map(float, l.split())) for l in open(f"videos/{name}.xlog") if len(l.split()) == 2]
ts = next((t for t, x in log if x >= xs), log[0][0]) + off
te = next((t for t, x in log if x >= xe), log[-1][0]) + off
print(f"{max(0, ts - 1.0):.2f} {te + 1.5:.2f}")
PY
}
one() {
  [ -n "$ONLY" ] && [[ " $ONLY " != *" $1 "* ]] && return 0   # ONLY="v2_ditch_human" のように指定すると、その場面だけ処理する
  read ss to < <(cut_one "$1" "$2" "$3")
  echo "$1: $ss〜$to s"
  box="drawbox=y=ih-70:w=iw:h=70:color=black@0.55:t=fill"
  ffmpeg -y -loglevel error -ss $ss -to $to -i videos/$1_raw.mp4 -vf "$box,drawtext=fontfile=$FONT:text='$4':fontcolor=white:fontsize=34:x=(w-text_w)/2:y=h-55" -c:v libx264 -pix_fmt yuv420p -crf 20 videos/$1.mp4
  ffmpeg -y -loglevel error -i videos/$1.mp4 -vf 'fps=0.7,scale=480:-1,tile=4x3' -frames:v 1 videos/$1_sheet.png
}
one v2_berm_full   90 122 "全開のまま通過：山の頂上で車体が宙に浮く"
one v2_berm_policy 90 122 "学習した方策（ACT）：山の手前で自ら減速して通過"
one v2_ditch_full  90 120 "全開のまま通過：入るときも出るときも車体が宙に浮く"
one v2_ditch_human 90 120 "人のテレオペ：壕の手前で減速し、縁でほぼ停止してから進入"
one v2_ditch_policy 90 120 "学習した方策（ACT）：壕の手前で自ら減速して通過"
