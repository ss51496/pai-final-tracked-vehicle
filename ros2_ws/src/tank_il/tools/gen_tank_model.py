#!/usr/bin/env python3
"""装軌車両（多輪スキッドステア）の model.sdf を生成する。

使い方（TANK_PROFILE で車両の種類を選ぶ。既定は v1）:
  python3 tools/gen_tank_model.py > models/tank/model.sdf                       # v1：砲身 1.3 m（突堤用）。CONTACT_SENSORS=0
  BARREL_LEN=2.0 python3 tools/gen_tank_model.py > models/tank_long/model.sdf    # v1：砲身 2.0 m（壕用）
  TANK_PROFILE=v2 python3 tools/gen_tank_model.py > models/tank_v2/model.sdf      # v2：44 t 級の実寸の車両

履帯は見た目用の箱で、接地・駆動は片側 N 輪の車輪で行う。慣性は形状と質量から計算する。
v1 は架空の小型車両（約 445 kg）。v2 は、公開されている諸元（重量 約 44 t、全長 約 9.4 m、全幅 約 3.2 m、全高 約 2.3 m、
砲身長 約 5.3 m）に合わせた。公開されていない車体長（約 7.4 m）、転輪の数（片側 8 個、接地長 約 6.7 m）などは、全長から見積もった仮定の値。
"""
import math
import os

PROFILE = os.environ.get("TANK_PROFILE", "v1")

# 車両のプロファイル。TURRET_SHAPE は "cyl"（円柱：R, H）または "box"（直方体：SIZE）。
PROFILES = {
    "v1": dict(
        CH_L=2.0, CH_W=1.0, CH_H=0.4, CH_MASS=300.0, CLEARANCE=0.12,           # 車体 [m, kg]
        N_WHEELS=7, WHEEL_R=0.15, WHEEL_LEN=0.14, WHEEL_MASS=5.0, WHEEL_PITCH=0.30, WHEEL_Y=None,
        MU_ROLL=1.2, MU_LATERAL=0.5,
        TURRET_SHAPE="cyl", TURRET_R=0.35, TURRET_H=0.18, TURRET_SIZE=None, TURRET_MASS=60.0, TURRET_X=0.0,
        BARREL_R=0.04, BARREL_LEN=1.3, BARREL_MASS=15.0, BARREL_X0=0.20, BARREL_Z=0.0,
        TURRET_P=500, TURRET_D=100, TURRET_CMD_MAX=2000, TURRET_DAMPING=5,
        DD_LIMITS=None,
    ),
    # 44 t 級。全長 9.42 m ＝ 車体 7.4 m ＋ 砲の突き出し（砲身 5.28 m のうち車体の前端より前に出る分）約 2.0 m。
    # 全幅 3.24 m ＝ 履帯 0.62 m×2（中心間隔 2.62 m）。全高 2.30 m ＝ 地上高 0.45 + 車体 1.0 + 砲塔 0.85。
    # 質量 44 t ＝ 車体 28.5 t + 車輪 16×0.3 t + 砲塔 8.5 t + 砲身 2.2 t。
    "v2": dict(
        CH_L=7.4, CH_W=2.6, CH_H=1.0, CH_MASS=28500.0, CLEARANCE=0.45,
        N_WHEELS=8, WHEEL_R=0.45, WHEEL_LEN=0.62, WHEEL_MASS=300.0, WHEEL_PITCH=0.95, WHEEL_Y=1.31,
        MU_ROLL=1.2, MU_LATERAL=0.5,
        TURRET_SHAPE="box", TURRET_R=None, TURRET_H=0.85, TURRET_SIZE=(3.0, 2.5, 0.85), TURRET_MASS=8500.0, TURRET_X=0.3,
        BARREL_R=0.08, BARREL_LEN=5.28, BARREL_MASS=2200.0, BARREL_X0=0.14, BARREL_Z=0.05,
        TURRET_P=480000, TURRET_D=190000, TURRET_CMD_MAX=3000000, TURRET_DAMPING=5000,
        # 動力特性（仮定の値。公開情報にないため、44 t 級の車両の一般的な目安として置いた）
        #   最高速度 80 km/h（前進）、40 km/h（後退）。加速 1.5 m/s²（0→80 km/h に約 15 秒）、減速 3.5 m/s²（80 km/h から約 70 m）。
        #   旋回は最大 1.0 rad/s（約 57°/s）、角加速度 1.0 rad/s²。
        DD_LIMITS=dict(max_linear_velocity=22.22, min_linear_velocity=-11.11,
                       max_linear_acceleration=1.5, min_linear_acceleration=-3.5,
                       max_angular_velocity=1.0, min_angular_velocity=-1.0,
                       max_angular_acceleration=1.0, min_angular_acceleration=-1.5),
    ),
}
globals().update(PROFILES[PROFILE])
if "BARREL_LEN" in os.environ:                 # 砲身の長さだけを環境変数で上書きできる
    BARREL_LEN = float(os.environ["BARREL_LEN"])

