#!/usr/bin/env python3
"""学習データ上で、方策の予測と正解（GT）を比べて図に保存する。

使い方（pai_training の pixi 環境で実行する）:
    pixi run python /workspace/learning/debug_policy_tank.py \
        --episodes 0 5 --out /workspace/docs/debug_policy_berm.png

各エピソードを先頭から 1 フレームずつ方策に入力し（実機と同じく、行動チャンクのキューを使う）、
スロットルなどの予測と、デモの行動（GT）を重ねて描く。ピッチも併せて描き、
「ピッチの変化に応じてスロットルを変えられているか」を目で確認できるようにする。
"""
import argparse

import matplotlib
import numpy as np
import torch
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
from lerobot.common.policies.act.modeling_act import ACTPolicy

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="/workspace/dataset/lerobot_dataset/tank_berm")
    ap.add_argument("--repo-id", default="tank_berm")
    ap.add_argument("--policy-path", default="/workspace/checkpoints/train/tank_berm_act")
    ap.add_argument("--episodes", type=int, nargs="+", default=[0])
    ap.add_argument("--out", default="/workspace/docs/debug_policy_berm.png")
    args = ap.parse_args()

    dataset = LeRobotDataset(args.repo_id, root=args.dataset_root)
    policy = ACTPolicy.from_pretrained(args.policy_path)
    policy.eval()
    fps = dataset.fps

    fig, axes = plt.subplots(len(args.episodes), 2, figsize=(13, 3.6 * len(args.episodes)), squeeze=False)
    for row, ep in enumerate(args.episodes):
        lo = dataset.episode_data_index["from"][ep].item()
        hi = dataset.episode_data_index["to"][ep].item()
        policy.reset()
        pred, gt, pitch = [], [], []
        for i in range(lo, hi):
            sample = dataset[i]
            s = sample["observation.state"].float().unsqueeze(0)
            with torch.no_grad():
                a = policy.select_action({"observation.state": s, "observation.environment_state": s})
            pred.append(a.squeeze(0).numpy())
            gt.append(sample["action"].float().numpy())
            pitch.append(np.degrees(sample["observation.state"][2].item()))
        pred, gt = np.array(pred), np.array(gt)
        t = np.arange(len(pred)) / fps
        err = np.abs(pred - gt).mean(axis=0)
        print(f"ep{ep}: 平均絶対誤差 throttle={err[0]:.3f} steering={err[1]:.3f} turret={err[2]:.3f}")

        ax = axes[row, 0]
        ax.plot(t, gt[:, 0], "--", color="tab:red", label="GT throttle")
        ax.plot(t, pred[:, 0], color="tab:green", label="predicted throttle")
        ax.set_title(f"episode {ep}: throttle (MAE {err[0]:.3f})")
        ax.set_xlabel("time [s]")
        ax.grid(alpha=0.3)
        ax.legend(loc="upper right")
        ax = axes[row, 1]
        ax.plot(t, pitch, color="tab:blue")
        ax.set_title(f"episode {ep}: pitch [deg] (nose up = +)")
        ax.set_xlabel("time [s]")
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out, dpi=90)
    print(f"保存しました: {args.out}")


if __name__ == "__main__":
    main()
