#!/usr/bin/env python3
"""
Aviday — Custom Topic Faceless Reel AI Generator & Optional Publisher
Works locally (macOS/Linux) AND in GitHub Actions Linux runners, with or without social/AI keys!
1. Resolves script via `--script <path>`, direct `GEMINI_API_KEY` REST API, or zero-key style template fallback.
2. Synthesizes narration using selectable `--tts-provider` (`default`, `kokoro`, `gemini`, `elevenlabs`).
3. Runs `capture.mjs cues`, `tools/mix.py`, and `capture.mjs video` (1080x1920 MP4) + local cover thumbnails.
4. Optionally uploads to YouTube Shorts and Instagram Reels when credentials are configured (or skips cleanly with `--no-upload` / missing keys).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from synth_and_render import (
    DEFAULT_BADGES,
    PROJECTS_DIR,
    SKILL_DIR,
    STYLES_ALL,
    WORKER_URL,
    apply_cognitive_anticipation_lead,
    extract_cover_thumbnails,
    publish_social_uploads,
)
from tts_providers import (
    TTS_PROVIDERS,
    check_provider_readiness,
    get_faceless_home,
    get_projects_dir,
    is_real_secret,
    load_gemini_keys,
    resolve_python_bin,
    resolve_tts_provider,
    synthesize_project_audio,
)
from youtube_shorts_uploader import load_credentials as load_youtube_credentials

FACELESS_HOME = get_faceless_home()
ROTATED_STYLES = ["deep-dive", "night-file", "stick-story", "tall-tale"]
CHANNEL_HANDLE = os.environ.get("AVIDAY_HANDLE", "").lstrip("@")

VIRAL_TOPIC_CURRICULUM = {
    "deep-dive": [
        "What happens inside your body if you stop sleeping for 72 hours?",
        "Why does your body suddenly jerk awake right as you fall asleep?",
        "What actually happens inside your brain during a brain freeze?",
        "What happens to your human body at the bottom of the Mariana Trench?",
        "Why can't you tickle yourself even if you try your hardest?",
        "What happens inside your stomach if you swallow chewing gum?",
        "Why do your fingers wrinkle in water? (It is NOT osmosis!)",
        "What happens to your blood if you ascend too fast from deep water?",
        "How does rabies hijack the human nervous system to make you fear water?",
        "What happens inside your eyes when you rub them and see geometric stars?",
        "Why does biting aluminum foil send an electric shock through a filling?",
        "What happens inside your body during the first 60 seconds in an ice bath?",
        "How do painkillers actually know where the pain is in your body?",
        "What happens to your muscles and bones after 30 days in zero gravity?",
    ],
    "night-file": [
        "The unsolved disappearance of the 3 lighthouse keepers of Eilean Mor (1900)",
        "The mysterious Dyatlov Pass incident where 9 hikers cut their tent from the inside",
        "The ghost ship Mary Celeste found sailing with warm food still on the table",
        "The Max Headroom broadcast signal intrusion that hijacked Chicago television in 1987",
        "The Somerton Man (Tamam Shud case) found on an Australian beach with a secret code",
        "The unsolved Sodder Children disappearance on Christmas Eve 1945",
        "The mysterious Wow! radio signal from deep space that lasted 72 seconds and never repeated",
        "The Lead Masks Case of two Brazilian technicians found on Vintem Hill in 1966",
        "Flight 19: How five US Navy bombers vanished over the Atlantic in clear weather",
        "The unsolved Isabella Stewart Gardner Museum heist where thieves stole $500M in 81 minutes",
        "The Vela Incident: The unidentified double flash detected by satellite over the Indian Ocean",
        "The mysterious disappearance of pilot Frederick Valentich after reporting a hovering craft",
        "The Khamar-Daban incident where 6 experienced mountain hikers panicked in 1993",
        "The Hinterkaifeck footprints in the snow that led toward the farm but never left",
    ],
    "stick-story": [
        "What happens hour by hour if every human on Earth suddenly disappears except you?",
        "How to survive if you wake up trapped inside a sinking car underwater",
        "What happens if the global internet shuts down completely for 7 days?",
        "How to survive if an elevator cable snaps while you are on the 40th floor",
        "What happens if you get caught in a rip current and try to swim back to shore?",
        "What happens hour by hour if Earth stops spinning for just 5 seconds?",
        "How to survive if you fall onto subway tracks with a train approaching",
        "What happens if all GPS satellites stop working at the same time?",
        "How to survive being lost in the desert with only half a bottle of water",
        "What happens if every bee on Earth disappears tomorrow morning?",
        "How to escape quicksand if you sink up to your waist alone",
        "What happens inside a modern city if the water treatment plants stop for 48 hours?",
        "How to survive if lightning is about to strike where you are standing",
        "What happens if the Moon suddenly moves twice as close to Earth?",
    ],
    "tall-tale": [
        "In 1518, a town in France was struck by a mysterious plague that made 400 people dance for days",
        "In 1932, the Australian military declared war on 20,000 emus with machine guns—and lost",
        "In 1919, a 2.3-million-gallon tank of molasses burst in Boston and flooded the streets at 35 mph",
        "In 1859, the United States and Britain almost went to war over a single stray pig",
        "In 1904, the Olympic Marathon in St. Louis was so chaotic the winner rode in a car and ate rat poison",
        "How a corporal bear named Wojtek was officially enlisted in the Polish Army and carried artillery shells",
        "In 1814, a tsunami of 388,000 gallons of beer flooded the streets of London",
        "In 1788, the Austrian army accidentally fought a battle against itself in the dark",
        "How Napoleon Bonaparte was once attacked and overrun by a horde of 3,000 hungry rabbits",
        "In 1962, a contagious laughing epidemic in Tanganyika forced 14 schools to shut down",
        "How a cat named Unsinkable Sam survived the sinking of three different World War II warships",
        "In 1835, the New York Sun convinced millions of readers that astronomers found bat-people on the Moon",
        "How jockey Frank Hayes won a steeplechase horse race in 1923 despite passing away mid-race",
        "In 1977, Pepsi briefly became one of the largest naval powers on Earth after trading soda for submarines",
    ],
}


def pick_scheduled_style_and_topic(style_arg: str, topic_arg: str) -> tuple[str, str]:
    slot_idx = int(time.time() // (6 * 3600))
    clean_style = (style_arg or "").strip()
    if not clean_style or clean_style == "auto":
        style = ROTATED_STYLES[slot_idx % 4]
    elif clean_style in STYLES_ALL:
        style = clean_style
    else:
        raise ValueError(
            f"Invalid --style '{clean_style}'. Valid choices: auto, {', '.join(STYLES_ALL)}"
        )

    if not topic_arg or topic_arg == "auto" or topic_arg.startswith("Auto 6-Hour"):
        bank = VIRAL_TOPIC_CURRICULUM.get(style)
        if bank:
            day_cycle = (slot_idx // 4) % len(bank)
            topic = bank[day_cycle]
        else:
            ex_script = SKILL_DIR / "styles" / style / "example" / "script.json"
            if ex_script.is_file():
                topic = json.loads(ex_script.read_text()).get("title") or f"{style} explainer"
            else:
                topic = f"{style} explainer"
    else:
        topic = topic_arg

    return style, topic


def normalize_script_lines(lines: list) -> list[dict]:
    normalized: list[dict] = []
    for item in lines:
        if not isinstance(item, dict):
            raise ValueError("Each script line must be a JSON object.")
        text = str(item.get("text", "")).strip()
        if not text:
            raise ValueError("Each script line must contain a non-empty 'text' string.")
        entry = dict(item)
        entry["text"] = text
        caps = entry.get("caps")
        if isinstance(caps, list):
            parts = [str(c).strip() for c in caps if str(c).strip()]
            if parts:
                entry["caps"] = " | ".join(parts)
            else:
                entry.pop("caps", None)
        elif caps is not None:
            entry["caps"] = str(caps)
        normalized.append(entry)
    return normalized


def validate_and_load_script(script_path: str | Path) -> dict:
    p = Path(script_path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Script file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in script file {p}: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"Script JSON in {p} must be a top-level object.")
    lines = data.get("lines")
    if not isinstance(lines, list) or len(lines) == 0:
        raise ValueError(f"Script JSON in {p} must include a non-empty 'lines' list.")
    data = dict(data)
    data["lines"] = normalize_script_lines(lines)
    return data


def clear_stale_project_data(proj_dir: Path) -> None:
    data_dir = proj_dir / "data"
    if not data_dir.exists():
        return
    for name in (
        "lines.json",
        "words.json",
        "words.txt",
        "cues.json",
        "narration.wav",
        "mix.wav",
    ):
        target = data_dir / name
        if target.is_file():
            target.unlink()


def call_gemini_json(prompt: str) -> dict:
    """Call Google Gemini REST API directly using GEMINI_API_KEY / GEMINI_API_KEYS."""
    keys = load_gemini_keys()
    if not keys:
        raise RuntimeError("No valid GEMINI_API_KEY or GEMINI_API_KEYS configured.")

    base_url = (os.environ.get("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com").rstrip("/")
    models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    payload = json.dumps(
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.75, "responseMimeType": "application/json"},
        }
    ).encode("utf-8")

    last_err: Exception | None = None
    for key in keys:
        for model in models:
            endpoint = f"{base_url}/v1beta/models/{model}:generateContent"
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": key,
                    "User-Agent": "Project-Aviday/1.0",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                raw_text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.I)
                cleaned = re.sub(r"\s*```$", "", cleaned).strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and isinstance(parsed.get("lines"), list) and len(parsed["lines"]) >= 1:
                    return parsed
                last_err = RuntimeError(f"Gemini returned unexpected JSON shape: {str(parsed)[:200]}")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "ignore")[:240]
                last_err = RuntimeError(f"Gemini HTTP {e.code} ({model}): {body}")
                if e.code in (401, 403):
                    break
            except Exception as e:
                last_err = e
    raise RuntimeError(f"Gemini script generation failed: {last_err}")


def _build_script_prompt(style: str, topic: str, orig_script: dict) -> str:
    num_lines = len(orig_script["lines"])
    cta_text = f"credit to @{CHANNEL_HANDLE}" if CHANNEL_HANDLE else "a strong call-to-action"
    return f"""You are a viral Faceless Shorts / Instagram Reels & YouTube Shorts scriptwriter writing for style "{style}".