# 接触センサー（砲身・車体）。壕の評価に使う。突堤用のモデルには付けない（付けると方策の結果が変わったため）
CONTACT_SENSORS = os.environ.get("CONTACT_SENSORS", "1") == "1"

HULL_SENSOR = """      <!-- 車体が壁などに接触（激突）したかを検出する（砲身の接触センサーとは別） -->
      <sensor name="hull_contact" type="contact">
        <always_on>1</always_on>
        <update_rate>50</update_rate>
        <contact><collision>hull_collision</collision></contact>
      </sensor>
""" if CONTACT_SENSORS else ""
BARREL_SENSOR = """      <!-- 砲身が壁などに接触したかを検出する（評価の指標に使う） -->
      <sensor name="barrel_contact" type="contact">
        <always_on>1</always_on>
        <update_rate>50</update_rate>
        <contact><collision>barrel_collision</collision></contact>
      </sensor>
""" if CONTACT_SENSORS else ""

# 前方カメラ（CAMERA=1 で付ける。v2 の画像入力の試験用。既定は付けない）。解像度と周期は環境変数で変える
CAMERA = os.environ.get("CAMERA", "0") == "1"
CAMERA_W = int(os.environ.get("CAMERA_W", 160))
CAMERA_H = int(os.environ.get("CAMERA_H", 120))
CAMERA_HZ = int(os.environ.get("CAMERA_HZ", 10))
CAMERA_SENSOR = f"""      <!-- 前方カメラ：車体の前端の上面から、やや下向きに前を見る（地形の縁や斜面を見せる） -->
      <sensor name="front_camera" type="camera">
        <pose>{CH_L / 2 - 0.3:.2f} 0 {CH_H / 2 + 0.15:.2f} 0 0.20 0</pose>
        <always_on>1</always_on>
        <update_rate>{CAMERA_HZ}</update_rate>
        <topic>/camera/image</topic>
        <camera>
          <horizontal_fov>1.396</horizontal_fov>
          <image><width>{CAMERA_W}</width><height>{CAMERA_H}</height><format>R8G8B8</format></image>
          <clip><near>0.1</near><far>200</far></clip>
        </camera>
      </sensor>
""" if CAMERA else ""

# デバッグ用：車輪の関節状態も配信する（TANK_DEBUG_JOINTS=1）
DEBUG_JOINTS = ""

# ---- 派生値 ----
CH_Z = CLEARANCE + CH_H / 2            # 車体中心の地面からの高さ
AXLE_Z = WHEEL_R - CH_Z                # 車軸の車体中心からの相対高さ
WHEEL_Y = WHEEL_Y if WHEEL_Y is not None else CH_W / 2 + WHEEL_LEN / 2   # 車輪の左右位置
SEPARATION = 2 * WHEEL_Y               # DiffDrive に渡す左右輪の間隔
X0 = -WHEEL_PITCH * (N_WHEELS - 1) / 2


def box_inertia(m, x, y, z):
    return (m * (y * y + z * z) / 12, m * (x * x + z * z) / 12, m * (x * x + y * y) / 12)


def cyl_inertia(m, r, h):
    """軸方向 izz、軸に垂直な方向 ixx=iyy"""
    return (m * (3 * r * r + h * h) / 12, m * (3 * r * r + h * h) / 12, 0.5 * m * r * r)


def inertial(m, ixx, iyy, izz, pose="0 0 0 0 0 0"):
    return f"""<inertial>
        <pose>{pose}</pose>
        <mass>{m}</mass>
        <inertia><ixx>{ixx:.5f}</ixx><iyy>{iyy:.5f}</iyy><izz>{izz:.5f}</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>
      </inertial>"""


def color(r, g, b):
    return f"<material><ambient>{r} {g} {b} 1</ambient><diffuse>{r} {g} {b} 1</diffuse></material>"


