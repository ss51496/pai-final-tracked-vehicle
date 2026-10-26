#!/usr/bin/env python3
"""v2 の結果を「所要時間」と「着地衝撃」の散布図にする（左：突堤、右：壕）。左下ほど「速くて、衝撃が小さい」。

使い方（pai_training の pixi 環境で実行する）:
    pixi run python /workspace/report/plot_results_v2.py /workspace/docs/v2_results.png
"""
import csv
import os
import statistics as st
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f or "NotoSerifCJK" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["Noto Sans CJK JP", "DejaVu Sans"]

R = "/workspace/results/"


def rows(name):
    with open(R + name + ".csv") as f:
        return list(csv.DictReader(f))


def stat(name, impact_key):
    d = [r for r in rows(name) if r.get("outcome", "passed") == "passed" and r.get("reached", "True") != "False"]
    t = st.mean(float(r["time_sec"]) for r in d)
    if impact_key == "impact":
        im = st.mean(float(r["impact"]) for r in d)
    else:   # 壕：入るときと出るときのうち、大きい方の平均
        im = st.mean(max(float(r["impact_in"]), float(r["impact_out"])) for r in d)
    return t, im


berm = [("全開", "v2_berm_const_1.0", "rule"), ("一定 0.5", "v2_berm_const_0.5", "rule"), ("一定 0.25", "v2_berm_const_0.25", "rule"),
        ("一定 0.15", "v2_berm_const_0.15", "rule"), ("ACT（8 次元）", "v2_berm_policy_cmd_n8", "act"), ("ACT（7 次元）", "v2_berm_policy_nocmd_n8", "act")]
ditch = [("人のデモの再生", "v2_ditch_human_replay2", "human"), ("全開", "v2_ditch_full", "rule"), ("一定 0.15", "v2_ditch_const015", "rule"),
         ("減速ゾーン", "v2_ditch_slowzone", "rule"), ("ACT（数値）", "v2_ditch_policy_t90nocmd_n8_new", "act"),
         ("ACT（数値＋画像）", "v2_ditch_policy_t90imgnocmd_n8_new", "act")]
col = {"rule": "tab:gray", "human": "tab:blue", "act": "tab:red"}
fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
for a, data, key, title in ((ax[0], berm, "impact", "突堤（x=0〜125 m）"), (ax[1], ditch, "both", "壕（x=0〜135 m）")):
    for label, name, kind in data:
        t, im = stat(name, key)
        a.scatter(t, im, s=90, color=col[kind], zorder=3)
        a.annotate(label, (t, im), textcoords="offset points", xytext=(6, 5), fontsize=9)
    a.axhline(3.0, color="tab:orange", linestyle="--", linewidth=1.2)
    a.text(a.get_xlim()[1], 3.05, "基準 3.0 m/s", ha="right", va="bottom", color="tab:orange", fontsize=9)
    a.set_title(title)
    a.set_xlabel("所要時間 [s]（小さいほど速い）")
    a.set_ylabel("着地衝撃 [m/s]（小さいほど良い）")
    a.grid(alpha=0.3)
    a.set_ylim(bottom=0)
plt.tight_layout()
plt.savefig(sys.argv[1], dpi=110)
print("saved", sys.argv[1])