Topic requested: "{topic}"

Write a punchy, high-retention narration split into up to {num_lines} lines (matching this style template: {json.dumps(orig_script['lines'])}).

ENFORCE THE 8-BEAT VIRAL RETENTION FORMULA:
1. The Hook: A singular, absurd or shocking factual statement that arrests scrolling in the first 2 seconds.
2. The Setting: Establish the concrete context, year, or place to ground the absurdity.
3. The Escalation: Rapid beats of increasing tension, stakes, or physical progression.
4. The Snap: The physical breaking point or climax of the story.
5. Deadpan Double Line: A brief deadpan contrast break ("Luckily... / Unluckily...") to reset tension.
6. The Explanation: Shift to educational insight using a universally understood everyday analogy.
7. The Consequence: The permanent rule, biological law, or takeaway created by the event.
8. Callback Twist: A concluding line that loops seamlessly back into Beat 1 (The Hook) to trigger automatic re-watches.

STRICT WRITING RULES:
- Keep each line SHORT and punchy: strictly 5 to 9 words per line so the total video is fast-paced!
- NEVER verbally describe what is already visually obvious on screen.
- Write numbers as spoken words ("three", "seventy-four").
- For "caps", split the line into 1-3 word chunks separated by " | ", with ONE word per chunk prefixed by "*" for emphasis.
- Also write a viral Instagram Reel / YouTube Short caption with a strong hook, {cta_text}, and 12 relevant hashtags.
- Also write a short 2-line thumbnail hook ("thumb_line1" and "thumb_line2", 2-4 words each in ALL CAPS) and a short category badge ("thumb_badge").