def wheel(side, i, x):
    sign = 1 if side == "l" else -1
    ixx, iyy, izz = cyl_inertia(WHEEL_MASS, WHEEL_R, WHEEL_LEN)
    name = f"wheel_{side}{i}"
    link = f"""
    <link name="{name}">
      <pose>{x:.3f} {sign * WHEEL_Y:.3f} {AXLE_Z:.3f} {-math.pi / 2:.5f} 0 0</pose>
      {inertial(WHEEL_MASS, ixx, iyy, izz)}
      <collision name="collision">
        <geometry><cylinder><radius>{WHEEL_R}</radius><length>{WHEEL_LEN}</length></cylinder></geometry>
        <surface><friction><ode>
          <mu>{MU_LATERAL}</mu><mu2>{MU_ROLL}</mu2><fdir1>0 0 1</fdir1>
        </ode></friction></surface>
      </collision>
      <visual name="visual">
        <geometry><cylinder><radius>{WHEEL_R}</radius><length>{WHEEL_LEN}</length></cylinder></geometry>
        {color(0.15, 0.15, 0.15)}
      </visual>
    </link>
    <joint name="{name}_joint" type="revolute">
      <parent>base_link</parent>
      <child>{name}</child>
      <axis><xyz>0 0 1</xyz><limit><lower>-1e16</lower><upper>1e16</upper></limit></axis>
    </joint>"""
    return link


