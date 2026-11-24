"""
Upload Direct GraphQL 24/7 Worker to Cloudflare & Trigger Live /poll
"""
import urllib.request
import json
import ssl
import os
import subprocess

ctx = ssl._create_unverified_context()
ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
KV_ID = os.environ.get("CF_KV_NAMESPACE_ID", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
WORKER_URL = os.environ.get("AVIDAY_WORKER_URL", "").rstrip("/")
script_name = os.environ.get("CF_WORKER_NAME", "aviday-agent")
if not all([ACCOUNT_ID, KV_ID, CF_API_TOKEN, WORKER_URL]):
    raise SystemExit("Missing CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, CF_API_TOKEN, or AVIDAY_WORKER_URL.")
worker_file = os.path.join(os.path.dirname(__file__), "cloudflare-worker-24-7.js")
with open(worker_file, "r", encoding="utf-8") as f:
    worker_code = f.read()

boundary = "----AvidayWorkerBoundary987654321"
metadata = json.dumps({
    "main_module": "worker.js",
    "compatibility_date": "2025-01-01",
    "bindings": [
        {
            "type": "kv_namespace",
            "name": "AVIDAY_KV",
            "namespace_id": KV_ID
        }
    ]
})

body_parts = [
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="metadata"; filename="metadata.json"\r\n'
    f"Content-Type: application/json\r\n\r\n"
    f"{metadata}\r\n",
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="worker.js"; filename="worker.js"\r\n'
    f"Content-Type: application/javascript+module\r\n\r\n"
    f"{worker_code}\r\n"
    f"--{boundary}--\r\n"
]
body_bytes = "".join(body_parts).encode("utf-8")

print("1️⃣ Uploading Direct GraphQL 24/7 Worker to Cloudflare...")
req = urllib.request.Request(
    f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/workers/scripts/{script_name}",
    data=body_bytes,
    headers={
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    },
    method="PUT"
)
with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
    up_data = json.loads(r.read().decode("utf-8"))
    print(f"   Upload HTTP {r.status}: success={up_data.get('success')}")

print("\n2️⃣ Triggering /poll on Live Cloudflare Worker...")
out = subprocess.check_output(["/usr/bin/curl", "-s", f"{WORKER_URL}/poll"]).decode("utf-8", errors="ignore")
print(f"   Worker /poll response:\n{out}")
