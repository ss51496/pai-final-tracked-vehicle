"""v2（44 t 級の車両）の LeRobotDataset の特徴量定義。観測は 8 次元（rosbag の /tank/state と同じ並び）。

環境変数で切り替える（変換と学習の両方で同じ値にすること）:
  TANK_TASK=berm|ditch   タスク（データセットの名前と置き場が変わる）。既定 berm
  TANK_STATE_CMD=1|0     観測に throttle_cmd（直前のスロットル指令）を含めるか。既定 1。
                         0 にすると 7 次元になる。throttle_cmd は行動の写しなので、方策が「前回の指令をそのまま出す」
                         近道を覚えるおそれがある。含めた場合と含めない場合を比べて決める（比較実験用）
"""
import os

TASK = os.environ.get("TANK_TASK", "berm")
USE_CMD = os.environ.get("TANK_STATE_CMD", "1") == "1"

ALL_STATE_NAMES = ["x", "z", "pitch", "v_forward", "turret_angle", "vz", "roll", "throttle_cmd"]
STATE_DIMS = list(range(8)) if USE_CMD else list(range(7))     # 記録した 8 次元のうち学習に使う添字
IMG = TASK.endswith("_img")      # 前方カメラの画像を入力に加える（TANK_TASK=ditch_t90_img など）
if "_t90" in TASK:
    # 砲塔を一定（90°）にそろえた学習では、観測から砲塔角を外す。一定値の次元は標準偏差が 0 になり、正規化で
    # 実際の角度のわずかなずれ（走行中は 91°）が極端な入力になって、方策が壊れた
    STATE_DIMS.remove(4)
STATE_NAMES = [ALL_STATE_NAMES[i] for i in STATE_DIMS]
ACTION_NAMES = ["throttle", "steering", "turret_angle"]
n = len(STATE_NAMES)

features = {
    "observation.state": {"dtype": "float32", "shape": (n,), "names": STATE_NAMES},
    # カメラを使わないため、ACT の入力として environment_state にも同じ値を入れる
    "observation.environment_state": {"dtype": "float32", "shape": (n,), "names": STATE_NAMES},
    "action": {"dtype": "float32", "shape": (3,), "names": ACTION_NAMES},
}
if IMG:
    # 前方カメラ（160×120、rgb8）。ACT は画像を ResNet で特徴量にして使う
    features["observation.images.front"] = {"dtype": "image", "shape": (120, 160, 3), "names": ["height", "width", "channel"]}

robot_type = "tracked_vehicle_v2"
suffix = "" if USE_CMD else "_nocmd"
repo_id = f"tank_v2_{TASK}{suffix}"
root = f"/workspace/dataset/lerobot_dataset/{repo_id}"
task_name = TASK
