#!/usr/bin/env python3
"""Audit a short-form philosophy script (script.json or plain text) for:
- Spoken word budget (150 WPM = 2.5 words/sec, with 10-15% pause buffer)
- Opening hook length (7-8 spoken words max for first 3 seconds)
- Long sentences (>18 words), unspelled numbers, AI narration clichés
- Known disputed / misattributed philosophy quotes

Usage:
  python3 scripts/check_script_budget.py path/to/script.json --target-sec 30
  python3 scripts/check_script_budget.py path/to/draft.txt --target-sec 45 --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BUDGETS = {
    15: (30, 35, 38),
    30: (65, 70, 75),
    45: (95, 102, 113),
    60: (125, 140, 150),
}

AI_CLICHES = [
    "in today's fast-paced world",
    "in a world where",
    "delve into",
    "let's dive in",
    "ever wondered why",
    "unlock your potential",
    "game changer",
    "tapestry of",
    "without further ado",
    "like and subscribe",
]

DISPUTED_QUOTES = [
    ("only true wisdom is in knowing you know nothing", "Socrates (no confirmed Plato/Xenophon source; use Diogenes Laertius paraphrase or debunk)"),
    ("to find yourself, think for yourself", "Socrates (unverified viral attribution)"),
    ("let him who would move the world first move himself", "Socrates (unverified viral attribution)"),
    ("falling down is not a failure", "Socrates / Mary Pickford misattribution (unverified)"),
    ("what we do in life echoes in eternity", "Marcus Aurelius (actually from 2000 film Gladiator)"),
    ("luck is what happens when preparation meets opportunity", "Seneca (no matching Latin corpus text)"),
    ("circumstances do not make the man", "Epictetus (actually James Allen, As a Man Thinketh, 1903)"),
    ("life is not a problem to be solved, but a reality to be experienced", "Kierkegaard (actually J.J. van der Leeuw, 1928)"),
    ("tolerance will reach such a level that intelligent people will be banned", "Dostoevsky (modern internet fabrication)"),
    ("being deeply loved by someone gives you strength", "Lao Tzu (modern interpretive rendering, not classical Tao Te Ching)"),
    ("two ears and one tongue", "Diogenes (actually Zeno / Spartan attribution in antiquity)"),
]


def strip_directions(text: str) -> str:
    return re.sub(r"\[[^\]]+\]", " ", text)


def load_lines(path: Path) -> tuple[list[str], list[str]]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        raw_lines = [str(ln.get("text", "")).strip() for ln in data.get("lines", []) if ln.get("text")]
    else:
        raw_lines = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    spoken_lines = [re.sub(r"\s+", " ", strip_directions(ln)).strip() for ln in raw_lines]
    return raw_lines, [ln for ln in spoken_lines if ln]


def audit_script(path: Path, target_sec: int) -> dict:
    raw_lines, spoken_lines = load_lines(path)
    full_raw = " ".join(raw_lines)
    full_spoken = " ".join(spoken_lines)
    words = re.findall(r"[A-Za-z0-9'’-]+", full_spoken)
    word_count = len(words)

    rec_min, rec_max, hard_max = BUDGETS.get(
        target_sec,
        (int(target_sec * 2.15), int(target_sec * 2.3), int(target_sec * 2.5)),
    )
    est_sec_raw = round(word_count / 2.5, 2)
    pause_tags = len(re.findall(r"\[(beat|pause|slower|intimate)\]", full_raw, flags=re.I))
    est_sec_with_pauses = round(est_sec_raw + pause_tags * 0.35, 2)

    hook_words = len(re.findall(r"[A-Za-z0-9'’-]+", spoken_lines[0])) if spoken_lines else 0
    sentences = [s.strip() for s in re.split(r"[.!?]+", full_spoken) if s.strip()]
    long_sentences = [
        {"sentence": s, "words": len(re.findall(r"[A-Za-z0-9'’-]+", s))}
        for s in sentences
        if len(re.findall(r"[A-Za-z0-9'’-]+", s)) > 18
    ]
    digits = re.findall(r"\b\d+\b", full_spoken)
    lower_spoken = full_spoken.lower()
    cliches_found = [c for c in AI_CLICHES if c in lower_spoken]
    disputed_found = [
        {"snippet": snippet, "reason": reason}
        for snippet, reason in DISPUTED_QUOTES
        if snippet in lower_spoken
    ]

    warnings = []
    errors = []
    if word_count > hard_max:
        errors.append(f"Word count {word_count} exceeds {target_sec}s ceiling ({hard_max} max; target {rec_min}-{rec_max}).")
    elif word_count > rec_max:
        warnings.append(f"Word count {word_count} leaves <10% pause margin for {target_sec}s (recommended {rec_min}-{rec_max}).")
    elif word_count < rec_min:
        warnings.append(f"Word count {word_count} is below {target_sec}s target ({rec_min}-{rec_max}); ensure visual holds stay active.")

    if hook_words > 8:
        warnings.append(f"Line 1 hook has {hook_words} spoken words (target 7-8 words max for 0-3s scroll stop).")
    if long_sentences:
        warnings.append(f"{len(long_sentences)} sentence(s) exceed 18 words (harder to speak/parse by ear).")
    if digits:
        warnings.append(f"Unspelled digits found {digits}; spell out numbers for cleaner TTS pacing.")
    if cliches_found:
        warnings.append(f"AI/generic clichés detected: {cliches_found}")
    if disputed_found:
        errors.append("Disputed/misattributed quote detected! Replace or explicitly frame as myth-busting.")

    return {
        "file": str(path),
        "target_sec": target_sec,
        "word_count": word_count,
        "recommended_range": [rec_min, rec_max],
        "hard_max": hard_max,
        "est_spoken_sec": est_sec_raw,
        "est_total_sec": est_sec_with_pauses,
        "hook_words": hook_words,
        "pause_tags": pause_tags,
        "long_sentences": long_sentences,
        "unspelled_digits": digits,
        "cliches": cliches_found,
        "disputed_quotes": disputed_found,
        "warnings": warnings,
        "errors": errors,
        "ok": len(errors) == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate philosophy short script budget and ear-first quality.")
    ap.add_argument("script_path", help="Path to script.json or text script")
    ap.add_argument("--target-sec", type=int, default=30, help="Target runtime in seconds (15, 30, 45, 60)")
    ap.add_argument("--json", action="store_true", help="Print JSON output")
    args = ap.parse_args()

    res = audit_script(Path(args.script_path), args.target_sec)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        status = "PASS" if res["ok"] else "FAIL"
        print(f"[{status}] {res['file']} | {res['word_count']} words "
              f"(target {res['recommended_range'][0]}-{res['recommended_range'][1]}, max {res['hard_max']}) "
              f"| ~{res['est_total_sec']}s | hook={res['hook_words']}w")
        for err in res["errors"]:
            print(f"  ERROR: {err}")
        for warn in res["warnings"]:
            print(f"  WARN : {warn}")
        for dq in res["disputed_quotes"]:
            print(f"  QUOTE: '{dq['snippet']}' -> {dq['reason']}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
