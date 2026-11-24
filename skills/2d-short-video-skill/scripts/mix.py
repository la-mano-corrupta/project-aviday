#!/usr/bin/env python3
"""Procedural philosophy short soundtrack: narration + tactile 2D SFX + warm ambient bed (48 kHz stereo).

Reads data/cues.json, data/narration.wav (optional), and script.json ("music": "bed" | "none" | path).
Supports SFX types: ink, chalk, page, whoosh, pop, thud, slam, chime, tick, heartbeat.

Usage:
  scripts/py scripts/mix.py [project_dir=.]
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

P = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SR = 48000
rng = np.random.default_rng(42)

cj = json.loads((P / "data/cues.json").read_text(encoding="utf-8"))
script = json.loads((P / "script.json").read_text(encoding="utf-8"))
DUR = float(cj["duration"])
N = int(DUR * SR) + SR // 10


def lp(x, f, o=2):
    b, a = signal.butter(o, min(f, SR / 2 - 100) / (SR / 2), "low")
    return signal.lfilter(b, a, x)


def bp(x, f0, f1, o=2):
    b, a = signal.butter(o, [f0 / (SR / 2), min(f1, SR / 2 - 100) / (SR / 2)], "band")
    return signal.lfilter(b, a, x)


def db(x):
    return 10 ** (x / 20)


def tt(d):
    return np.arange(int(d * SR)) / SR


def env(n, a=0.005, r=5.0):
    e = np.ones(n)
    na = max(1, min(n, int(a * SR)))
    e[:na] = np.linspace(0, 1, na)
    rest = n - na
    if rest > 0:
        e[na:] = np.exp(-np.linspace(0, r, rest))
    return e


def sweep(f0, f1, d):
    t = tt(d)
    f = f0 * (f1 / max(1.0, f0)) ** (t / max(1e-4, d))
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def noise(d):
    return rng.standard_normal(int(d * SR))


# ---------- tactile 2D SFX ----------
def whoosh(d=0.36, **_):
    n = noise(d)
    lo, hi = lp(n, 420), lp(n, 1800)
    k = np.sin(np.pi * np.linspace(0, 1, len(n)))
    x = (lo * (1 - k) + hi * k) * (k ** 1.5)
    return x / (np.abs(x).max() + 1e-9) * 0.45


def page(d=0.28, **_):
    n = bp(noise(d), 600, 3200)
    k = np.sin(np.pi * np.linspace(0, 1, len(n))) ** 1.8
    return n / (np.abs(n).max() + 1e-9) * k * 0.38


def ink(d=0.22, **_):
    n = bp(noise(d), 900, 3400)
    mod = 0.55 + 0.45 * np.sin(2 * np.pi * 24 * tt(d))
    k = np.sin(np.pi * np.linspace(0, 1, len(n)))
    x = n * mod[: len(n)] * k
    return x / (np.abs(x).max() + 1e-9) * 0.32


def chalk(d=0.30, **_):
    return ink(d=d) * 0.9


def pop(**_):
    d = 0.11
    x = sweep(520, 220, d) * env(int(d * SR), 0.002, 6.0)
    return lp(x, 2600) * 0.65


def thud(**_):
    d = 0.35
    t = tt(d)
    x = np.sin(2 * np.pi * (68 + 38 * np.exp(-t * 28)) * t) * env(len(t), 0.002, 7.0)
    return x * 0.85 + lp(noise(d), 200) * env(len(t), 0.001, 11.0) * 0.25


def slam(**_):
    d = 0.45
    t = tt(d)
    x = np.sin(2 * np.pi * (56 + 55 * np.exp(-t * 24)) * t) * env(len(t), 0.002, 6.0)
    return np.tanh(1.5 * (x + lp(noise(d), 1000) * env(len(t), 0.001, 10.0) * 0.5)) * 0.85


def chime(d=1.2, **_):
    freqs = [523.25, 659.25, 783.99]
    x = np.zeros(int(d * SR))
    t = tt(d)
    for idx, f in enumerate(freqs):
        x += np.sin(2 * np.pi * f * t) * env(len(t), 0.01, 4.5 + idx) * (0.28 / (idx + 1))
    return lp(x, 3800)


def tick(**_):
    d = 0.08
    t = tt(d)
    return lp(np.sin(2 * np.pi * 410 * t) * env(len(t), 0.001, 10.0), 2200) * 0.32


def heartbeat(**_):
    one = lambda d, f: np.sin(2 * np.pi * f * tt(d)) * env(int(d * SR), 0.004, 7.0)
    x = np.concatenate([one(0.16, 58), np.zeros(int(0.09 * SR)), one(0.20, 52) * 0.75])
    return lp(x, 280) * 0.95


FX = {
    "whoosh": whoosh,
    "page": page,
    "ink": ink,
    "chalk": chalk,
    "pop": pop,
    "thud": thud,
    "slam": slam,
    "chime": chime,
    "tick": tick,
    "heartbeat": heartbeat,
}
LEVEL = {
    "whoosh": -17,
    "page": -17,
    "ink": -16,
    "chalk": -16,
    "pop": -14,
    "thud": -11,
    "slam": -9,
    "chime": -15,
    "tick": -18,
    "heartbeat": -9,
}


def build_ambient_bed() -> np.ndarray:
    """Warm contemplative ambient chord bed tailored for philosophy storytelling."""
    t = np.arange(N) / SR
    bar = 3.2
    prog = [
        (110.0, 164.81, 220.0, 261.63),  # Am7 feel
        (87.31, 130.81, 174.61, 220.0),  # Fmaj7 feel
        (98.00, 146.83, 196.00, 246.94), # G6 feel
        (82.41, 123.47, 164.81, 196.00), # Em7 feel
    ]
    bed_l = np.zeros(N)
    bed_r = np.zeros(N)
    for step in range(int(DUR / bar) + 2):
        chord = prog[step % len(prog)]
        st = int(step * bar * SR)
        seg_n = min(N - st, int((bar + 0.6) * SR))
        if seg_n <= 10:
            continue
        tt_seg = np.arange(seg_n) / SR
        fade = np.sin(np.pi * np.linspace(0, 1, seg_n)) ** 0.75
        chord_sig = np.zeros(seg_n)
        for j, freq in enumerate(chord):
            chord_sig += np.sin(2 * np.pi * freq * tt_seg + j * 0.4) * (0.28 / (j + 1))
        chord_sig *= fade
        bed_l[st : st + seg_n] += chord_sig * 0.95
        bed_r[st : st + seg_n] += np.roll(chord_sig, int(0.012 * SR)) * 0.95

    air = lp(noise(N / SR), 420) * 0.018
    bed = np.stack([lp(bed_l, 900) + air[:N], lp(bed_r, 900) + air[:N]], axis=1)
    fade_out = np.minimum(1.0, (N - np.arange(N)) / (0.8 * SR))[:, None]
    fade_in = np.minimum(1.0, np.arange(N) / (0.4 * SR))[:, None]
    return bed * fade_in * fade_out * db(-19)


def main() -> None:
    voice = np.zeros(N)
    narr_path = P / "data/narration.wav"
    if narr_path.exists():
        sr_n, raw_v = wavfile.read(narr_path)
        if raw_v.ndim > 1:
            raw_v = raw_v.mean(axis=1)
        v = raw_v.astype(np.float64) / 32768.0
        if sr_n != SR:
            v = signal.resample_poly(v, SR, sr_n)
        n = min(len(v), N)
        voice[:n] = v[:n]

    sfx = np.zeros((N, 2))
    for cue in cj.get("cues", []):
        fn = FX.get(cue.get("type"))
        if not fn:
            continue
        x = fn(d=float(cue.get("dur", 0.35)))
        st = max(0, int(float(cue.get("t", 0.0)) * SR))
        gain = db(LEVEL.get(cue["type"], -15) + float(cue.get("gain", 0.0)))
        pan = float(cue.get("pan", 0.0))
        gl, gr = gain * np.sqrt(0.5 * (1 - pan)), gain * np.sqrt(0.5 * (1 + pan))
        k = min(len(x), N - st)
        if k > 0:
            sfx[st : st + k, 0] += x[:k] * gl
            sfx[st : st + k, 1] += x[:k] * gr

    music_mode = script.get("music", "bed")
    if music_mode == "none":
        music = np.zeros((N, 2))
    elif music_mode == "bed":
        music = build_ambient_bed()
    else:
        track_path = Path(music_mode)
        if not track_path.is_absolute():
            track_path = P / music_mode
        raw_m = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(track_path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
            capture_output=True,
            check=True,
        ).stdout
        arr = np.frombuffer(raw_m, dtype=np.float32).reshape(-1, 2).astype(np.float64)
        reps = int(np.ceil(N / max(1, len(arr))))
        music = np.tile(arr, (reps, 1))[:N] * db(-17)

    # Smooth ducking under voice
    env_v = lp(np.abs(voice), 6.0)
    duck = 1.0 - 0.58 * np.clip(env_v / (env_v.max() * 0.25 + 1e-6), 0.0, 1.0)
    mix = np.column_stack([voice, voice]) + sfx + music * duck[:, None]
    mix = np.tanh(mix * 0.92) * 0.96

    (P / "data").mkdir(exist_ok=True)
    wavfile.write(P / "data/mix.wav", SR, (np.clip(mix, -1.0, 1.0) * 32767).astype(np.int16))
    print(f"data/mix.wav ({DUR:.2f} s, {len(cj.get('cues', []))} SFX cues, music={music_mode})")


if __name__ == "__main__":
    main()
