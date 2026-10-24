#!/usr/bin/env python3
"""壕（台形または V 字の深い溝）の地形モデルを生成する。

使い方:  python3 tools/gen_ditch.py <出力先ディレクトリ>   （model.sdf と model.config を書く）

無限平面は掘れないので、地面そのものを「断面（x-z 平面）の多角形を y 方向に押し出した立体」として作る。
この world では、無限平面を z=-1.5 に下げて、この立体の下面（z=-1.5）に合わせる。
壁は垂直にせず、車輪式でも登れる角度の斜面にする。

砲身の長さ（車体の前端から約 0.5 m 突き出る）と壕の幅は、
「砲塔が前向きだと砲身が向こう側の壁に当たり、90 度回すと当たらない」関係になるように決める。
"""
import math
import os
import sys

V2 = os.environ.get("TERRAIN_PROFILE") == "v2"    # 44 t 級の車両用（実寸に合わせ、80 km/h 級の助走を確保する）
def _p(name, v1, v2):
    return float(os.environ.get(name, v2 if V2 else v1))

X_NEAR = _p("DITCH_X_NEAR", 6.0, 100.0)         # 手前の縁の x 座標 [m]（車両の初期位置 x=0 から助走する）
TOP_W = _p("DITCH_TOP_W", 4.8, 9.0)     # 壕の上端の幅 [m]（環境変数で上書き可）。全開（4 m/s）でも飛び越えられず底まで落ちる広さ
DEPTH = _p("DITCH_DEPTH", 1.0, 1.5)     # 深さ [m]
SLOPE_DEG = _p("DITCH_SLOPE", 40.0, 40.0)  # 壁の角度 [deg]
LIP_LEN = _p("DITCH_LIP_LEN", 0.0, 2.5)   # 縁の面取り（水平長 [m]）。長い車体の腹が縁に乗り上げて止まるのを防ぐ
LIP_DEG = 12.0       # 縁の面取りの角度 [deg]
WIDTH = _p("TERRAIN_WIDTH", 12.0, 24.0)          # 壕の長さ（y 方向）[m]
X_MIN, X_MAX, Z_BOTTOM = -20.0, _p("TERRAIN_X_MAX", 40.0, 260.0), _p("DITCH_ZB", -1.5, -2.5)   # 立体の下面。深さ 1.0 m の壕でも底の下に厚みが残るようにする
MU = 1.0


def profile():
    lip = math.tan(math.radians(LIP_DEG)) * LIP_LEN     # 縁の面取りの深さ
    run = (DEPTH - lip) / math.tan(math.radians(SLOPE_DEG))   # 壁の水平長
    bottom = TOP_W - 2 * (run + LIP_LEN)                # 底の幅（負なら V 字として底を 0 にする）
    if bottom < 0.02:
        run, bottom = max(TOP_W / 2 - LIP_LEN - 0.01, 0.01), 0.02
    x0 = X_NEAR
    near = [(x0, 0.0), (x0 + LIP_LEN, -lip)] if LIP_LEN > 0 else [(x0, 0.0)]
    xa = x0 + LIP_LEN + run                             # 壁の下端（手前）
    xb = xa + bottom                                    # 底の奥端
    far = [(xb + run, -lip), (x0 + TOP_W, 0.0)] if LIP_LEN > 0 else [(x0 + TOP_W, 0.0)]
    pts = [(X_MIN, Z_BOTTOM), (X_MIN, 0.0)] + near + [(xa, -DEPTH), (xb, -DEPTH)] + far + [(X_MAX, 0.0), (X_MAX, Z_BOTTOM)]
    return pts, dict(x_near=x0, x_far=x0 + TOP_W, bottom_w=bottom, run=run)


def main(out_dir):
    pts, info = profile()
    poly = "\n          ".join(f"<point>{x:.4f} {z:.4f}</point>" for x, z in pts)
    geom = f"""<polyline>
          {poly}
          <height>{WIDTH}</height>
        </polyline>"""
    sdf = f"""<?xml version="1.0"?>
<!-- gen_ditch.py で生成。直接編集せず、スクリプトのパラメータを変更すること -->
<sdf version="1.8">
  <model name="ditch">
    <static>true</static>
    <pose>0 {WIDTH / 2} 0 {math.pi / 2:.5f} 0 0</pose>
    <link name="link">
      <collision name="collision">
        <geometry>
        {geom}
        </geometry>
        <surface><friction><ode><mu>{MU}</mu><mu2>{MU}</mu2></ode></friction></surface>
      </collision>
      <visual name="visual">
        <geometry>
        {geom}
        </geometry>
        <material>
          <ambient>0.50 0.43 0.32 1</ambient>
          <diffuse>0.50 0.43 0.32 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>
"""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "model.sdf"), "w") as f:
        f.write(sdf)
    with open(os.path.join(out_dir, "model.config"), "w") as f:
        f.write("""<?xml version="1.0"?>
<model>
  <name>ditch</name>
  <version>1.0</version>
  <sdf version="1.8">model.sdf</sdf>
  <description>壕（深い溝）。壁は車輪式でも登れる斜面</description>
</model>
""")
    print({k: round(v, 3) for k, v in info.items()}, file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "models/ditch")
