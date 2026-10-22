#!/usr/bin/env python3
"""装軌車両（多輪スキッドステア）の model.sdf を生成する。

使い方:  python3 tools/gen_tank_model.py > models/tank/model.sdf                      # 砲身 1.3 m（突堤用）
         BARREL_LEN=2.0 python3 tools/gen_tank_model.py > models/tank_long/model.sdf   # 砲身 2.0 m（壕用）

履帯は見た目用の箱で、接地・駆動は片側 N 輪の車輪で行う。
パラメータは架空の値。慣性は形状と質量から計算する。
"""
import math
import os

# ---- 車体 ----
CH_L, CH_W, CH_H = 2.0, 1.0, 0.4      # 車体の長さ(x) 幅(y) 高さ(z) [m]
CH_MASS = 300.0                        # [kg]
CLEARANCE = 0.12                       # 地上高 [m]

# ---- 走行装置 ----
N_WHEELS = 7                           # 片側の車輪数
WHEEL_R = 0.15                         # 車輪半径 [m]
WHEEL_LEN = 0.14                       # 車輪の幅 [m]
WHEEL_MASS = 5.0                       # [kg]
WHEEL_PITCH = 0.30                     # 車輪の間隔 [m]
MU_ROLL = 1.2                          # 転がり方向の摩擦
MU_LATERAL = 0.5                       # 横方向の摩擦（小さいほど旋回しやすい）

# ---- 砲塔・砲身 ----
TURRET_R, TURRET_H, TURRET_MASS = 0.35, 0.18, 60.0
BARREL_R, BARREL_LEN, BARREL_MASS = 0.04, float(os.environ.get("BARREL_LEN", 1.3)), 15.0
BARREL_X0 = 0.20                       # 砲身の根元（砲塔中心から）

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

# ---- 派生値 ----
CH_Z = CLEARANCE + CH_H / 2            # 車体中心の地面からの高さ
AXLE_Z = WHEEL_R - CH_Z                # 車軸の車体中心からの相対高さ
WHEEL_Y = CH_W / 2 + WHEEL_LEN / 2     # 車輪の左右位置
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
    xs = [X0 + WHEEL_PITCH * i for i in range(N_WHEELS)]
    wheels = "".join(wheel(s, i, x) for s in ("l", "r") for i, x in enumerate(xs))
    left = "\n    ".join(f"<left_joint>wheel_l{i}_joint</left_joint>" for i in range(N_WHEELS))
    right = "\n    ".join(f"<right_joint>wheel_r{i}_joint</right_joint>" for i in range(N_WHEELS))

    cix, ciy, ciz = box_inertia(CH_MASS, CH_L, CH_W, CH_H)

    # 砲塔リンク（原点は砲塔円柱の中心）。砲身の重心ぶん慣性中心を前にずらす。
    tx, ty, tz = cyl_inertia(TURRET_MASS, TURRET_R, TURRET_H)
    bx, by, bz = cyl_inertia(BARREL_MASS, BARREL_R, BARREL_LEN)  # 軸は砲身の長手方向
    barrel_cx = BARREL_X0 + BARREL_LEN / 2
    # 砲身は x 軸方向に寝ている: 長手(軸)まわり = bz、垂直まわり = bx
    m_tot = TURRET_MASS + BARREL_MASS
    com_x = BARREL_MASS * barrel_cx / m_tot
    ixx = tx + bz
    iyy = ty + by + BARREL_MASS * barrel_cx ** 2 - m_tot * com_x ** 2
    izz = tz + bx + BARREL_MASS * barrel_cx ** 2 - m_tot * com_x ** 2
    turret_z = CH_H / 2 + TURRET_H / 2

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
{HULL_SENSOR}      <sensor name="imu_sensor" type="imu">
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
      <pose>0 0 {turret_z:.3f} 0 0 0</pose>
      {inertial(m_tot, ixx, iyy, izz, pose=f"{com_x:.4f} 0 0 0 0 0")}
      <collision name="turret_collision">
        <geometry><cylinder><radius>{TURRET_R}</radius><length>{TURRET_H}</length></cylinder></geometry>
      </collision>
      <visual name="turret_visual">
        <geometry><cylinder><radius>{TURRET_R}</radius><length>{TURRET_H}</length></cylinder></geometry>
        {color(0.35, 0.43, 0.25)}
      </visual>
      <!-- 砲身: 壁との接触を再現するため衝突判定を付ける -->
      <collision name="barrel_collision">
        <pose>{barrel_cx:.3f} 0 0 0 {math.pi / 2:.5f} 0</pose>
        <geometry><cylinder><radius>{BARREL_R}</radius><length>{BARREL_LEN}</length></cylinder></geometry>
      </collision>
{BARREL_SENSOR}      <visual name="barrel_visual">
        <pose>{barrel_cx:.3f} 0 0 0 {math.pi / 2:.5f} 0</pose>
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
        <dynamics><damping>5</damping></dynamics>
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
      <odom_publish_frequency>50</odom_publish_frequency>
    </plugin>
    <plugin filename="ignition-gazebo-joint-position-controller-system" name="ignition::gazebo::systems::JointPositionController">
      <joint_name>turret_joint</joint_name>
      <topic>/tank/turret_cmd</topic>
      <p_gain>500</p_gain>
      <i_gain>0</i_gain>
      <d_gain>100</d_gain>
      <cmd_max>2000</cmd_max>
      <cmd_min>-2000</cmd_min>
    </plugin>
    <plugin filename="ignition-gazebo-joint-state-publisher-system" name="ignition::gazebo::systems::JointStatePublisher">
      <topic>/joint_states</topic>
      <joint_name>turret_joint</joint_name>
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