Return strictly JSON:
{{
  "title": "Short Viral Title",
  "thumb_badge": "🔴 WHAT HAPPENS IF...",
  "thumb_line1": "YOU NEVER",
  "thumb_line2": "SLEEP AGAIN?!",
  "caption": "Full Instagram Reel caption with 12 hashtags",
  "lines": [
    {{"text": "...", "caps": "..."}}
  ]
}}"""


def resolve_script_and_metadata(
    style: str,
    topic: str,
    orig_script: dict,
    script_path: str | Path | None = None,
) -> tuple[dict, dict, str]:
    """
    3-mode script resolution:
      1. --script <path> -> local JSON override (0 HTTP calls)
      2. Direct GEMINI_API_KEY / GEMINI_API_KEYS -> Gemini REST generateContent
      3. Zero-key template fallback -> copied example/script.json (0 HTTP calls)
    """
    merged = dict(orig_script)
    if script_path:
        custom = validate_and_load_script(script_path)
        for key in ("voice", "speed", "lead", "outro", "gap", "music", "sources"):
            if key in custom:
                merged[key] = custom[key]
        merged["title"] = custom.get("title") or topic or orig_script.get("title", "Short")
        merged["lines"] = custom["lines"]
        gen = {
            "title": merged["title"],
            "thumb_badge": custom.get("thumb_badge") or DEFAULT_BADGES.get(style),
            "thumb_line1": custom.get("thumb_line1") or custom.get("hook") or "WAIT UNTIL YOU SEE",
            "thumb_line2": custom.get("thumb_line2") or custom.get("thumb_hook") or "WHAT HAPPENS?!",
            "caption": custom.get("caption", ""),
        }
        return merged, gen, "script_file"

    keys = load_gemini_keys()
    if keys:
        try:
            prompt = _build_script_prompt(style, topic, orig_script)
            gen = call_gemini_json(prompt)
            merged["title"] = gen.get("title") or topic
            merged["lines"] = normalize_script_lines(gen["lines"])
            gen_meta = {
                "title": merged["title"],
                "thumb_badge": gen.get("thumb_badge") or DEFAULT_BADGES.get(style),
                "thumb_line1": gen.get("thumb_line1") or gen.get("hook") or "WAIT UNTIL YOU SEE",
                "thumb_line2": gen.get("thumb_line2") or gen.get("thumb_hook") or "WHAT HAPPENS?!",
                "caption": gen.get("caption", ""),
            }
            return merged, gen_meta, "gemini_api"
        except Exception as e:
            print(f"   ⚠️ Gemini script generation unavailable ({e}); using style template fallback.", flush=True)

    # Mode 3: Zero-key template fallback
    merged["lines"] = normalize_script_lines(orig_script["lines"])
    title = orig_script.get("title") or topic
    gen_meta = {
        "title": title,
        "thumb_badge": DEFAULT_BADGES.get(style, "🔴 WAIT FOR IT..."),
        "thumb_line1": "WAIT UNTIL YOU SEE",
        "thumb_line2": "WHAT HAPPENS?!",
        "caption": "",
    }
    return merged, gen_meta, "template_fallback"


def _has_any_upload_creds() -> bool:
    yt_ok = load_youtube_credentials() is not None
    ig_ok = is_real_secret(os.environ.get("META_PAGE_ACCESS_TOKEN")) and is_real_secret(
        os.environ.get("IG_BUSINESS_ACCOUNT_ID")
    )
    worker_ok = is_real_secret(os.environ.get("AVIDAY_WORKER_URL"))
    return yt_ok or ig_ok or worker_ok


async def generate_and_publish_custom_topic(
    style: str = "auto",
    topic: str = "auto",
    custom_caption: str = "",
    job_id: str = "",
    add_to_pool_only: bool = False,
    existing_youtube_url: str = "",
    script_path: str = "",
    tts_provider: str | None = None,
    voice: str | None = None,
    no_upload: bool = False,
    publish: bool = False,
    dry_run: bool = False,
):
    style, topic = pick_scheduled_style_and_topic(style, topic)
    resolved_provider = resolve_tts_provider(tts_provider)

    if dry_run:
        if script_path:
            loaded = validate_and_load_script(script_path)
            script_source = "script_file"
            script_voice = loaded.get("voice")
            resolved_title = loaded.get("title") or topic
        else:
            ex_path = SKILL_DIR / "styles" / style / "example" / "script.json"
            ex_script = json.loads(ex_path.read_text()) if ex_path.is_file() else {}
            script_voice = ex_script.get("voice")
            script_source = "gemini_api" if load_gemini_keys() else "template_fallback"
            resolved_title = topic if script_source == "gemini_api" else (ex_script.get("title") or topic)

        readiness = check_provider_readiness(
            resolved_provider,
            style=style,
            cli_voice=voice,
            script_voice=script_voice,
            default_mode="auto",
        )
        upload_status = "skipped" if (no_upload or not _has_any_upload_creds()) else "enabled"
        summary = {
            "dry_run": True,
            "style": style,
            "topic": topic,
            "title": resolved_title,
            "script_source": script_source,
            "tts_provider": readiness["provider"],
            "tts_backend": readiness["resolved_backend"],
            "voice": readiness["voice"],
            "credentials_present": readiness["credentials_present"],
            "tts_detail": readiness["detail"],
            "upload": upload_status,
            "publish": bool(publish and not no_upload),
            "projects_dir": str(get_projects_dir()),
            "faceless_home": str(get_faceless_home()),
        }
        print(json.dumps(summary, indent=2), flush=True)
        return summary

    print(f"🎯 Selected Niche: [{style}] | Topic: {topic} | TTS: {resolved_provider}", flush=True)
    slug = f"aviday-custom-{style}-{int(time.time())}"
    projects_dir = get_projects_dir()
    proj_dir = projects_dir / slug
    if proj_dir.exists():
        shutil.rmtree(proj_dir)
    projects_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_DIR / "styles" / style / "example", proj_dir)
    (proj_dir / "renders").mkdir(exist_ok=True)
    (proj_dir / "review").mkdir(exist_ok=True)

    orig_script = json.loads((proj_dir / "script.json").read_text())
    resolved_script, gen, script_source = resolve_script_and_metadata(
        style=style,
        topic=topic,
        orig_script=orig_script,
        script_path=script_path or None,
    )
    print(f"   📝 Script source: {script_source} ({len(resolved_script['lines'])} lines)", flush=True)

    clear_stale_project_data(proj_dir)
    (proj_dir / "script.json").write_text(json.dumps(resolved_script, indent=2))

    # Synthesize narration using selected TTS provider
    synthesize_project_audio(
        proj_dir,
        style=style,
        provider=resolved_provider,
        voice=voice or None,
        default_mode="auto",
    )

    # Apply 0-3 frame (65ms) cognitive anticipation lead on word timestamps
    apply_cognitive_anticipation_lead(proj_dir, lead_sec=0.065)

    # Generate cues and mix audio
    subprocess.run(["node", "tools/capture.mjs", "cues"], cwd=str(proj_dir), check=True)
    py_mix = resolve_python_bin(("numpy", "scipy"))
    subprocess.run([py_mix, "-B", "tools/mix.py", "."], cwd=str(proj_dir), check=True)

    # Render vertical 1080x1920 MP4
    out_mp4 = proj_dir / "renders" / f"{slug}.mp4"
    env = os.environ.copy()
    env.setdefault("FPS", "24")
    subprocess.run(
        ["node", "tools/capture.mjs", "video", str(out_mp4)],
        cwd=str(proj_dir),
        env=env,
        check=True,
    )

    cover_jpg, yt_cover_jpg = extract_cover_thumbnails(
        proj_dir,
        style=style,
        badge=gen.get("thumb_badge"),
        line1=gen.get("thumb_line1", "WAIT UNTIL YOU SEE"),
        line2=gen.get("thumb_line2", "WHAT HAPPENS?!"),
        offset_sec=3.2,
    )

    follow_line = f"Follow @{CHANNEL_HANDLE}!\n\n" if CHANNEL_HANDLE else ""
    spec = {
        "style": style,
        "title": gen.get("title", topic),
        "caption": custom_caption or gen.get("caption") or f"{topic} ✨\n\n{follow_line}#reels #fyp #viral",
    }

    res_data = publish_social_uploads(
        out_mp4,
        spec=spec,
        cover_jpg=cover_jpg,
        yt_cover_jpg=yt_cover_jpg,
        existing_youtube_url=existing_youtube_url,
        add_to_pool_only=add_to_pool_only,
        job_id=job_id,
        no_upload=no_upload,
        publish=publish,
    )
    res_data["project_dir"] = str(proj_dir)
    res_data["script_source"] = script_source
    print(f"🎉 Custom Topic Reel complete: {json.dumps(res_data)}", flush=True)
    return res_data


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Aviday Custom Topic Faceless Reel Generator & Optional Publisher"
    )
    ap.add_argument(
        "--style",
        default="auto",
        help=f"Visual style (auto, {', '.join(STYLES_ALL)})",
    )
    ap.add_argument("--topic", default="auto", help="Reel topic or 'auto'")
    ap.add_argument("--script", default="", help="Path to local script JSON (skips Gemini API)")
    ap.add_argument(
        "--tts-provider",
        default=None,
        help=f"TTS provider ({', '.join(TTS_PROVIDERS)}; default from TTS_PROVIDER env or 'default')",
    )
    ap.add_argument("--voice", default="", help="TTS voice name or ID override")
    ap.add_argument("--no-upload", action="store_true", help="Skip YouTube and Instagram uploads")
    ap.add_argument("--publish", action="store_true", help="Enable publishing when social keys are set")
    ap.add_argument("--dry-run", action="store_true", help="Validate config and print summary without rendering")
    ap.add_argument("--caption", default="", help="Custom social caption")
    ap.add_argument("--job-id", default="", help="Optional Cloudflare Worker job ID")
    ap.add_argument("--existing-youtube-url", default="", help="Reuse existing YouTube Short URL")
    ap.add_argument("--pool", action="store_true", help="Add rendered reel to Worker pool")
    return ap


if __name__ == "__main__":
    ap = build_arg_parser()
    args = ap.parse_args()
    try:
        pick_scheduled_style_and_topic(args.style, args.topic)
        resolve_tts_provider(args.tts_provider)
        if args.dry_run and args.script:
            validate_and_load_script(args.script)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    res = asyncio.run(
        generate_and_publish_custom_topic(
            style=args.style,
            topic=args.topic,
            custom_caption=args.caption,
            job_id=args.job_id,
            add_to_pool_only=args.pool,
            existing_youtube_url=args.existing_youtube_url,
            script_path=args.script,
            tts_provider=args.tts_provider,
            voice=args.voice,
            no_upload=args.no_upload,
            publish=args.publish,
            dry_run=args.dry_run,
        )
    )
    if (
        args.dry_run
        and isinstance(res, dict)
        and res.get("tts_provider") != "default"
        and not res.get("credentials_present")
    ):
        print(f"Error: {res.get('tts_detail', 'Missing TTS credentials/models')}", file=sys.stderr)
        sys.exit(2)
