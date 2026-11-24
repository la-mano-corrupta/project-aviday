#!/usr/bin/env python3
"""Multi-key Gemini REST API router (stdlib-only) for Philosophy 2D Shorts.

Supports up to 7+ Gemini API keys via:
  - GEMINI_API_KEYS="k1,k2,...,k7"
  - GEMINI_API_KEY_1 .. GEMINI_API_KEY_7
  - GEMINI_API_KEY
  - .env file in current dir or repo root (never committed)
  - Optional --worker-url / GEMINI_WORKER_URL proxy

Rotates keys automatically on HTTP 429 / 500 / 502 / 503.

Examples:
  python3 scripts/gemini_router.py check-keys
  python3 scripts/gemini_router.py generate-short \
    --philosopher "Aristotle" \
    --topic "Why leisure precedes wisdom" \
    --duration 45 --style dark-academia-monograph --out script.json
  python3 scripts/gemini_router.py audit-quotes --script path/to/script.json
  python3 scripts/gemini_router.py generate-thumbnail \
    --script path/to/script.json --both --out path/to/review/cover
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
DEFAULT_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-nano-banana-2.1")
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVISION = "2026-05-20"


def load_dotenv_candidates() -> None:
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ and v:
                os.environ[k] = v


def collect_keys() -> list[str]:
    load_dotenv_candidates()
    keys: list[str] = []
    multi = os.environ.get("GEMINI_API_KEYS", "")
    if multi:
        keys.extend([k.strip() for k in multi.split(",") if k.strip()])
    for i in range(1, 20):
        val = os.environ.get(f"GEMINI_API_KEY_{i}", "").strip()
        if val and val not in keys:
            keys.append(val)
    single = os.environ.get("GEMINI_API_KEY", "").strip()
    if single and single not in keys:
        keys.append(single)
    return keys


def call_gemini_json(prompt: str, model: str = DEFAULT_MODEL, worker_url: str = "") -> dict:
    if worker_url:
        req = urllib.request.Request(
            f"{worker_url.rstrip('/')}/reels/generate-script",
            data=json.dumps({"prompt": prompt}).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "2D-Short-Skill/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("result", payload)

    keys = collect_keys()
    if not keys:
        raise RuntimeError(
            "No Gemini API keys configured. Set GEMINI_API_KEYS or GEMINI_API_KEY_1..7 in env or .env."
        )

    candidates = [model] + [m for m in ("gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash") if m != model]
    order = list(keys)
    random.shuffle(order)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
        },
    }).encode("utf-8")

    last_err = None
    for candidate_model in candidates:
        overload_hits = 0
        for idx, key in enumerate(order, start=1):
            url = f"{API_BASE}/{candidate_model}:generateContent?key={key}"
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
            except urllib.error.HTTPError as e:
                last_err = f"{candidate_model} Key #{idx} HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')[:200]}"
                print(f"[gemini_router] {last_err}", file=sys.stderr)
                if e.code == 503:
                    overload_hits += 1
                    if overload_hits >= 2 and candidate_model != candidates[-1]:
                        print(f"[gemini_router] {candidate_model} overloaded globally; cascading fallback...", file=sys.stderr)
                        break
                    continue
                if e.code in (404, 429, 500, 502):
                    continue
                raise RuntimeError(last_err) from e
            except Exception as e:
                last_err = f"{candidate_model} Key #{idx} error: {e}"
                print(f"[gemini_router] {last_err}", file=sys.stderr)
                overload_hits += 1
                if overload_hits >= 2 and candidate_model != candidates[-1]:
                    break
                continue
    raise RuntimeError(f"All {len(order)} Gemini key(s) failed across {candidates}. Last error: {last_err}")


def build_short_prompt(philosopher: str, topic: str, duration: int, style: str) -> str:
    targets = {15: "30-35", 30: "65-70", 45: "95-102", 60: "125-140"}
    budget = targets.get(duration, f"{int(duration * 2.15)}-{int(duration * 2.35)}")
    return f"""
You are an elite 2D Philosophy Shorts scriptwriter & director for YouTube Shorts, Instagram Reels, and TikTok.
Create a complete JSON package for a {duration}-second vertical (1080x1920) 2D short in style "{style}".
Philosopher / Lens: {philosopher}
Topic: {topic}

