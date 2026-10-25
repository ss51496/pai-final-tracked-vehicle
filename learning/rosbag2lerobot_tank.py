#!/usr/bin/env python3
"""rosbag2（/tank/state と /tank/command）を LeRobotDataset に変換する。

使い方（pai_training の pixi 環境で実行する）:
    cd /workspace/pai_training
    pixi run python /workspace/learning/rosbag2lerobot_tank.py \
        --config /workspace/learning/conversion_config.yaml

変換の流れ:
  1. bag_dir 以下の .db3 を持つフォルダを 1 エピソードとして集める
  2. state と action のメッセージを時刻つきで読み出す
  3. 両方が存在する区間を fps の等間隔で区切り、直前の値を保持して再サンプルする
  4. 1 フレームずつ LeRobotDataset に追加し、エピソードごとに保存する

操縦を始める前と終えた後の停止区間は切り詰める（trim_idle）。始める前の観測は毎回同じ（x=0、速度 0）なのに
動き出す時刻は毎回違うため、そのまま学習すると「止まったまま」と出力して動き出せなくなる。

講義のスクリプトとの違い: 全エピソードを最長に合わせて最後のフレームで延ばさない。
延ばすと「通過後に止まり続ける区間」が長く学習データに入ってしまうため。
ACT は行動チャンクが終端を越える部分を action_is_pad として扱えるので、延ばさなくてよい。
"""
import argparse
import importlib.util
import shutil
from pathlib import Path

import numpy as np
import torch
import yaml
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
from rosbags.rosbag2 import Reader
from rosbags.serde import deserialize_cdr


def load_module(path):
    spec = importlib.util.spec_from_file_location("tank_features", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_topic(episode_dir, topic, dim):
    """トピックの (時刻 [ns], 値 (N, dim)) を返す"""
    times, values = [], []
    with Reader(episode_dir) as reader:
        conns = [c for c in reader.connections if c.topic == topic]
        if not conns:
            raise RuntimeError(f"{episode_dir} に {topic} がありません")
        for conn, t, raw in reader.messages(connections=conns):
            msg = deserialize_cdr(raw, conn.msgtype)
            data = np.asarray(msg.data, dtype=np.float32)
            if data.shape[0] != dim:
                raise RuntimeError(f"{topic} の次元が {data.shape[0]}（期待は {dim}）")
            times.append(t)
            values.append(data)
    return np.asarray(times, dtype=np.int64), np.stack(values)


def sample_and_hold(times, values, target_times):
    """各 target_time 以前で最も新しい値を取る（それより前なら最初の値）"""
    idx = np.searchsorted(times, target_times, side="right") - 1
    return values[np.clip(idx, 0, len(times) - 1)]


def trim_idle(action, fps, tail_sec):
    """行動が最初に変わった位置から、最後に変わった位置の tail_sec 秒後までを残す範囲 (start, end) を返す"""
    moving = np.abs(action - action[0]).max(axis=1) > 1e-3
    if not moving.any():
        return 0, len(action) - 1
    first = int(np.argmax(moving))
    last = len(moving) - 1 - int(np.argmax(moving[::-1]))
    return first, min(len(action) - 1, last + int(tail_sec * fps))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="/workspace/learning/conversion_config.yaml")
    ap.add_argument("--overwrite", action="store_true", help="出力先が既にあれば確認なしで消して作り直す")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    feat = load_module(cfg["features_file"])
    fps = int(cfg["fps"])
    out_dir = Path(cfg["output_dir"]) if "output_dir" in cfg else Path(feat.root)   # v2 は特徴量定義の root（TANK_STATE_CMD で変わる）
    state_dim = feat.features["observation.state"]["shape"][0]
    action_dim = feat.features["action"]["shape"][0]

    episodes = sorted(p.parent for p in Path(cfg["bag_dir"]).rglob("*.db3"))
    if not episodes:
        raise FileNotFoundError(f"{cfg['bag_dir']} に rosbag2 が見つかりません")
    print(f"{len(episodes)} エピソードを変換します（fps={fps}）")

    if out_dir.exists():
        if not args.overwrite and input(f"{out_dir} は既にあります。消して作り直しますか？ (y/N): ").strip().lower() != "y":
            raise SystemExit("中止しました")
        shutil.rmtree(out_dir)

    dataset = LeRobotDataset.create(
        repo_id=feat.repo_id, fps=fps, root=out_dir,
        robot_type=feat.robot_type, features=feat.features, use_videos=False)

    for i, ep in enumerate(episodes):
        s_t, s_v = read_topic(ep, cfg["state_topic"], int(cfg.get("state_topic_dim", state_dim)))
        a_t, a_v = read_topic(ep, cfg["action_topic"], action_dim)
        start, end = max(s_t[0], a_t[0]), min(s_t[-1], a_t[-1])
        n = int((end - start) * 1e-9 * fps) + 1
        target = start + (np.arange(n) / fps * 1e9).astype(np.int64)
        state = sample_and_hold(s_t, s_v, target)
        if hasattr(feat, "STATE_DIMS"):           # 記録した次元のうち、学習に使うものだけを取り出す（v2）
            state = np.ascontiguousarray(state[:, feat.STATE_DIMS])
        action = sample_and_hold(a_t, a_v, target)
        if "fix_turret_deg" in cfg:               # 砲塔を一定の角度にそろえる（観測の砲塔角 [4]、行動の砲塔角 [2] の両方）
            rad = np.radians(float(cfg["fix_turret_deg"]))
            state[:, 4] = rad
            action[:, 2] = rad

        n_raw = n
        if cfg.get("trim_idle", False):
            lo, hi = trim_idle(action, fps, float(cfg.get("trim_tail_sec", 1.0)))
            state, action = state[lo:hi + 1], action[lo:hi + 1]
            n = len(action)
        for k in range(n):
            dataset.add_frame({
                "observation.state": torch.from_numpy(state[k]),
                "observation.environment_state": torch.from_numpy(state[k]),
                "action": torch.from_numpy(action[k]),
                "task": feat.task_name,
            })
        dataset.save_episode()
        # 変換の健全性を確認するための要約（ピッチとスロットルの対応が見えるはず）
        print(f"[ep{i}] {ep.name}: {n} フレーム ({n / fps:.1f}s、切り詰め前 {n_raw})  "
              f"最大ピッチ={np.degrees(state[:, 2].max()):.1f}deg  最大z={state[:, 1].max():.2f}m  "
              f"スロットル最大={action[:, 0].max():.2f}  最小={action[:, 0].min():.2f}")

    print(f"データセットを保存しました: {dataset.root}  ({dataset.num_episodes} エピソード, {dataset.num_frames} フレーム)")


if __name__ == "__main__":
    main()
