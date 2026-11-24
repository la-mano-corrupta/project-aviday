#!/usr/bin/env python3
"""
Synthesizes millisecond-accurate voiceover into data/narration.wav
matching data/lines.json (or generating new timings via estimate.py/words.py),
runs tools/mix.py, renders the 1080x1920 MP4 via tools/capture.mjs,
and optionally uploads/publishes when credentials are configured!
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from tts_providers import (
    TTS_PROVIDERS,
    check_provider_readiness,
    get_faceless_home,
    get_projects_dir,
    is_real_secret,
    resolve_python_bin,
    resolve_tts_provider,
    synthesize_project_audio,
)

SKILL_DIR = Path(__file__).resolve().parent / "faceless-shorts-skill" / "faceless-shorts"
FACELESS_HOME = get_faceless_home()
PROJECTS_DIR = get_projects_dir()
WORKER_URL = os.environ.get("AVIDAY_WORKER_URL", "").rstrip("/")
CHANNEL_HANDLE = os.environ.get("AVIDAY_HANDLE", "").lstrip("@")
_FOLLOW_PREFIX = f"Follow @{CHANNEL_HANDLE}" if CHANNEL_HANDLE else "Follow"

STYLES_ALL: tuple[str, ...] = (
    "deep-dive",
    "inside-out",
    "night-file",
    "paper-atlas",
    "stick-story",
    "tall-tale",
)

os.environ["PATH"] = (
    f"{Path.home() / '.local/bin'}:/opt/homebrew/bin:/usr/local/bin:"
    + os.environ.get("PATH", "")
)

VOICE_MAP = {
    "deep-dive": "en-US-AndrewNeural",
    "night-file": "en-US-ChristopherNeural",
    "stick-story": "en-US-GuyNeural",
    "tall-tale": "en-US-BrianNeural",
}

REEL_SPECS = [
    {
        "style": "stick-story",
        "slug": "aviday-stick-story",
        "title": "What Would You Do If The Power Went Out For 3 Days?",
        "thumb_badge": "⚠️ SURVIVAL TEST",
        "thumb_line1": "72 HOURS",
        "thumb_line2": "ZERO POWER?!",
        "caption": (
            "If the grid goes dark for 72 hours tonight, do NOT open your fridge first. ⚡🕯️ "
            "Here is the exact 4-step survival playbook that keeps you safe.\n\n"
            f"{_FOLLOW_PREFIX} for daily survival guides & explainers ✨\n\n"
            "#survival #lifehacks #whatwouldyoudo #survivaltips #preparedness "
            "#stickstory #smarttips #emergencyprep #didyouknow #reels #fyp #viral"
        ),
    },
    {
        "style": "deep-dive",
        "slug": "aviday-deep-dive",
        "title": "What Happens If You Hold Your Breath Too Long?",
        "thumb_badge": "🔴 WHAT HAPPENS IF...",
        "thumb_line1": "YOU HOLD YOUR BREATH",
        "thumb_line2": "TOO LONG?!",
        "caption": (
            "What actually happens inside your body when you hold your breath to the limit? 🫁⚡ "
            "Wait until your brain hits the emergency switch...\n\n"
            f"{_FOLLOW_PREFIX} for daily 3D science deep dives ✨\n\n"
            "#whatif #sciencefacts #humanbody #3danimation #deepdive #anatomy "
            "#didyouknow #biology #explainer #reels #viralreels #fyp"
        ),
    },
    {
        "style": "night-file",
        "slug": "aviday-night-file",
        "title": "The Man Who Jumped Out of a Plane and Vanished (Flight 305)",
        "thumb_badge": "🕵️‍♂️ UNSOLVED CASE FILE",
        "thumb_line1": "JUMPED AT 10,000 FT",
        "thumb_line2": "& VANISHED?!",
        "caption": (
            "Nov 24, 1971 — Flight 305. He parachuted into a freezing rainstorm at 10,000 feet "
            "with $200,000 in cash and was never seen again. 🕵️‍♂️✈️ Case File #305: UNSOLVED.\n\n"
            f"{_FOLLOW_PREFIX} for nightly mystery files 📁\n\n"
            "#unsolvedmysteries #truecrime #dbcooper #mystery #nightfile #coldcase "
            "#creepyfacts #historymystery #darkhistory #reels #fyp #viral"
        ),
    },
    {
        "style": "tall-tale",
        "slug": "aviday-tall-tale",
        "title": "In 1914, Parents Legally Mailed Their Daughter to Grandma",
        "thumb_badge": "🤯 BIZARRE TRUE STORY",
        "thumb_line1": "THEY LEGALLY MAILED",
        "thumb_line2": "THEIR BABY?!",
        "caption": (
            "In 1914, stamps were cheaper than a train ticket... so May Pierstorff's parents "
            "checked the parcel post weight limit and mailed her 73 miles to Grandma's house. 📦🚂\n\n"
            f"{_FOLLOW_PREFIX} for wild true stories every day ✨\n\n"
            "#truestory #weirdhistory #historyfacts #talltale #funfacts #storytime "
            "#1914 #didyouknow #animation #reels #fyp #viral"
        ),
    },
]

DEFAULT_BADGES = {
    "deep-dive": "🔴 WHAT HAPPENS IF...",
    "night-file": "🕵️‍♂️ UNSOLVED CASE FILE",
    "stick-story": "⚠️ SURVIVAL TEST",
    "tall-tale": "🤯 BIZARRE TRUE STORY",
    "inside-out": "🧠 INSIDE THE BODY",
    "paper-atlas": "🗺️ UNTOLD HISTORY",
}


async def synthesize_narration(
    proj_dir: Path,
    style: str,
    tts_provider: str | None = None,
    voice: str | None = None,
) -> dict:
    return synthesize_project_audio(
        proj_dir,
        style=style,
        provider=tts_provider,
        voice=voice,
        default_mode="edge",
    )


def upload_to_litterbox(file_path: Path) -> str:
    print(
        f"   ☁️ Uploading {file_path.name} ({file_path.stat().st_size / 1024 / 1024:.2f} MB) for temporary Reels CDN...",
        flush=True,
    )
    res = subprocess.run(
        [
            "curl",
            "-sS",
            "-A",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "-F",
            "reqtype=fileupload",
            "-F",
            "time=72h",
            "-F",
            f"fileToUpload=@{file_path}",
            "https://litterbox.catbox.moe/resources/internals/api.php",
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    url = res.stdout.strip()
    if url.startswith("https://"):
        print(f"   🔗 Hosted URL (Litterbox): {url}", flush=True)
        return url
    raise RuntimeError(
        f"Temporary media upload failed ({res.stderr.strip() or url or 'no URL'}). Set PUBLIC_VIDEO_BASE_URL to self-host MP4s."
    )


def resolve_public_media_url(file_path: Path) -> str | None:
    base_url = os.environ.get("PUBLIC_VIDEO_BASE_URL", "").strip()
    if base_url:
        return f"{base_url.rstrip('/')}/{file_path.name}"
    if os.environ.get("LITTERBOX_UPLOAD", "1").strip() != "0":
        return upload_to_litterbox(file_path)
    return None


def apply_cognitive_anticipation_lead(proj_dir: Path, lead_sec: float = 0.065):
    """
    Shifts visual cues and word-level emphasis timestamps 2 frames (~65ms at 30fps)
    earlier than the spoken audio (0-3 frame cognitive anticipation rule from
    claude-animated-shorts), ensuring visual reactions land right as the brain registers the word.
    """
    words_file = proj_dir / "data" / "words.json"
    if words_file.exists():
        try:
            wdata = json.loads(words_file.read_text())
            words_list = wdata if isinstance(wdata, list) else wdata.get("words", [])
            for w in words_list:
                w["s"] = round(max(0.0, float(w.get("s", 0.0)) - lead_sec), 3)
                w["e"] = round(max(w["s"] + 0.04, float(w.get("e", 0.0)) - lead_sec * 0.5), 3)
            words_file.write_text(json.dumps(wdata, indent=1))
        except Exception as e:
            print(f"   ⚠️ Cognitive lead on words.json skipped: {e}", flush=True)


def extract_cover_thumbnails(
    proj_dir: Path,
    style: str = "deep-dive",
    badge: str | None = None,
    line1: str = "WAIT UNTIL YOU SEE",
    line2: str = "WHAT HAPPENS?!",
    offset_sec: float = 3.2,
) -> tuple[Path | None, Path | None]:
    """Generate local cover_hook.jpg + cover_youtube.jpg in review/ with zero network calls."""
    out_jpg = proj_dir / "review" / "cover_hook.jpg"
    yt_jpg = proj_dir / "review" / "cover_youtube.jpg"
    try:
        thumb_script = Path(__file__).resolve().parent / "render_viral_thumbnail.mjs"
        subprocess.run(
            [
                "node",
                str(thumb_script),
                str(proj_dir),
                str(out_jpg),
                style,
                badge or DEFAULT_BADGES.get(style, "🔴 WAIT FOR IT..."),
                line1,
                line2,
                f"{offset_sec}",
            ],
            cwd=str(proj_dir),
            check=True,
        )
        return (
            out_jpg if out_jpg.exists() else None,
            yt_jpg if yt_jpg.exists() else None,
        )
    except Exception as e:
        print(
            f"   ⚠️ Custom viral thumbnail skipped ({e}); falling back to thumb_offset=2500ms",
            flush=True,
        )
    return None, None


def extract_and_upload_cover(
    proj_dir: Path,
    style: str = "deep-dive",
    badge: str | None = None,
    line1: str = "WAIT UNTIL YOU SEE",
    line2: str = "WHAT HAPPENS?!",
    offset_sec: float = 3.2,
    upload: bool = True,
) -> tuple[str | None, Path | None]:
    cover_jpg, _ = extract_cover_thumbnails(
        proj_dir,
        style=style,
        badge=badge,
        line1=line1,
        line2=line2,
        offset_sec=offset_sec,
    )
    if cover_jpg and cover_jpg.exists() and upload:
        try:
            return resolve_public_media_url(cover_jpg), cover_jpg
        except Exception as e:
            print(f"   ⚠️ Cover upload skipped ({e})", flush=True)
    return None, cover_jpg


def publish_instagram_reel_direct(
    video_url: str,
    caption: str,
    cover_url: str | None = None,
    thumb_offset_ms: int = 2500,
) -> dict:
    token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
    ig_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "").strip()
    if not is_real_secret(token) or not is_real_secret(ig_id):
        return {
            "ok": False,
            "skipped": True,
            "reason": "META_PAGE_ACCESS_TOKEN or IG_BUSINESS_ACCOUNT_ID not configured",
        }

    graph_base = "https://graph.facebook.com/v22.0"
    form: dict[str, str] = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "thumb_offset": str(thumb_offset_ms),
        "share_to_feed": "true",
        "access_token": token,
    }
    if cover_url:
        form["cover_url"] = cover_url

    create_req = urllib.request.Request(
        f"{graph_base}/{urllib.parse.quote(ig_id, safe='')}/media",
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(create_req, timeout=60) as resp:
        created = json.loads(resp.read().decode("utf-8"))
    creation_id = created.get("id")
    if not creation_id:
        raise RuntimeError(f"Meta Graph /media did not return creation id: {created}")

    # Poll container status until FINISHED
    for _ in range(30):
        status_url = (
            f"{graph_base}/{urllib.parse.quote(str(creation_id), safe='')}"
            f"?fields=status_code,status&access_token={urllib.parse.quote(token, safe='')}"
        )
        with urllib.request.urlopen(status_url, timeout=30) as sresp:
            sdata = json.loads(sresp.read().decode("utf-8"))
        code = str(sdata.get("status_code", "")).upper()
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Meta Reel container processing failed: {sdata}")
        time.sleep(3)

    pub_req = urllib.request.Request(
        f"{graph_base}/{urllib.parse.quote(ig_id, safe='')}/media_publish",
        data=urllib.parse.urlencode(
            {"creation_id": str(creation_id), "access_token": token}
        ).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(pub_req, timeout=60) as presp:
        pub = json.loads(presp.read().decode("utf-8"))

    media_id = pub.get("id")
    permalink = None
    if media_id:
        try:
            perm_url = (
                f"{graph_base}/{urllib.parse.quote(str(media_id), safe='')}"
                f"?fields=permalink&access_token={urllib.parse.quote(token, safe='')}"
            )
            with urllib.request.urlopen(perm_url, timeout=20) as p_resp:
                permalink = json.loads(p_resp.read().decode("utf-8")).get("permalink")
        except Exception:
            pass

    return {
        "ok": True,
        "creationId": creation_id,
        "mediaId": media_id,
        "permalink": permalink,
    }


def publish_via_worker(
    video_url: str,
    spec: dict,
    add_to_pool_only: bool = False,
    cover_url: str | None = None,
    youtube_url: str | None = None,
    job_id: str = "",
) -> dict:
    worker = os.environ.get("AVIDAY_WORKER_URL", WORKER_URL).rstrip("/")
    if not worker:
        return {"ok": False, "skipped": True, "reason": "AVIDAY_WORKER_URL not set"}
    payload = json.dumps(
        {
            "videoUrl": video_url,
            "coverUrl": cover_url,
            "youtubeUrl": youtube_url,
            "thumbOffsetMs": 2500,
            "caption": spec["caption"],
            "style": spec["style"],
            "title": spec["title"],
            "jobId": job_id,
            "addToPoolOnly": add_to_pool_only,
            "notifyAdmins": True,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{worker}/reels/publish",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Aviday-Reel-Publisher/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(f"   🎉 Worker /reels/publish result: {json.dumps(data)}", flush=True)
    return data


def publish_social_uploads(
    out_mp4: Path,
    spec: dict,
    cover_jpg: Path | None = None,
    yt_cover_jpg: Path | None = None,
    existing_youtube_url: str = "",
    add_to_pool_only: bool = False,
    job_id: str = "",
    no_upload: bool = False,
    publish: bool = False,
) -> dict:
    """Upload rendered MP4 + covers to YouTube Shorts and/or Instagram Reels when enabled and configured."""
    if no_upload:
        print("   ⏭️ --no-upload enabled: skipping YouTube & Instagram publishing.", flush=True)
        return {
            "ok": True,
            "skipped": True,
            "publish": False,
            "youtube": {"ok": False, "skipped": True, "reason": "--no-upload specified"},
            "instagram": {"ok": False, "skipped": True, "reason": "--no-upload specified"},
            "mp4": str(out_mp4),
            "cover": str(cover_jpg) if cover_jpg else None,
            "youtube_cover": str(yt_cover_jpg) if yt_cover_jpg else None,
        }

    from youtube_shorts_uploader import upload_youtube_short

    style = spec["style"]
    if existing_youtube_url:
        print(f"   📺 Using existing live YouTube Short: {existing_youtube_url}", flush=True)
        yt_res = {"ok": True, "url": existing_youtube_url, "reused": True}
    else:
        yt_res = upload_youtube_short(
            out_mp4,
            title=spec["title"],
            description=spec["caption"],
            style=style,
            cover_jpg=yt_cover_jpg if (yt_cover_jpg and yt_cover_jpg.exists()) else cover_jpg,
        )
        if yt_res.get("skipped"):
            print(f"   ⏭️ YouTube upload skipped: {yt_res.get('reason')}", flush=True)

    youtube_url = yt_res.get("url") if yt_res.get("ok") else None

    meta_token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
    ig_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "").strip()
    worker = os.environ.get("AVIDAY_WORKER_URL", WORKER_URL).rstrip("/")

    ig_res: dict
    if is_real_secret(meta_token) and is_real_secret(ig_id):
        video_url = resolve_public_media_url(out_mp4)
        if not video_url:
            ig_res = {
                "ok": False,
                "skipped": True,
                "reason": "No public video URL resolved (set PUBLIC_VIDEO_BASE_URL or LITTERBOX_UPLOAD=1)",
            }
        else:
            cover_url = None
            if cover_jpg and cover_jpg.exists():
                try:
                    cover_url = resolve_public_media_url(cover_jpg)
                except Exception:
                    cover_url = None
            ig_res = publish_instagram_reel_direct(
                video_url=video_url,
                caption=spec["caption"],
                cover_url=cover_url,
                thumb_offset_ms=2500,
            )
    elif is_real_secret(worker):
        video_url = resolve_public_media_url(out_mp4)
        if not video_url:
            ig_res = {
                "ok": False,
                "skipped": True,
                "reason": "No public video URL resolved for worker publish",
            }
        else:
            cover_url = None
            if cover_jpg and cover_jpg.exists():
                try:
                    cover_url = resolve_public_media_url(cover_jpg)
                except Exception:
                    cover_url = None
            ig_res = publish_via_worker(
                video_url,
                spec,
                add_to_pool_only=add_to_pool_only,
                cover_url=cover_url,
                youtube_url=youtube_url,
                job_id=job_id,
            )
    else:
        print(
            "   ⏭️ Instagram upload skipped: META_PAGE_ACCESS_TOKEN / IG_BUSINESS_ACCOUNT_ID not configured.",
            flush=True,
        )
        ig_res = {
            "ok": False,
            "skipped": True,
            "reason": "META_PAGE_ACCESS_TOKEN or IG_BUSINESS_ACCOUNT_ID not configured",
        }

    return {
        "ok": True,
        "youtube": yt_res,
        "instagram": ig_res,
        "mp4": str(out_mp4),
        "cover": str(cover_jpg) if cover_jpg else None,
        "youtube_cover": str(yt_cover_jpg) if yt_cover_jpg else None,
    }


async def build_and_publish_one(
    spec: dict,
    add_to_pool_only: bool = False,
    tts_provider: str | None = None,
    voice: str | None = None,
    no_upload: bool = False,
    publish: bool = False,
):
    style = spec["style"]
    slug = spec["slug"]
    projects_dir = get_projects_dir()
    proj_dir = projects_dir / slug
    if proj_dir.exists():
        shutil.rmtree(proj_dir)
    projects_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_DIR / "styles" / style / "example", proj_dir)
    (proj_dir / "renders").mkdir(exist_ok=True)
    (proj_dir / "review").mkdir(exist_ok=True)

    print(f"\n🎬 === Building [{style}] -> {spec['title']} ===", flush=True)
    await synthesize_narration(proj_dir, style, tts_provider=tts_provider, voice=voice)
    apply_cognitive_anticipation_lead(proj_dir, lead_sec=0.065)

    # Mix voice + procedural SFX + music bed
    py_mix = resolve_python_bin(("numpy", "scipy"))
    subprocess.run([py_mix, "-B", "tools/mix.py", "."], cwd=str(proj_dir), check=True)

    # Render MP4 via headless Chrome
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
        badge=spec.get("thumb_badge"),
        line1=spec.get("thumb_line1", "WAIT UNTIL YOU SEE"),
        line2=spec.get("thumb_line2", "WHAT HAPPENS?!"),
        offset_sec=3.2,
    )
    return publish_social_uploads(
        out_mp4,
        spec=spec,
        cover_jpg=cover_jpg,
        yt_cover_jpg=yt_cover_jpg,
        add_to_pool_only=add_to_pool_only,
        no_upload=no_upload,
        publish=publish,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Aviday Batch/Preset Faceless Reel Synthesizer & Renderer")
    ap.add_argument("style_pos", nargs="?", default="", help="Optional style filter (e.g. deep-dive)")
    ap.add_argument("--style", default="", help="Filter preset reel by style")
    ap.add_argument(
        "--tts-provider",
        default=None,
        help="TTS provider: default | kokoro | gemini | elevenlabs (or TTS_PROVIDER env)",
    )
    ap.add_argument("--voice", default="", help="Voice name or ID override (or TTS_VOICE env)")
    ap.add_argument("--no-upload", action="store_true", help="Skip YouTube and Instagram uploads")
    ap.add_argument("--publish", action="store_true", help="Attempt social publishing when credentials are set")
    ap.add_argument("--dry-run", action="store_true", help="Validate config and print plan without rendering")
    ap.add_argument("--pool", action="store_true", help="Add rendered reel to Worker 6h pool instead of immediate publish")
    return ap.parse_args(argv)


async def main(argv: list[str] | None = None):
    args = parse_args(argv)
    only_style = (args.style or args.style_pos or "").strip()
    if only_style and only_style not in STYLES_ALL:
        print(
            f"Error: invalid style '{only_style}'. Valid styles: {', '.join(STYLES_ALL)}",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        provider = resolve_tts_provider(args.tts_provider)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    specs = [s for s in REEL_SPECS if not only_style or s["style"] == only_style]
    if not specs and only_style:
        specs = [
            {
                "style": only_style,
                "slug": f"aviday-{only_style}",
                "title": f"Aviday {only_style} Reel",
                "thumb_badge": DEFAULT_BADGES.get(only_style, "🔴 WAIT FOR IT..."),
                "thumb_line1": "WAIT UNTIL YOU SEE",
                "thumb_line2": "WHAT HAPPENS?!",
                "caption": f"{only_style} explainer ✨\n\n#reels #fyp #viral",
            }
        ]

    from youtube_shorts_uploader import load_credentials as load_youtube_credentials

    has_upload_creds = (
        load_youtube_credentials() is not None
        or (
            is_real_secret(os.environ.get("META_PAGE_ACCESS_TOKEN"))
            and is_real_secret(os.environ.get("IG_BUSINESS_ACCOUNT_ID"))
        )
        or is_real_secret(os.environ.get("AVIDAY_WORKER_URL"))
    )
    upload_skipped = bool(args.no_upload) or not has_upload_creds
    if args.dry_run:
        first_style = specs[0]["style"] if specs else "deep-dive"
        readiness = check_provider_readiness(
            provider,
            style=first_style,
            cli_voice=args.voice or None,
            default_mode="edge",
        )
        summary = {
            "dry_run": True,
            "projects_dir": str(get_projects_dir()),
            "faceless_home": str(get_faceless_home()),
            "styles": [s["style"] for s in specs],
            "tts_provider": readiness["provider"],
            "tts_backend": readiness["resolved_backend"],
            "voice": readiness["voice"],
            "credentials_present": readiness["credentials_present"],
            "tts_detail": readiness["detail"],
            "upload": "skipped" if upload_skipped else "enabled",
            "publish": bool(args.publish and not args.no_upload),
            "pool": bool(args.pool),
        }
        print(json.dumps(summary, indent=2), flush=True)
        if provider != "default" and not readiness["credentials_present"]:
            print(f"Error: {readiness['detail']}", file=sys.stderr)
            sys.exit(2)
        return

    for spec in specs:
        await build_and_publish_one(
            spec,
            add_to_pool_only=args.pool,
            tts_provider=provider,
            voice=args.voice or None,
            no_upload=args.no_upload,
            publish=args.publish,
        )


if __name__ == "__main__":
    asyncio.run(main())
