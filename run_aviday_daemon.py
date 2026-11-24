#!/usr/bin/env python3
"""
Aviday — Fast Poll Booster + On-Demand DM Reel Builder Daemon
1. Triggers $AVIDAY_WORKER_URL/poll every 4s for fast DM responses.
2. Checks $AVIDAY_WORKER_URL/reels/claim for any new Reel topic
   requested by the admin in Instagram DMs (or scheduled every 6 hours), renders it with faceless-shorts,
   and publishes it live!
"""
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

WORKER_BASE = os.environ.get("AVIDAY_WORKER_URL", "").rstrip("/")
if not WORKER_BASE:
    raise SystemExit("Set AVIDAY_WORKER_URL in your environment.")
VENV_PY = str(Path.home() / ".faceless-shorts" / "venv" / "bin" / "python")
CUSTOM_REEL_SCRIPT = str(Path(__file__).resolve().parent / "generate_custom_topic_reel.py")

os.environ["PATH"] = f"{Path.home() / '.local/bin'}:/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

print("🚀 Aviday Fast-Poll + On-Demand DM Reel Builder started ->", WORKER_BASE, flush=True)

tick = 0
while True:
    try:
        req = urllib.request.Request(f"{WORKER_BASE}/poll", headers={"User-Agent": "Aviday-FastPoller/2.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            poll_data = json.loads(r.read().decode("utf-8"))

        # Check if there is a pending Reel job in reelQueue
        queue = poll_data.get("reelQueue") or []
        has_pending = any(j.get("status") == "pending" for j in queue)
        if has_pending and Path(VENV_PY).exists():
            claim_req = urllib.request.Request(
                f"{WORKER_BASE}/reels/claim",
                data=b"{}",
                headers={"Content-Type": "application/json", "User-Agent": "Aviday-ReelBuilder/2.0"},
                method="POST",
            )
            with urllib.request.urlopen(claim_req, timeout=15) as cr:
                claim_data = json.loads(cr.read().decode("utf-8"))
            job = claim_data.get("job")
            if job:
                print(f"🎬 Claimed Reel Job {job['id']}: [{job['style']}] {job['topic']}", flush=True)
                subprocess.run(
                    [
                        VENV_PY,
                        CUSTOM_REEL_SCRIPT,
                        "--style",
                        job.get("style", "deep-dive"),
                        "--topic",
                        job.get("topic", "What happens inside your body when you hold your breath?"),
                        "--caption",
                        job.get("caption", ""),
                        "--job-id",
                        job.get("id", ""),
                    ],
                    check=False,
                )
    except Exception as e:
        print("Poll/Reel check warning:", e, flush=True)

    tick += 1
    time.sleep(4)