def main():
    global DEBUG_JOINTS
    if os.environ.get("TANK_DEBUG_JOINTS") == "1":
        DEBUG_JOINTS = "".join(f"\n      <joint_name>wheel_{sd}{i}_joint</joint_name>" for sd in ("l", "r") for i in range(N_WHEELS))
    dd_limits = "".join(f"\n      <{k}>{v}</{k}>" for k, v in (DD_LIMITS or {}).items())
    xs = [X0 + WHEEL_PITCH * i for i in range(N_WHEELS)]
    wheels = "".join(wheel(s, i, x) for s in ("l", "r") for i, x in enumerate(xs))
    left = "\n    ".join(f"<left_joint>wheel_l{i}_joint</left_joint>" for i in range(N_WHEELS))
    right = "\n    ".join(f"<right_joint>wheel_r{i}_joint</right_joint>" for i in range(N_WHEELS))

    cix, ciy, ciz = box_inertia(CH_MASS, CH_L, CH_W, CH_H)

    # 砲塔リンク（原点は砲塔の中心）。砲身の重心ぶん慣性中心を前にずらす。
    if TURRET_SHAPE == "cyl":
        tx, ty, tz = cyl_inertia(TURRET_MASS, TURRET_R, TURRET_H)
    else:
        tx, ty, tz = box_inertia(TURRET_MASS, *TURRET_SIZE)
    bx, by, bz = cyl_inertia(BARREL_MASS, BARREL_R, BARREL_LEN)  # 軸は砲身の長手方向
    barrel_cx = BARREL_X0 + BARREL_LEN / 2
    # 砲身は x 軸方向に寝ている: 長手(軸)まわり = bz、垂直まわり = bx
    m_tot = TURRET_MASS + BARREL_MASS
    com_x = BARREL_MASS * barrel_cx / m_tot
    ixx = tx + bz
    iyy = ty + by + BARREL_MASS * barrel_cx ** 2 - m_tot * com_x ** 2
    izz = tz + bx + BARREL_MASS * barrel_cx ** 2 - m_tot * com_x ** 2
    turret_z = CH_H / 2 + TURRET_H / 2
    if TURRET_SHAPE == "cyl":
        turret_geom = f"<cylinder><radius>{TURRET_R}</radius><length>{TURRET_H}</length></cylinder>"
    else:
        turret_geom = f"<box><size>{TURRET_SIZE[0]} {TURRET_SIZE[1]} {TURRET_SIZE[2]}</size></box>"

    print(f"""<?xml version="1.0"?>
<!-- gen_tank_model.py で生成。直接編集せず、スクリプトのパラメータを変更すること -->
<sdf version="1.8">
  <model name="tank">
    <link name="base_link">
      {inertial(CH_MASS, cix, ciy, ciz)}
      <collision name="hull_collision">
        <geometry><box><size>{CH_L} {CH_W} {CH_H}</size></box></geometry>
      </collision>
      <visual name="hull_visual">
        <geometry><box><size>{CH_L} {CH_W} {CH_H}</size></box></geometry>
        {color(0.30, 0.38, 0.22)}
      </visual>
      <!-- 履帯（見た目のみ。衝突判定は車輪が担当） -->
      <visual name="track_left">
        <pose>0 {WHEEL_Y:.3f} {AXLE_Z:.3f} 0 0 0</pose>
        <geometry><box><size>{WHEEL_PITCH * (N_WHEELS - 1) + 2 * WHEEL_R + 0.05:.3f} {WHEEL_LEN + 0.02:.3f} {2 * WHEEL_R + 0.02:.3f}</size></box></geometry>
        {color(0.10, 0.10, 0.10)}
      </visual>
      <visual name="track_right">
        <pose>0 {-WHEEL_Y:.3f} {AXLE_Z:.3f} 0 0 0</pose>
        <geometry><box><size>{WHEEL_PITCH * (N_WHEELS - 1) + 2 * WHEEL_R + 0.05:.3f} {WHEEL_LEN + 0.02:.3f} {2 * WHEEL_R + 0.02:.3f}</size></box></geometry>
        {color(0.10, 0.10, 0.10)}
      </visual>
{HULL_SENSOR}{CAMERA_SENSOR}      <sensor name="imu_sensor" type="imu">
        <always_on>1</always_on>
        <update_rate>50</update_rate>
        <topic>/imu</topic>
        <imu>
          <angular_velocity><x><noise type="none"/></x><y><noise type="none"/></y><z><noise type="none"/></z></angular_velocity>
          <linear_acceleration><x><noise type="none"/></x><y><noise type="none"/></y><z><noise type="none"/></z></linear_acceleration>
        </imu>
      </sensor>
    </link>
{wheels}
    <link name="turret">
      <pose>{TURRET_X:g} 0 {turret_z:.3f} 0 0 0</pose>
      {inertial(m_tot, ixx, iyy, izz, pose=f"{com_x:.4f} 0 0 0 0 0")}
      <collision name="turret_collision">
        <geometry>{turret_geom}</geometry>
      </collision>
      <visual name="turret_visual">
        <geometry>{turret_geom}</geometry>
        {color(0.35, 0.43, 0.25)}
      </visual>
      <!-- 砲身: 壁との接触を再現するため衝突判定を付ける -->
      <collision name="barrel_collision">
        <pose>{barrel_cx:.3f} 0 {BARREL_Z:g} 0 {math.pi / 2:.5f} 0</pose>
        <geometry><cylinder><radius>{BARREL_R}</radius><length>{BARREL_LEN}</length></cylinder></geometry>
      </collision>
{BARREL_SENSOR}      <visual name="barrel_visual">
        <pose>{barrel_cx:.3f} 0 {BARREL_Z:g} 0 {math.pi / 2:.5f} 0</pose>
        <geometry><cylinder><radius>{BARREL_R}</radius><length>{BARREL_LEN}</length></cylinder></geometry>
        {color(0.20, 0.20, 0.20)}
      </visual>
    </link>
    <joint name="turret_joint" type="revolute">
      <parent>base_link</parent>
      <child>turret</child>
      <axis>
        <xyz>0 0 1</xyz>
        <limit><lower>-3.1416</lower><upper>3.1416</upper></limit>
        <dynamics><damping>{TURRET_DAMPING}</damping></dynamics>
      </axis>
    </joint>

    <plugin filename="ignition-gazebo-diff-drive-system" name="ignition::gazebo::systems::DiffDrive">
    {left}
    {right}
      <wheel_separation>{SEPARATION:.3f}</wheel_separation>
      <wheel_radius>{WHEEL_R}</wheel_radius>
      <topic>/cmd_vel</topic>
      <odom_topic>/odom</odom_topic>
      <tf_topic>/tank_tf</tf_topic>
      <frame_id>odom</frame_id>
      <child_frame_id>base_link</child_frame_id>
      <odom_publish_frequency>50</odom_publish_frequency>{dd_limits}
    </plugin>
    <plugin filename="ignition-gazebo-joint-position-controller-system" name="ignition::gazebo::systems::JointPositionController">
      <joint_name>turret_joint</joint_name>
      <topic>/tank/turret_cmd</topic>
      <p_gain>{TURRET_P}</p_gain>
      <i_gain>0</i_gain>
      <d_gain>{TURRET_D}</d_gain>
      <cmd_max>{TURRET_CMD_MAX}</cmd_max>
      <cmd_min>-{TURRET_CMD_MAX}</cmd_min>
    </plugin>
    <plugin filename="ignition-gazebo-joint-state-publisher-system" name="ignition::gazebo::systems::JointStatePublisher">
      <topic>/joint_states</topic>
      <joint_name>turret_joint</joint_name>{DEBUG_JOINTS}
    </plugin>
    <!-- 真値の位置姿勢（world 座標、z を含む 3 次元）。DiffDrive の /odom は車輪の積分で滑りを含むため別に出す -->
    <plugin filename="ignition-gazebo-odometry-publisher-system" name="ignition::gazebo::systems::OdometryPublisher">
      <odom_frame>world</odom_frame>
      <robot_base_frame>base_link</robot_base_frame>
      <odom_topic>/odom_gt</odom_topic>
      <tf_topic>/odom_gt_tf</tf_topic>
      <odom_publish_frequency>50</odom_publish_frequency>
      <dimensions>3</dimensions>
    </plugin>
  </model>
</sdf>""")


if __name__ == "__main__":
    main()
