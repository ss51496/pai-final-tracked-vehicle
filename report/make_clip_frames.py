#!/usr/bin/env python3
"""動画のクリップから 4 コマを切り出して 2×2 に並べる（レポートの図用）。
使い方（コンテナ内）: python3 report/make_clip_frames.py <場面名> <割合1,割合2,割合3,割合4>
割合は、クリップの長さに対する位置（0〜1）。出力: docs/clip_<場面名>.png"""
import subprocess
import sys

name, fr = sys.argv[1], [float(v) for v in sys.argv[2].split(",")]
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"videos/{name}.mp4"]))
for i, f in enumerate(fr):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{dur * f:.2f}", "-i", f"videos/{name}.mp4", "-frames:v", "1", f"/tmp/{name}_{i}.png"], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + sum([["-i", f"/tmp/{name}_{i}.png"] for i in range(4)], [])
               + ["-filter_complex", "[0][1]hstack[a];[2][3]hstack[b];[a][b]vstack,scale=1280:-1", f"docs/clip_{name}.png"], check=True)
print("saved", f"docs/clip_{name}.png", round(dur, 1))
