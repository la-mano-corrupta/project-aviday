#!/usr/bin/env python3
"""
Aviday — Silent OS Background Queue Poller (launchd)
Polls $AVIDAY_WORKER_URL/reels/claim every 20 seconds.
Whenever the admin DMs a Reel topic/story (or the 6-hour scheduler fires),
this daemon claims the job, renders the 3D/2D video + custom viral thumbnail,
and publishes it to Instagram + YouTube Shorts!
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.request
from pathlib import Path

os.environ["PATH"] = f"{Path.home() / '.local/bin'}:/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

from generate_custom_topic_reel import WORKER_URL, generate_and_publish_custom_topic


def claim_next_job() -> dict | None:
    try:
        req = urllib.request.Request(
            f"{WORKER_URL}/reels/claim",
            data=b"{}",
            headers={"Content-Type": "application/json", "User-Agent": "Aviday-Queue-Daemon/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("job")
    except Exception as e:
        print(f"⚠️ Queue poll warning: {e}", flush=True)
        return None


async def run_loop():
    if not WORKER_URL:
        raise SystemExit("Set AVIDAY_WORKER_URL in your environment.")
    print("🚀 Aviday Reel Queue Poller started (checking /reels/claim every 20s)...", flush=True)
    while True:
        job = claim_next_job()
        if job and job.get("topic"):
            print(f"🎬 Claimed Reel Job [{job.get('id')}]: style={job.get('style')} topic={job.get('topic')}", flush=True)
            try:
                await generate_and_publish_custom_topic(
                    style=job.get("style", "deep-dive"),
                    topic=job.get("topic"),
                    custom_caption=job.get("caption", ""),
                    job_id=job.get("id", ""),
                    add_to_pool_only=False,
                )
            except Exception as e:
                print(f"❌ Error rendering job {job.get('id')}: {e}", flush=True)
        await asyncio.sleep(20)


if __name__ == "__main__":
    asyncio.run(run_loop())
