#!/usr/bin/env python3
"""学習ログ（`step: N loss: X` の行）から loss の推移を図にする。

使い方（pai_training の pixi 環境で実行する）:
    pixi run python /workspace/learning/plot_loss.py /workspace/logs/train_berm.log /workspace/logs/loss.png
"""
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

log, out = sys.argv[1], sys.argv[2]
steps, losses = [], []
for line in open(log, errors="ignore"):
    m = re.match(r"step: (\d+) loss: ([0-9.]+)", line)
    if m:
        steps.append(int(m.group(1)))
        losses.append(float(m.group(2)))
steps, losses = np.array(steps), np.array(losses)

fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(steps, losses, color="tab:blue", alpha=0.35, label="loss (every 50 steps)")
w = min(10, len(losses))
if w > 1:
    smooth = np.convolve(losses, np.ones(w) / w, mode="valid")
    ax.plot(steps[w - 1:], smooth, color="tab:blue", linewidth=2, label=f"moving average ({w} pts)")
ax.set_xlabel("training step")
ax.set_ylabel("loss")
ax.set_yscale("log")
ax.set_title("ACT training loss (tank_berm)")
ax.grid(alpha=0.3, which="both")
ax.legend()
fig.tight_layout()
fig.savefig(out, dpi=100)
print(f"{len(steps)} 点, 最初 {losses[0]:.3f} → 最後 {losses[-1]:.3f}, 最小 {losses.min():.3f} -> {out}")
