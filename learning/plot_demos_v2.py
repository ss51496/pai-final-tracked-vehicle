#!/usr/bin/env python3
"""v2 の突堤のデモ（8 次元の観測と行動）をエピソードごとに重ねて図にし、要約を表示する。

使い方（pai_training の pixi 環境で実行する）:
    pixi run python /workspace/learning/plot_demos_v2.py \
        --root /workspace/dataset/lerobot_dataset/tank_v2_berm --out /workspace/docs/v2_berm_demo.png
観測の並び: x, z, pitch, v_forward, turret_angle, vz, roll, throttle_cmd
"""
import argparse
import glob

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BERM = (100.0, 117.6)    # 既定：山の範囲 x [m]（gen_berm.py の v2 の値）。壕は --span 100 111

ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--span", type=float, nargs=2, default=None, help="山または壕の範囲 x [m]")
args = ap.parse_args()
if args.span:
    BERM = tuple(args.span)

files = sorted(glob.glob(args.root + "/data/chunk-000/episode_*.parquet"))
fig, ax = plt.subplots(2, 3, figsize=(18, 9))
cm = plt.get_cmap("tab10")
for i, f in enumerate(files):
    d = pd.read_parquet(f)
    s = np.stack(d["observation.state"].to_numpy())
    a = np.stack(d["action"].to_numpy())
    c = cm(i % 10)
    ax[0, 0].plot(s[:, 0], a[:, 0], color=c, label=f"ep{i}")      # スロットル vs x
    ax[0, 1].plot(s[:, 0], s[:, 3] * 3.6, color=c)                # 速度 [km/h] vs x
    ax[0, 2].plot(s[:, 0], s[:, 1], color=c)                      # 高さ vs x
    ax[1, 0].plot(s[:, 0], s[:, 5], color=c)                      # 鉛直速度 vs x
    ax[1, 1].plot(s[:, 0], np.degrees(s[:, 2]), color=c)          # ピッチ vs x
    ax[1, 2].plot(np.arange(len(d)) / 10, a[:, 0], color=c)               # スロットル vs 時間
titles = ["throttle vs x", "speed [km/h] vs x", "z [m] vs x", "vz [m/s] vs x", "pitch [deg] vs x", "throttle vs time [s]"]
for a_, t_ in zip(ax.flat, titles):
    a_.set_title(t_)
    a_.grid(alpha=0.3)
for a_ in ax.flat[:5]:
    a_.axvspan(*BERM, color="orange", alpha=0.12)
ax[0, 0].legend(ncol=2, fontsize=8)
plt.tight_layout()
plt.savefig(args.out, dpi=80)

print("ep: フレーム 所要s | 最高速度 山での最低速度 山に入る速度 | 着地衝撃（0.1 秒の vz の変化の最大）| 最終x")
for i, f in enumerate(files):
    d = pd.read_parquet(f)
    s = np.stack(d["observation.state"].to_numpy())
    a = np.stack(d["action"].to_numpy())
    on = (s[:, 0] >= BERM[0]) & (s[:, 0] <= BERM[1])
    vz = s[:, 5]
    dv = float(np.max(vz[1:] - vz[:-1])) if len(vz) > 1 else 0.0   # 0.1 秒刻みの変化
    enter = s[np.argmax(s[:, 0] >= BERM[0]), 3] * 3.6 if (s[:, 0] >= BERM[0]).any() else float("nan")
    print(f"ep{i}: {len(d)}フレーム {len(d)/10:.1f}s | 最高 {s[:,3].max()*3.6:.0f} km/h  山で最低 {s[on,3].min()*3.6 if on.any() else float('nan'):.0f} km/h  "
          f"進入 {enter:.0f} km/h | 衝撃 {dv:.1f} m/s | 最終x={s[-1,0]:.1f}")
