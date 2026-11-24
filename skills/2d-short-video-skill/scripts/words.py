#!/usr/bin/env python3
"""Word-level timestamp aligner using local Whisper (faster-whisper) with clean inline fallback.

Usage:
  scripts/py scripts/words.py <project_dir>
  scripts/py scripts/words.py <project_dir> --audio my_recording.m4a
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path

norm = lambda w: re.sub(r"[^a-z0-9]+", "", w.lower())
strip_tags = lambda txt: re.sub(r"\[[^\]]+\]", " ", txt)


def align(script_words: list[str], heard: list[tuple[str, float, float]], t0: float, t1: float) -> list[tuple[float, float]]:
    a = [norm(w) for w in script_words]
    b = [norm(h[0]) for h in heard]
    times: list[tuple[float, float] | None] = [None] * len(a)
    for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (heard[blk.b + k][1], heard[blk.b + k][2])
    i = 0
    while i < len(a):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(a) and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i > 0 else t0
        hi = times[j][0] if j < len(a) else t1
        if hi <= lo:
            hi = lo + 0.05 * (j - i)
        lengths = [max(1, len(a[k])) for k in range(i, j)]
        tot = sum(lengths)
        c = lo
        for k, l in zip(range(i, j), lengths):
            d = (hi - lo) * l / tot
            times[k] = (c, c + d * 0.9)
            c += d
        i = j
    return times  # type: ignore[return-value]


def inline_fallback(proj: Path, script: dict) -> None:
    lines_data = json.loads((proj / "data/lines.json").read_text(encoding="utf-8"))["lines"]
    words = []
    for i, ln in enumerate(script["lines"]):
        clean = strip_tags(ln["text"])
        toks = [w for w in clean.split() if norm(w)]
        wts = [
            len(norm(w)) + 2.5 + (2.5 if w.endswith(",") else 4.5 if re.search(r"[.?!]$", w) and k < len(toks) - 1 else 0)
            for k, w in enumerate(toks)
        ]
        lo, hi = lines_data[i]["start"], lines_data[i]["end"]
        c = lo
        tot = sum(wts) or 1.0
        for w, wt in zip(toks, wts):
            d = (hi - lo) * wt / tot
            speak = d - (hi - lo) * (wt - len(norm(w)) - 2.5) / tot
            words.append({"w": w, "line": i, "s": round(c, 3), "e": round(c + speak * 0.92, 3)})
            c += d
    (proj / "data/words.json").write_text(json.dumps(words, indent=2), encoding="utf-8")
    (proj / "data/words.txt").write_text(
        "\n".join(f"{w['s']:7.2f} {w['e']:7.2f}  L{w['line']:<2d} {w['w']}" for w in words),
        encoding="utf-8",
    )
    print(f"data/words.json: {len(words)} words (interpolated within line bounds)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--audio", help="Optional custom voiceover file (wav/m4a/mp3)")
    args = ap.parse_args()

    proj = Path(args.project)
    script = json.loads((proj / "script.json").read_text(encoding="utf-8"))

    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("small.en", device="cpu", compute_type="int8")
    except Exception as e:
        if args.audio or not (proj / "data/lines.json").exists():
            raise SystemExit(f"faster-whisper required for custom audio: {e}")
        print(f"Whisper unavailable ({type(e).__name__}); using line-bounded fallback")
        inline_fallback(proj, script)
        return

    if args.audio:
        (proj / "data").mkdir(exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", args.audio, "-ac", "1", "-ar", "24000", str(proj / "data/narration.wav")],
            check=True,
        )

    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(proj / "data/narration.wav"), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    segs, _ = model.transcribe(np.frombuffer(raw, dtype=np.float32), word_timestamps=True, vad_filter=False)
    heard = [(w.word.strip(), w.start + 0.04, w.end) for s in segs for w in s.words]

    toks = [(w, i) for i, ln in enumerate(script["lines"]) for w in strip_tags(ln["text"]).split() if norm(w)]
    dur_audio = float(
        subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(proj / "data/narration.wav")],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    times = align([w for w, _ in toks], heard, 0.0, dur_audio)
    words = [{"w": w, "line": i, "s": round(s, 3), "e": round(e, 3)} for (w, i), (s, e) in zip(toks, times)]

    if args.audio or not (proj / "data/lines.json").exists():
        lines = []
        for i, ln in enumerate(script["lines"]):
            ws = [w for w in words if w["line"] == i]
            lines.append({"i": i, "text": strip_tags(ln["text"]).strip(), "start": ws[0]["s"], "end": ws[-1]["e"]})
        (proj / "data/lines.json").write_text(
            json.dumps({"duration": round(dur_audio, 3), "lines": lines}, indent=2),
            encoding="utf-8",
        )
    else:
        lines_data = json.loads((proj / "data/lines.json").read_text(encoding="utf-8"))["lines"]
        for w in words:
            lo, hi = lines_data[w["line"]]["start"], lines_data[w["line"]]["end"]
            w["s"] = round(min(max(w["s"], lo), hi), 3)
            w["e"] = round(min(max(w["e"], w["s"]), hi), 3)

    (proj / "data/words.json").write_text(json.dumps(words, indent=2), encoding="utf-8")
    (proj / "data/words.txt").write_text(
        "\n".join(f"{w['s']:7.2f} {w['e']:7.2f}  L{w['line']:<2d} {w['w']}" for w in words),
        encoding="utf-8",
    )
    print(f"data/words.json: {len(words)} words (Whisper matched {len(heard)} tokens)")


if __name__ == "__main__":
    main()
