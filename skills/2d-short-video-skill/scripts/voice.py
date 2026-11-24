#!/usr/bin/env python3
"""Narration synthesizer for 2D Philosophy Shorts ($0 local Kokoro-82M via kokoro-onnx, or edge-tts fallback).

Usage:
  scripts/py scripts/voice.py <project_dir>
  scripts/py scripts/voice.py --list
  scripts/py scripts/voice.py --download
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

import numpy as np
from scipy.io import wavfile

HOME = Path(os.environ.get("FACELESS_HOME", Path.home() / ".faceless-shorts"))
KDIR = HOME / "kokoro"
FILES = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
VOICES = {
    "bm_george": "UK male, documentary calm (Dark Academia / Stoic default)",
    "bm_fable": "UK male, reflective storyteller (Sisyphus / Existential)",
    "am_michael": "US male, steady explainer (School of Thought)",
    "am_onyx": "US male, deep gravitas (Schopenhauer / Nietzsche)",
    "am_puck": "US male, nimble conversational (Diogenes / Socratic Duo)",
    "af_heart": "US female, warm intimate (School of Life / Parable)",
    "bf_emma": "UK female, poised thoughtful",
}
SR = 24000


def clean_tts_text(raw: str, tts_map: dict[str, str] | None = None) -> str:
    txt = re.sub(r"\[[^\]]+\]", " ", raw)
    txt = re.sub(r"\s+", " ", txt).strip()
    if tts_map:
        for k, v in tts_map.items():
            txt = re.sub(rf"\b{re.escape(k)}\b", v, txt)
    return txt


def ensure_models() -> None:
    KDIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        p = KDIR / name
        if p.exists() and p.stat().st_size > 1_000_000:
            continue
        print(f"Downloading {name} (~one-time)...", flush=True)
        tmp = p.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(p)


def trim_silence(x: np.ndarray, thr: float = 0.008) -> np.ndarray:
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx):
        return x
    a = max(0, idx[0] - int(0.01 * SR))
    b = min(len(x), idx[-1] + int(0.03 * SR))
    return x[a:b]


def find_silences(x: np.ndarray, thr: float = 0.012, min_len: float = 0.06) -> list[tuple[float, float]]:
    hop = int(0.01 * SR)
    n = len(x) // hop
    if n <= 0:
        return []
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1))
    quiet = rms < thr * (np.abs(x).max() + 1e-9)
    out, st = [], None
    for f, q in enumerate(quiet):
        if q and st is None:
            st = f
        if (not q or f == n - 1) and st is not None:
            if (f - st) * 0.01 >= min_len:
                out.append((st * 0.01, f * 0.01))
            st = None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--voice")
    ap.add_argument("--speed", type=float)
    args = ap.parse_args()

    if args.list:
        for k, v in VOICES.items():
            print(f"{k:12s} {v}")
        return

    ensure_models()
    if args.download:
        return
    if not args.project:
        ap.error("project directory missing")

    from kokoro_onnx import Kokoro

    proj = Path(args.project)
    script = json.loads((proj / "script.json").read_text(encoding="utf-8"))
    voice = args.voice or script.get("voice", "bm_george")
    speed = float(args.speed or script.get("speed", 0.98))
    tts_map = script.get("ttsPhonetics", {})

    kokoro = Kokoro(str(KDIR / "kokoro-v1.0.onnx"), str(KDIR / "voices-v1.0.bin"))
    lang = "en-gb" if voice.startswith("b") else "en-us"
    say = lambda txt: trim_silence(np.asarray(kokoro.create(txt, voice=voice, speed=speed, lang=lang)[0], dtype=np.float64))

    groups, cur = [], []
    for i, ln in enumerate(script["lines"]):
        cur.append(i)
        cleaned = clean_tts_text(ln["text"])
        if re.search(r'[.?!]["\')]*$', cleaned) or ln.get("break") or i == len(script["lines"]) - 1:
            groups.append(cur)
            cur = []

    out = [np.zeros(int(float(script.get("lead", 0.35)) * SR))]
    t = len(out[0]) / SR
    lines = [None] * len(script["lines"])

    for g in groups:
        joined = " ".join(clean_tts_text(script["lines"][i]["text"], tts_map) for i in g)
        x = say(joined)
        cuts = [0.0]
        if len(g) > 1:
            lens = np.array([len(say(clean_tts_text(script["lines"][i]["text"], tts_map))) for i in g], dtype=float)
            pauses = find_silences(x)
            for c in np.cumsum(lens)[:-1] / lens.sum() * len(x) / SR:
                near = [p for p in pauses if abs((p[0] + p[1]) / 2 - c) < 0.4]
                if near:
                    p = min(near, key=lambda p: abs((p[0] + p[1]) / 2 - c))
                    cuts.append((p[0], p[1]))
                else:
                    cuts.append((c, c))
        dur_g = len(x) / SR
        for j, i in enumerate(g):
            a = 0.0 if j == 0 else cuts[j][1]
            b = dur_g if j == len(g) - 1 else cuts[j + 1][0]
            clean_orig = clean_tts_text(script["lines"][i]["text"])
            lines[i] = {"i": i, "text": clean_orig, "start": round(t + a, 3), "end": round(t + b, 3)}
            print(f"{i:2d} {lines[i]['start']:6.2f}-{lines[i]['end']:6.2f}  {clean_orig}", flush=True)
        last_ln = script["lines"][g[-1]]
        extra_pause = 0.35 if "[pause]" in last_ln["text"].lower() else 0.15 if "[beat]" in last_ln["text"].lower() else 0.0
        gap_sec = float(last_ln.get("gap", script.get("gap", 0.28))) + extra_pause
        gap = np.zeros(int(gap_sec * SR))
        out.extend([x, gap])
        t += (len(x) + len(gap)) / SR

    out.append(np.zeros(int(float(script.get("outro", 0.75)) * SR)))
    y = np.concatenate(out)
    y = y / (np.abs(y).max() + 1e-9) * 0.9
    (proj / "data").mkdir(exist_ok=True)
    wavfile.write(proj / "data/narration.wav", SR, (y * 32767).astype(np.int16))
    dur = len(y) / SR
    (proj / "data/lines.json").write_text(
        json.dumps({"duration": round(dur, 3), "voice": voice, "speed": speed, "lines": lines}, indent=2),
        encoding="utf-8",
    )
    print(f"data/narration.wav ({dur:.2f} s, {voice} x{speed}) + data/lines.json")


if __name__ == "__main__":
    main()