STRICT RULES:
1. Spoken word budget: strictly {budget} spoken words across all lines (excluding [beat]/[pause] tags).
2. Line 1 Spoken Hook: 7-8 words MAX. Start mid-tension on frame 1 (zero greetings, zero logos).
3. Quote Verification: Use ONLY verifiable primary-source quotes (cite book/section) or clearly label secondary historical accounts (Plutarch, Diogenes Laertius). NEVER fabricate or use disputed internet quotes.
4. Ear-first prose: short sentences, natural contractions, spell out all numbers ("twenty-four", not 24), add phonetic guide in parentheses on first tricky name in "phonetics" field.
5. Reverse-write ending: final line loops seamlessly back into line 1 OR lands a crisp DM-shareable mirror stinger.
6. Cover text: 2-3 bold words max complementing (never repeating) the title.

Return valid JSON matching this exact structure:
{{
  "title": "Short compelling title",
  "style": "{style}",
  "northStar": "One sentence philosophical shift",
  "cover": {{
    "headline": "2-3 WORDS",
    "sublabel": "{philosopher}",
    "visualBrief": "Expressive high-contrast 2D focal subject"
  }},
  "hooks": [
    {{"archetype": "Misconception|Story|Callout|Paradox", "spoken": "...", "onScreen": "...", "frame1Visual": "..."}}
  ],
  "voice": "bm_george",
  "speed": 1.0,
  "lead": 0.35,
  "outro": 0.75,
  "gap": 0.28,
  "music": "bed",
  "sources": ["Primary text citation or archival source"],
  "phonetics": {{"Word": "pro-NUN-see-ay-shun"}},
  "lines": [
    {{
      "text": "Spoken line (can include [beat] or [pause] in scriptNotes, keep text clean for TTS)",
      "caps": "1 TO 3 *WORDS | PER *CHUNK",
      "scene": "metaphor|diagram|chart|dialogue|rebel",
      "visual": "Concise 2D Enter/Action/Exit direction inside 823x960 safe box",
      "sfx": "thud|ink|whoosh|pop|chime|none",
      "gap": 0.28
    }}
  ],
  "instagramCaption": "Hook question\\n\\nBrief reflection\\n\\n#philosophy #2danimation #shorts"
}}
""".strip()


def build_audit_prompt(script_json: dict) -> str:
    return f"""
Audit all philosophical claims and quotes in this short-form video script against primary texts.
Identify any fabricated, paraphrased, or misattributed internet quotes (e.g., Gladiator lines credited to Marcus Aurelius, James Allen credited to Epictetus, fake Socrates quotes).
Return JSON:
{{
  "verifiedClaims": [{{"claim": "...", "citation": "...", "status": "verified|secondary|disputed"}}],
  "issuesFound": ["..."],
  "suggestedFixes": ["..."],
  "safeToPublish": true
}}

