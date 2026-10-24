#!/usr/bin/env python3
"""突堤（台形の山）のモデルを生成する。

使い方:  python3 tools/gen_berm.py <出力先ディレクトリ>   （model.sdf と model.config を書く）

断面（x-z 平面）の多角形を y 方向に押し出して作る。登り口と下り口の根元は、
車体の前端が地面に刺さらないよう小さな面取りを入れる。頂上の縁は鋭いままにして、
全開で越えると車体が跳ねるようにする。
"""
import math
import os
import sys

# TERRAIN_PROFILE=v2 は 44 t 級の車両用（寸法を実寸に合わせ、80 km/h 級の助走を確保する）。環境変数で個別に上書きもできる
V2 = os.environ.get("TERRAIN_PROFILE") == "v2"
def _p(name, v1, v2):
    return float(os.environ.get(name, v2 if V2 else v1))

X_START = _p("BERM_X_START", 6.0, 100.0)       # 登り口の x 座標 [m]（車両の初期位置 x=0 から助走する）
HEIGHT = _p("BERM_HEIGHT", 1.0, 1.5)         # 山の高さ [m]
SLOPE_DEG = _p("BERM_SLOPE", 35.0, 20.0)     # 斜面の角度 [deg]
TOP_LEN = _p("BERM_TOP_LEN", 0.3, 6.0)        # 頂上の平らな部分の長さ [m]（小さいほど尖る）
CHAMFER_DEG = 17.0   # 根元の面取りの角度 [deg]
CHAMFER_LEN = _p("BERM_CHAMFER", 0.30, 0.8)   # 根元の面取りの水平長 [m]
CREST_LEN = _p("BERM_CREST_LEN", 0.0, 3.0)   # 頂上の縁の面取り（水平長 [m]）。長い車体が縁で前のめりに落ちるのを和らげる
CREST_DEG = 10.0     # 頂上の縁の面取りの角度 [deg]
WIDTH = _p("TERRAIN_WIDTH", 12.0, 24.0)         # 山の幅（y 方向）[m]
X_MIN, X_MAX, Z_BOTTOM = -20.0, _p("TERRAIN_X_MAX", 40.0, 260.0), -1.0
MU = 1.0


def profile():
    t = math.tan(math.radians(SLOPE_DEG))
    c = math.tan(math.radians(CHAMFER_DEG)) * CHAMFER_LEN
    cr = math.tan(math.radians(CREST_DEG)) * CREST_LEN    # 頂上の面取りの高さ
    run = (HEIGHT - c - cr) / t                  # 斜面本体の水平長
    x1 = X_START                                 # 登り口
    x2 = x1 + CHAMFER_LEN                        # 面取りの終わり
    x3a = x2 + run                               # 斜面本体の終わり（面取りの始まり）
    x3 = x3a + CREST_LEN                         # 頂上の手前の縁
    x4 = x3 + TOP_LEN                            # 頂上の奥の縁
    x4a = x4 + CREST_LEN                         # 下り側の面取りの終わり
    x5 = x4a + run                               # 下り斜面の終わり
    x6 = x5 + CHAMFER_LEN
    up = [(x3a, HEIGHT - cr)] if CREST_LEN > 0 else []
    down = [(x4a, HEIGHT - cr)] if CREST_LEN > 0 else []
    pts = [(X_MIN, 0.0), (x1, 0.0), (x2, c)] + up + [(x3, HEIGHT), (x4, HEIGHT)] + down + [
           (x5, c), (x6, 0.0), (X_MAX, 0.0), (X_MAX, Z_BOTTOM), (X_MIN, Z_BOTTOM)]
    return pts, dict(x_up=x1, x_crest=x3, x_top_end=x4, x_down_end=x6)


def main(out_dir):
    pts, info = profile()
    poly = "\n          ".join(f"<point>{x:.4f} {z:.4f}</point>" for x, z in pts)
    geom = f"""<polyline>
          {poly}
          <height>{WIDTH}</height>
        </polyline>"""
    # 断面は x-z 平面。polyline は z 方向に押し出されるので、x まわりに 90 度回して
    # 押し出し方向を -y に向け、y=+WIDTH/2 から -WIDTH/2 に広げる。
    sdf = f"""<?xml version="1.0"?>
<!-- gen_berm.py で生成。直接編集せず、スクリプトのパラメータを変更すること -->
<sdf version="1.8">
  <model name="berm">
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
          <ambient>0.45 0.40 0.30 1</ambient>
          <diffuse>0.45 0.40 0.30 1</diffuse>
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
  <name>berm</name>
  <version>1.0</version>
  <sdf version="1.8">model.sdf</sdf>
  <description>突堤（台形の山）。登り斜面、平らな頂上、下り斜面</description>
</model>
""")
    print({k: round(v, 3) for k, v in info.items()}, file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "models/berm")
