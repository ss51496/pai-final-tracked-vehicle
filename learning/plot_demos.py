#!/usr/bin/env python3
"""LeRobotDataset のデモ（観測と行動）をエピソードごとに重ねて図にする。

使い方（pai_training の pixi 環境で実行する）:
    pixi run python /workspace/learning/plot_demos.py \
        --root /workspace/dataset/lerobot_dataset/tank_ditch --out /workspace/docs/ditch_demo.png
"""
import argparse
import glob

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True)
ap.add_argument("--out", required=True)
args = ap.parse_args()

files = sorted(glob.glob(args.root + "/data/chunk-000/episode_*.parquet"))
fig, ax = plt.subplots(2, 3, figsize=(18, 9))
cm = plt.get_cmap("tab10")
for i, f in enumerate(files):
    d = pd.read_parquet(f)
    s = np.stack(d["observation.state"].to_numpy())
    a = np.stack(d["action"].to_numpy())
    t = np.arange(len(d)) / 10
    c = cm(i % 10)
    ax[0, 0].plot(s[:, 0], a[:, 0], color=c, label=f"ep{i}")      # スロットル vs x
    ax[0, 1].plot(s[:, 0], s[:, 1], color=c)                      # 高さ vs x
    ax[0, 2].plot(s[:, 0], np.degrees(s[:, 2]), color=c)          # ピッチ vs x
    ax[1, 0].plot(t, a[:, 0], color=c)                            # スロットル vs 時間
    ax[1, 1].plot(t, np.degrees(a[:, 2]), color=c)                # 砲塔角の指令 vs 時間
    ax[1, 2].plot(s[:, 0], s[:, 3], color=c)                      # 速度 vs x
titles = ["throttle vs x", "z [m] vs x", "pitch [deg] vs x", "throttle vs time [s]", "turret command [deg] vs time [s]", "v_forward [m/s] vs x"]
for a_, t_ in zip(ax.flat, titles):
    a_.set_title(t_)
    a_.grid(alpha=0.3)
for a_ in (ax[0, 0], ax[0, 1], ax[0, 2], ax[1, 2]):
    a_.axvspan(6.0, 10.8, color="orange", alpha=0.12)   # 壕（x=6.0〜10.8 m）
ax[0, 0].legend(ncol=2, fontsize=8)
plt.tight_layout()
plt.savefig(args.out, dpi=80)
for i, f in enumerate(files):
    d = pd.read_parquet(f)
    s = np.stack(d["observation.state"].to_numpy())
    a = np.stack(d["action"].to_numpy())
    thr = a[:, 0]
    tur = np.degrees(a[:, 2])
    t_turn = np.argmax(np.abs(tur) > 45) / 10 if (np.abs(tur) > 45).any() else float("nan")
    print(f"ep{i}: {len(d)}フレーム ({len(d)/10:.1f}s) x:{s[0,0]:.1f}->{s[-1,0]:.1f}  砲塔90°到達の指令 t={t_turn:.1f}s  "
          f"最大スロットル={thr.max():.2f}  最小z={s[:,1].min():.2f} 最大z={s[:,1].max():.2f}  最大|steer|={np.abs(a[:,1]).max():.2f}")
