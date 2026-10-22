"""装軌車両の LeRobotDataset の特徴量定義（変換スクリプトと学習スクリプトが読む）"""

STATE_NAMES = ["x", "z", "pitch", "v_forward", "turret_angle"]
ACTION_NAMES = ["throttle", "steering", "turret_angle"]

features = {
    # 観測：[x, z, pitch, v_forward, turret_angle]（/tank/state と同じ並び）
    "observation.state": {
        "dtype": "float32",
        "shape": (5,),
        "names": STATE_NAMES,
    },
    # カメラを使わないため、ACT の入力として environment_state にも同じ値を入れる
    "observation.environment_state": {
        "dtype": "float32",
        "shape": (5,),
        "names": STATE_NAMES,
    },
    # 行動：[throttle, steering, turret_angle]（/tank/command と同じ並び）
    "action": {
        "dtype": "float32",
        "shape": (3,),
        "names": ACTION_NAMES,
    },
}

# 変換に使う情報
robot_type = "tracked_vehicle"
repo_id = "tank_ditch"
root = "/workspace/dataset/lerobot_dataset/tank_ditch"
task_name = "ditch"