Script JSON:
{json.dumps(script_json, indent=2)}
""".strip()


def _extract_image_bytes(payload: dict) -> tuple[bytes, str]:
    """Extract raw image bytes & mime type from Interactions or generateContent responses."""
    out_img = payload.get("output_image")
    if isinstance(out_img, dict) and out_img.get("data"):
        return base64.b64decode(out_img["data"]), out_img.get("mime_type", "image/jpeg")

    for step in payload.get("steps", []) or []:
        if step.get("type") != "model_output":
            continue
        for block in step.get("content", []) or []:
            if block.get("type") == "image" and block.get("data"):
                return base64.b64decode(block["data"]), block.get("mime_type", "image/jpeg")

    for block in payload.get("outputs", []) or []:
        if block.get("type") == "image" and block.get("data"):
            return base64.b64decode(block["data"]), block.get("mime_type", "image/jpeg")

    for cand in payload.get("candidates", []) or []:
        parts = cand.get("content", {}).get("parts", []) or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if isinstance(inline, dict) and inline.get("data"):
                return base64.b64decode(inline["data"]), inline.get("mimeType") or inline.get("mime_type", "image/jpeg")

    raise RuntimeError(f"No image data in response keys: {sorted(payload.keys())}")


def _find_ffmpeg() -> str | None:
    local_ff = Path.home() / ".local" / "bin" / "ffmpeg"
    if local_ff.is_file():
        return str(local_ff)
    return shutil.which("ffmpeg")


def _normalize_cover_image(raw_bytes: bytes, out_path: Path, aspect_ratio: str) -> None:
    """Save raw generated image and normalize to exact platform cover dimensions under 2 MB."""
    target_dims = {"9:16": (1080, 1920), "3:4": (1080, 1440)}.get(aspect_ratio)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_dims:
        out_path.write_bytes(raw_bytes)
        return

    w, h = target_dims
    ffmpeg = _find_ffmpeg()
    with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = Path(tmp.name)

    try:
        if out_path.suffix.lower() in {".jpg", ".jpeg"} and ffmpeg:
            vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
            subprocess.run(
                [ffmpeg, "-y", "-v", "error", "-i", str(tmp_path), "-vf", vf, "-q:v", "2", str(out_path)],
                check=True,
            )
            return
        if out_path.suffix.lower() == ".png" and ffmpeg:
            vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
            subprocess.run(
                [ffmpeg, "-y", "-v", "error", "-i", str(tmp_path), "-vf", vf, str(out_path)],
                check=True,
            )
            return
        out_path.write_bytes(raw_bytes)
    finally:
        tmp_path.unlink(missing_ok=True)


def call_gemini_image(
    prompt: str,
    aspect_ratio: str = "9:16",
    image_size: str = "2K",
    model: str = DEFAULT_IMAGE_MODEL,
    out_mime: str = "image/jpeg",
) -> tuple[bytes, str]:
    """Generate an image via Gemini Nano Banana Interactions API with 7-key rotation."""
    keys = collect_keys()
    if not keys:
        raise RuntimeError(
            "No Gemini API keys configured. Set GEMINI_API_KEYS or GEMINI_API_KEY_1..7 in env or .env."
        )

    order = list(keys)
    random.shuffle(order)

    interactions_body = json.dumps({
        "model": model,
        "input": prompt,
        "response_format": {
            "type": "image",
            "mime_type": out_mime,
            "aspect_ratio": aspect_ratio,
            "image_size": image_size,
        },
    }).encode("utf-8")

    generate_content_body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "imageSize": image_size,
            },
        },
    }).encode("utf-8")

    last_err = None
    for idx, key in enumerate(order, start=1):
        req = urllib.request.Request(
            INTERACTIONS_URL,
            data=interactions_body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key,
                "Api-Revision": API_REVISION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return _extract_image_bytes(data)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")[:300]
            last_err = f"Key #{idx} Interactions HTTP {e.code}: {err_body}"
            print(f"[gemini_router] {last_err}", file=sys.stderr)
            if e.code in (429, 500, 502, 503):
                continue
            if e.code in (400, 404):
                # Fallback to classic generateContent image endpoint if interactions schema rejects model/header
                fb_url = f"{API_BASE}/{model}:generateContent?key={key}"
                fb_req = urllib.request.Request(
                    fb_url,
                    data=generate_content_body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(fb_req, timeout=60) as fb_resp:
                        fb_data = json.loads(fb_resp.read().decode("utf-8"))
                    return _extract_image_bytes(fb_data)
                except urllib.error.HTTPError as fb_e:
                    fb_err = fb_e.read().decode("utf-8", errors="ignore")[:300]
                    last_err = f"Key #{idx} fallback HTTP {fb_e.code}: {fb_err}"
                    print(f"[gemini_router] {last_err}", file=sys.stderr)
                    if fb_e.code in (429, 500, 502, 503):
                        continue
                    raise RuntimeError(last_err) from fb_e
            raise RuntimeError(last_err) from e
        except Exception as e:
            last_err = f"Key #{idx} error: {e}"
            print(f"[gemini_router] {last_err}", file=sys.stderr)
            continue
    raise RuntimeError(f"All {len(order)} Gemini key(s) failed for image generation. Last error: {last_err}")


def _find_chrome() -> str:
    candidates = [
        os.environ.get("CHROME", ""),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    raise RuntimeError("Headless Chrome not found (set CHROME env var).")


def generate_api_svg_cover(script_json: dict, out_path: Path, aspect_ratio: str = "9:16", custom_prompt: str = "") -> str:
    """Ask the 7-key Gemini text pool for an editorial 2D SVG poster and rasterize via Chrome+FFmpeg."""
    w, h = (1080, 1440) if aspect_ratio == "3:4" else (1080, 1920)
    cover = script_json.get("cover", {}) or {}
    headline = str(cover.get("headline") or script_json.get("title") or "STOLEN MINDS").strip().upper()
    sublabel = str(cover.get("sublabel") or "ARISTOTLE · ORWELL · RUSSELL").strip().upper()
    brief = custom_prompt or str(cover.get("visualBrief") or script_json.get("northStar") or "Moody dark academia allegory")

    svg_prompt = f"""
