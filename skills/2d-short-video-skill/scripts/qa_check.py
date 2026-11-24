#!/usr/bin/env python3
"""Automated pre-publish QA checks for 2D Short Video projects.

Checks:
  1. Script word budget & disputed quote audit (check_script_budget.py)
  2. Timing JSON presence & duration bounds (<= 60s preferred, <= 180s max)
  3. Cover image resolutions (9:16 = 1080x1920, IG 3:4 = 1080x1440) if generated
  4. Rendered MP4 stream audit via ffprobe (1080x1920, audio stream present) if present
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from check_script_budget import audit_script


def probe_media(path: Path) -> dict | None:
    if not path.exists():
        return None
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run QA checks on a 2D short video project.")
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--target-sec", type=int, default=30)
    args = ap.parse_args()

    proj = Path(args.project).resolve()
    script_path = proj / "script.json"
    if not script_path.exists():
        print(f"FAIL: missing {script_path}")
        return 1

    budget = audit_script(script_path, args.target_sec)
    print(f"[SCRIPT] {budget['word_count']} words (target {budget['recommended_range'][0]}-{budget['recommended_range'][1]}, max {budget['hard_max']}) | ok={budget['ok']}")
    for e in budget["errors"]:
        print(f"  ERROR: {e}")
    for w in budget["warnings"]:
        print(f"  WARN : {w}")

    ok = budget["ok"]

    words_path = proj / "data/words.json"
    lines_path = proj / "data/lines.json"
    if words_path.exists() and lines_path.exists():
        lines_meta = json.loads(lines_path.read_text(encoding="utf-8"))
        words_meta = json.loads(words_path.read_text(encoding="utf-8"))
        dur = float(lines_meta.get("duration", 0.0))
        print(f"[TIMING] {len(lines_meta.get('lines', []))} lines, {len(words_meta)} words, duration={dur:.2f}s")
        if dur > 62.0:
            print("  WARN : Duration exceeds 60s (optimal Shorts/Reels completion pocket is 15-45s).")
    else:
        print("[TIMING] WARN: data/lines.json or data/words.json not generated yet.")

    for label, expected in [("review/cover-9x16.jpg", (1080, 1920)), ("review/cover-3x4.jpg", (1080, 1440))]:
        p = proj / label
        info = probe_media(p)
        if info:
            st = info["streams"][0]
            dims = (int(st["width"]), int(st["height"]))
            size_kb = p.stat().st_size / 1024
            match = dims == expected
            print(f"[COVER ] {label}: {dims[0]}x{dims[1]} ({size_kb:.1f} KB) {'OK' if match else f'MISMATCH expected {expected}'}")
            if not match or size_kb >= 2048:
                ok = False

    mp4s = sorted((proj / "renders").glob("*.mp4")) if (proj / "renders").exists() else []
    for mp4 in mp4s:
        info = probe_media(mp4)
        if not info:
            continue
        v = [s for s in info["streams"] if s["codec_type"] == "video"]
        a = [s for s in info["streams"] if s["codec_type"] == "audio"]
        dims = (int(v[0]["width"]), int(v[0]["height"])) if v else (0, 0)
        dur_m = float(info["format"].get("duration", 0))
        print(f"[VIDEO ] {mp4.name}: {dims[0]}x{dims[1]} | {dur_m:.2f}s | audio_streams={len(a)}")
        if dims != (1080, 1920) or not a:
            print("  ERROR: Final MP4 must be 1080x1920 with an audio stream.")
            ok = False

    print("QA RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
