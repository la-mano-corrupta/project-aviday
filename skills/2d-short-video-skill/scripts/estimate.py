#!/usr/bin/env python3
"""Estimated word & line timing with no audio: script.json -> data/lines.json + data/words.json.

Usage:
  python3 scripts/estimate.py <project_dir> [--wps 2.5]
"""
import argparse
import json
import re
from pathlib import Path


def strip_tags(text: str) -> str:
    return re.sub(r"\[[^\]]+\]", " ", text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument(
        "--wps",
        type=float,
        default=2.5,
        help="Conversational philosophy pace in words/sec (150 WPM = 2.5)",
    )
    args = ap.parse_args()

    proj = Path(args.project)
    script = json.loads((proj / "script.json").read_text(encoding="utf-8"))
    speed = float(script.get("speed", 1.0))
    t = float(script.get("lead", 0.35))
    lines, words = [], []

    for i, ln in enumerate(script["lines"]):
        raw_text = ln["text"]
        clean_text = re.sub(r"\s+", " ", strip_tags(raw_text)).strip()
        toks = clean_text.split()
        letters = [len(re.sub(r"[^A-Za-z0-9]", "", w)) or 1 for w in toks]
        base = max(0.35, len(toks) / (args.wps * speed))
        unit = base / max(1.0, sum(l + 2.5 for l in letters))
        start = t
        for w, l in zip(toks, letters):
            d = (l + 2.5) * unit
            words.append({"w": w, "line": i, "s": round(t, 3), "e": round(t + d * 0.92, 3)})
            t += d
            if w.endswith(",") or w.endswith("—"):
                t += 0.14
            elif re.search(r"[.?!]$", w) and w is not toks[-1]:
                t += 0.28
        pauses = len(re.findall(r"\[pause\]", raw_text, flags=re.I)) * 0.45
        beats = len(re.findall(r"\[beat\]", raw_text, flags=re.I)) * 0.22
        t += pauses + beats
        lines.append({"i": i, "text": clean_text, "start": round(start, 3), "end": round(t, 3)})
        t += float(ln.get("gap", script.get("gap", 0.28)))

    dur = (lines[-1]["end"] if lines else 0.0) + float(script.get("outro", 0.75))
    data_dir = proj / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "lines.json").write_text(
        json.dumps({"duration": round(dur, 3), "estimated": True, "lines": lines}, indent=2),
        encoding="utf-8",
    )
    (data_dir / "words.json").write_text(json.dumps(words, indent=2), encoding="utf-8")
    print(f"estimated timing: {len(lines)} lines, {len(words)} words, {dur:.2f} s -> data/lines.json, data/words.json")


if __name__ == "__main__":
    main()
