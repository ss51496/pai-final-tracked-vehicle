#!/usr/bin/env python3
"""動画用の BGM を合成する（著作権の問題がないように、既存の曲は使わず、プログラムで作る）。
128 BPM、コード進行 Am–F–C–G。キック、スネア、ハイハット、ベース、アルペジオ、パッドを重ねる。
使い方:  python3 scripts/make_music.py <出力 wav> [秒数]
"""
import sys
import wave

import numpy as np

SR = 44100
BPM = 128
BEAT = 60.0 / BPM
dur = float(sys.argv[2]) if len(sys.argv) > 2 else 140.0
n = int(SR * dur)
t = np.arange(n) / SR
rng = np.random.default_rng(1)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(length, a=0.005, d=0.1, s=0.0):
    x = np.arange(length) / SR
    return np.minimum(x / a, 1.0) * (s + (1 - s) * np.exp(-x / d))


def add(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


# 音色
def kick():
    x = np.arange(int(SR * 0.28)) / SR
    f = 50 + 110 * np.exp(-x * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 11)


def snare():
    x = np.arange(int(SR * 0.22)) / SR
    return (rng.standard_normal(len(x)) * 0.7 + np.sin(2 * np.pi * 190 * x) * 0.5) * np.exp(-x * 20)


def hat(open_=False):
    x = np.arange(int(SR * (0.18 if open_ else 0.05))) / SR
    nz = rng.standard_normal(len(x))
    nz = nz - np.concatenate([[0], nz[:-1]]) * 0.95       # 高域を強調
    return nz * np.exp(-x * (18 if open_ else 70))


def saw(freq, length, detune=0.004):
    x = np.arange(length) / SR
    s = np.zeros(length)
    for dt in (-detune, 0.0, detune):
        s += 2 * ((x * freq * (1 + dt)) % 1.0) - 1
    return s / 3


def square(freq, length):
    x = np.arange(length) / SR
    return np.sign(np.sin(2 * np.pi * freq * x)) * 0.6


def lowpass(x, k=0.25):
    y = np.zeros_like(x)
    a = 0.0
    for i in range(len(x)):
        a += k * (x[i] - a)
        y[i] = a
    return y


# コード進行（1 小節ずつ）: ルート（ベース）、コード構成音（MIDI）
prog = [(45, [57, 60, 64]), (41, [53, 57, 60]), (48, [55, 60, 64]), (43, [55, 59, 62])]   # Am F C G
bars = int(dur / (BEAT * 4)) + 1
K, S, H, HO = kick(), snare(), hat(), hat(True)
drums = np.zeros(n)
bass = np.zeros(n)
arp = np.zeros(n)
pad = np.zeros(n)
for b in range(bars):
    t0 = b * BEAT * 4
    root, chord = prog[b % 4]
    section = min(b // 8, 3)                      # 8 小節ごとに盛り上げる
    has_drums = b >= 2
    if has_drums:
        for beat in range(4):
            add(drums, t0 + beat * BEAT, K, 0.9)                           # 4 つ打ち
            if beat in (1, 3):
                add(drums, t0 + beat * BEAT, S, 0.55)
            add(drums, t0 + (beat + 0.5) * BEAT, HO if beat % 2 == 1 else H, 0.22)
            if section >= 2:
                add(drums, t0 + (beat + 0.25) * BEAT, H, 0.1)
                add(drums, t0 + (beat + 0.75) * BEAT, H, 0.1)
    # ベース（8 分音符、2 拍目と 4 拍目の裏でオクターブ上）
    if b >= 1:
        for e in range(8):
            f = midi(root - 12 + (12 if e in (3, 7) else 0))
            ln = int(SR * BEAT * 0.5)
            add(bass, t0 + e * BEAT * 0.5, square(f, ln) * env(ln, 0.004, 0.18, 0.25), 0.34)
    # アルペジオ（16 分音符）
    if b >= 4:
        pat = [0, 1, 2, 1, 0, 1, 2, 1, 0, 2, 1, 2, 0, 1, 2, 1] if section < 3 else [0, 1, 2, 2 + 1, 2, 1, 0, 1, 2, 1, 2, 3, 2, 1, 0, 1]
        for s16 in range(16):
            m = chord[pat[s16] % 3] + (12 if pat[s16] >= 3 else 0) + 12
            ln = int(SR * BEAT * 0.25)
            add(arp, t0 + s16 * BEAT * 0.25, saw(midi(m), ln) * env(ln, 0.003, 0.09, 0.1), 0.24 if section < 2 else 0.3)
    # パッド（小節ごとの和音。8 小節目以降に入れる）
    if b >= 8:
        ln = int(SR * BEAT * 4)
        p = sum(saw(midi(m), ln, 0.006) for m in chord) / 3
        add(pad, t0, lowpass(p, 0.12) * np.minimum(np.arange(ln) / (SR * 0.4), 1.0) * 0.5, 0.35)

mix = drums + bass + arp + pad
# サイドチェイン風：キックのたびに、ベース・パッドを少し下げる
duck = np.ones(n)
for b in range(bars):
    for beat in range(4):
        i = int((b * 4 + beat) * BEAT * SR)
        if i < n:
            m = min(n, i + int(SR * 0.18))
            duck[i:m] = np.minimum(duck[i:m], np.linspace(0.45, 1.0, m - i))
mix = drums + (bass + pad) * duck + arp
# ステレオ（アルペジオを少し左右に振る）、フェード
left = mix + np.roll(arp, int(SR * 0.012)) * 0.25
right = mix + np.roll(arp, int(SR * 0.024)) * 0.25
fade_in, fade_out = int(SR * 1.5), int(SR * 4.0)
g = np.ones(n)
g[:fade_in] = np.linspace(0, 1, fade_in)
g[-fade_out:] = np.linspace(1, 0, fade_out)
st = np.stack([left, right], axis=1) * g[:, None]
st = st / (np.max(np.abs(st)) + 1e-9) * 0.8
pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("saved", sys.argv[1], f"{dur:.0f}s")