Design a high-CTR editorial 2D philosophy poster as pure valid standalone SVG (viewBox="0 0 {w} {h}", width="{w}", height="{h}").
Headline text centered in the upper-middle safe third (around y={int(h*0.29)}): "{headline}"
Sublabel right underneath (around y={int(h*0.34)}): "{sublabel}"
Visual brief (centered cleanly between y={int(h*0.38)} and y={int(h*0.74)}): {brief}
Palette: obsidian background #08090C, crimson #9E3B33, amber gold #D4A853, cream ivory #F2EAD8.
Requirements:
- Keep ALL text and focal art strictly inside x=[110..{w-110}], y=[{int(h*0.23)}..{int(h*0.77)}] so 1:1, 4:5, and 3:4 center crops never slice anything.
- Use rich layered SVG gradients, geometric shapes, dramatic chiaroscuro rim lighting, radial glow behind the focal subject, subtle crosshatch accents, and razor-sharp bold typography.
- Return valid JSON: {{"svg": "<svg xmlns=\\"http://www.w3.org/2000/svg\\" viewBox=\\"0 0 {w} {h}\\" ...>...</svg>"}}
""".strip()

    res = call_gemini_json(svg_prompt)
    svg_code = str(res.get("svg", "")).strip()
    if "<svg" not in svg_code:
        raise RuntimeError("Gemini SVG fallback did not return valid <svg> markup.")

    chrome = _find_chrome()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        html_file = td_p / "cover.html"
        shot_png = td_p / "shot.png"
        html_file.write_text(
            f'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:#08090C;overflow:hidden;">{svg_code}</body></html>',
            encoding="utf-8",
        )
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                f"--window-size={w},{h}",
                "--hide-scrollbars",
                f"--screenshot={shot_png}",
                html_file.as_uri(),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _normalize_cover_image(shot_png.read_bytes(), out_path, aspect_ratio)
    return "gemini-text-svg-chrome"


def build_thumbnail_prompt(script_json: dict, aspect_ratio: str = "9:16") -> str:
    cover = script_json.get("cover", {}) or {}
    headline = str(cover.get("headline") or script_json.get("title") or "THINK OR OBEY").strip()
    sublabel = str(cover.get("sublabel") or "").strip()
    visual = str(cover.get("visualBrief") or script_json.get("northStar") or "Dramatic philosophical allegory").strip()
    style = str(script_json.get("style") or "dark-academia-monograph").strip()

    style_desc = {
        "sisyphus-sketch": "hand-drawn rough black ink notebook illustration with cross-hatching, textured off-white/sepia paper grain, amber highlight glow, Sisyphus 55 / After Skool indie philosophy aesthetic",
        "dark-academia-monograph": "moody chiaroscuro 2D charcoal and hand-inked gouache illustration, deep obsidian #09090D shadows, burnt amber #E5A93C rim lighting, ivory parchment highlights, Eternalised / Einzelganger aesthetic",
        "school-of-thought": "editorial flat-vector 2D animation keyframe with tactile paper grain, bold geometric silhouette, warm slate and coral contrast, The School of Life aesthetic",
        "socratic-duo": "stark minimalist 2D ink cartoon on aged parchment backdrop, expressive wide-eyed silhouette vs glowing lantern sage",
    }.get(style, "high-contrast 2D editorial hand-inked animation illustration with chiaroscuro lighting")

    crop_note = (
        "Strictly center ALL vital imagery, character eyes/head, and typography inside the central 55% safe box (horizontally centered, vertically in the middle third) so 1:1, 4:5, and 3:4 crops never slice any letter or focal detail. Leave top 20% and bottom 30% clear dark negative space for Shorts/Reels UI."
        if aspect_ratio == "9:16"
        else "Strictly frame the hero subject and text centered inside the inner 75% safe area for an Instagram 3:4 grid cover."
    )

    sub_line = f' Underneath in subtle smaller tracked gold serif caps: "{sublabel.upper()}".' if sublabel else ""
    return (
        f"Vertical {aspect_ratio} high-CTR YouTube Shorts & Instagram Reels cover art. "
        f"Style: {style_desc}. "
        f"Scene concept: {visual}. "
        f"Focal emotion & contrast: razor-sharp focal separation between grim industrial shadow and a single warm golden spark of consciousness, instantly readable at 150px thumbnail scale, zero clutter, zero stock-photo realism. "
        f"Render large, razor-sharp, high-contrast distressed cream/gold editorial display typography inside the middle-upper safe zone reading ONLY the exact phrase: \"{headline.upper()}\".{sub_line} "
        f"{crop_note} No watermarks, no UI buttons, no small paragraph text."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="7-key Gemini router for 2D philosophy shorts & thumbnails.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate-short", help="Generate hooks, citations, and script.json")
    g.add_argument("--philosopher", required=True)
    g.add_argument("--topic", required=True)
    g.add_argument("--duration", type=int, default=30, choices=[15, 30, 45, 60])
    g.add_argument("--style", default="sisyphus-sketch")
    g.add_argument("--model", default=DEFAULT_MODEL)
    g.add_argument("--worker-url", default=os.environ.get("GEMINI_WORKER_URL", ""))
    g.add_argument("--out", default="-")

    a = sub.add_parser("audit-quotes", help="Verify quotes & claims in an existing script.json")
    a.add_argument("--script", required=True)
    a.add_argument("--model", default=DEFAULT_MODEL)
    a.add_argument("--worker-url", default=os.environ.get("GEMINI_WORKER_URL", ""))

    t = sub.add_parser("generate-thumbnail", help="Generate high-CTR 2D philosophy covers via Gemini Nano Banana API")
    t.add_argument("--script", help="Path to script.json (optional if --prompt provided)")
    t.add_argument("--prompt", help="Custom image prompt override")
    t.add_argument("--aspect", default="9:16", choices=["9:16", "3:4"])
    t.add_argument("--both", action="store_true", help="Generate both -9x16.jpg (1080x1920) and -3x4.jpg (1080x1440)")
    t.add_argument("--size", default="2K", choices=["1K", "2K", "4K"])
    t.add_argument("--model", default=DEFAULT_IMAGE_MODEL)
    t.add_argument("--mode", default="auto", choices=["auto", "raster", "svg"], help="auto falls back to Gemini-authored SVG+Chrome when Free Tier keys return limit:0 for Nano Banana")
    t.add_argument("--out", required=True, help="Output file path (or prefix when --both is used)")

    k = sub.add_parser("check-keys", help="Report how many Gemini keys are configured (without printing secrets)")

    args = ap.parse_args()
    if args.cmd == "check-keys":
        keys = collect_keys()
        worker = os.environ.get("GEMINI_WORKER_URL", "")
        print(json.dumps({"keyCount": len(keys), "workerConfigured": bool(worker)}, indent=2))
        return 0

    if args.cmd == "generate-short":
        res = call_gemini_json(
            build_short_prompt(args.philosopher, args.topic, args.duration, args.style),
            model=args.model,
            worker_url=args.worker_url,
        )
        out_str = json.dumps(res, indent=2, ensure_ascii=False)
        if args.out == "-":
            print(out_str)
        else:
            Path(args.out).write_text(out_str + "\n", encoding="utf-8")
            print(f"Wrote {args.out}")
        return 0

    if args.cmd == "audit-quotes":
        data = json.loads(Path(args.script).read_text(encoding="utf-8"))
        res = call_gemini_json(
            build_audit_prompt(data),
            model=args.model,
            worker_url=args.worker_url,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "generate-thumbnail":
        if not args.prompt and not args.script:
            ap.error("Provide --script or --prompt for generate-thumbnail")
        script_data = json.loads(Path(args.script).read_text(encoding="utf-8")) if args.script else {}
        aspects = ["9:16", "3:4"] if args.both else [args.aspect]
        for ar in aspects:
            prompt = args.prompt or build_thumbnail_prompt(script_data, ar)
            if args.both:
                suffix = "9x16" if ar == "9:16" else "3x4"
                out_file = Path(f"{args.out}-{suffix}.jpg")
            else:
                out_file = Path(args.out)

            if args.mode == "svg":
                engine_used = generate_api_svg_cover(script_data, out_file, ar, args.prompt or "")
                size_kb = out_file.stat().st_size / 1024.0
                print(f"Generated {ar} SVG thumbnail ({engine_used}) -> {out_file} ({size_kb:.1f} KB)")
                continue

            try:
                raw_bytes, mime = call_gemini_image(
                    prompt,
                    aspect_ratio=ar,
                    image_size=args.size,
                    model=args.model,
                )
                _normalize_cover_image(raw_bytes, out_file, ar)
                size_kb = out_file.stat().st_size / 1024.0
                print(f"Generated {ar} thumbnail ({args.model}, {mime}) -> {out_file} ({size_kb:.1f} KB)")
            except RuntimeError as exc:
                if args.mode == "auto" and ("limit: 0" in str(exc) or "quota" in str(exc).lower() or "429" in str(exc)):
                    print(f"[gemini_router] Native Nano Banana raster unavailable on current key tier; generating Gemini-authored 2D SVG poster via Chrome...", file=sys.stderr)
                    engine_used = generate_api_svg_cover(script_data, out_file, ar, args.prompt or "")
                    size_kb = out_file.stat().st_size / 1024.0
                    print(f"Generated {ar} thumbnail ({engine_used}) -> {out_file} ({size_kb:.1f} KB)")
                else:
                    raise
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
