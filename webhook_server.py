#!/usr/bin/env python3
"""Local Meta Webhook receiver for Instagram DMs & comments (standalone env-backed)."""
from __future__ import annotations

import http.server
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "CHANGE_ME_VERIFY_TOKEN")
IG_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
META_TOKEN = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
STATE_FILE = Path(os.environ.get("WEBHOOK_STATE_FILE", ".webhook_state.json"))
PORT = int(os.environ.get("WEBHOOK_PORT", "8765"))

state: dict = {"replied_ids": {}}
if STATE_FILE.is_file():
    try:
        loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            state.update(loaded)
    except Exception:
        pass


def save_state(cur_state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(cur_state, indent=2), encoding="utf-8")
    except Exception:
        pass


def http_json(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
        except Exception:
            err = {"error": str(e)}
        return e.code, err
    except Exception as e:
        return 0, {"error": str(e)}


def generate_response_for_user(sender_id: str, username: str, text: str, is_comment: bool = False) -> str:
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("YOUR_"):
        return "Thanks for reaching out! I will pass your message along."
    prompt = (
        f"You are a helpful Instagram assistant replying to @{username or sender_id}. "
        f"{'Comment' if is_comment else 'DM'}: {text}"
    )
    status, data = http_json(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        method="POST",
        headers={"x-goog-api-key": GEMINI_API_KEY},
        body={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
    )
    if status == 200:
        reply = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        if reply:
            return reply[:900]
    return "Thanks for reaching out! I will pass your message along."


def send_ig_dm(recipient_id: str, text: str) -> tuple[int, dict]:
    if not META_TOKEN or not IG_ID:
        return 0, {"skipped": True, "reason": "META_PAGE_ACCESS_TOKEN or IG_BUSINESS_ACCOUNT_ID unset"}
    url = f"https://graph.facebook.com/v22.0/{IG_ID}/messages?access_token={urllib.parse.quote(META_TOKEN, safe='')}"
    return http_json(url, method="POST", body={"recipient": {"id": recipient_id}, "message": {"text": text}})


def reply_ig_comment(comment_id: str, text: str) -> tuple[int, dict]:
    if not META_TOKEN:
        return 0, {"skipped": True, "reason": "META_PAGE_ACCESS_TOKEN unset"}
    url = f"https://graph.facebook.com/v22.0/{comment_id}/replies?access_token={urllib.parse.quote(META_TOKEN, safe='')}"
    return http_json(url, method="POST", body={"message": text})


def poll_once() -> None:
    worker_url = os.environ.get("AVIDAY_WORKER_URL", "").strip().rstrip("/")
    if worker_url:
        http_json(f"{worker_url}/poll")


def resolve_username(sender_id: str) -> str:
    if not META_TOKEN:
        return ""
    url = f"https://graph.facebook.com/v22.0/{sender_id}?fields=username,name&access_token={urllib.parse.quote(META_TOKEN, safe='')}"
    status, data = http_json(url)
    if status == 200 and data.get("username"):
        return data["username"]
    return ""


def handle_webhook_payload(body: dict) -> None:
    print("⚡ WEBHOOK EVENT RECEIVED:", json.dumps(body), flush=True)
    for entry in body.get("entry", []):
        for event in entry.get("messaging", []):
            msg = event.get("message", {})
            if msg.get("is_echo"):
                continue
            mid = msg.get("mid")
            text = msg.get("text")
            sender_id = event.get("sender", {}).get("id")
            if not sender_id or not text or sender_id == IG_ID:
                continue
            if mid and state["replied_ids"].get(mid):
                continue
            if mid:
                state["replied_ids"][mid] = True
                save_state(state)

            username = resolve_username(sender_id)
            print(f"📩 [WEBHOOK DM] From @{username or sender_id} ({sender_id}): {text}", flush=True)
            reply = generate_response_for_user(sender_id, username, text, is_comment=False)
            send_ig_dm(sender_id, reply)

        for change in entry.get("changes", []):
            val = change.get("value", {})
            if change.get("field") == "comments" and val.get("text") and val.get("id"):
                cid = val["id"]
                from_user = val.get("from", {})
                cuser = from_user.get("username", "")
                bot_handle = os.environ.get("AVIDAY_HANDLE", "").lstrip("@")
                if from_user.get("id") == IG_ID or (bot_handle and cuser == bot_handle):
                    continue
                if state["replied_ids"].get(cid):
                    continue
                state["replied_ids"][cid] = True
                save_state(state)
                print(f"💬 [WEBHOOK COMMENT] From @{cuser}: {val['text']}", flush=True)
                reply = generate_response_for_user(cuser or cid, cuser, f"[Commented on post]: {val['text']}", is_comment=True)
                reply_ig_comment(cid, reply)


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        mode = params.get("hub.mode", [""])[0]
        token = params.get("hub.verify_token", [""])[0]
        challenge = params.get("hub.challenge", [""])[0]

        if mode == "subscribe" and token == VERIFY_TOKEN:
            print(f"✅ Meta Webhook Verified! Challenge: {challenge}", flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(challenge.encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "agent": "Aviday Webhook Server Live"}).encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"EVENT_RECEIVED")
        try:
            body = json.loads(raw)
            threading.Thread(target=handle_webhook_payload, args=(body,), daemon=True).start()
        except Exception as e:
            print("Webhook parse error:", e, flush=True)


def background_poller() -> None:
    while True:
        try:
            poll_once()
        except Exception:
            pass
        time.sleep(5)


if __name__ == "__main__":
    if not META_TOKEN or not IG_ID:
        raise SystemExit("Set META_PAGE_ACCESS_TOKEN and IG_BUSINESS_ACCOUNT_ID before running webhook_server.py")
    threading.Thread(target=background_poller, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"🚀 Aviday Webhook Server listening on http://127.0.0.1:{PORT}/webhook", flush=True)
    server.serve_forever()
