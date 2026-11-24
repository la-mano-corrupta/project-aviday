import json
import os
import ssl
import urllib.request

ctx = ssl._create_unverified_context()
META_TOKEN = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
IG_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
if not META_TOKEN or not IG_ID:
    raise SystemExit("Set META_PAGE_ACCESS_TOKEN and IG_BUSINESS_ACCOUNT_ID in your environment.")

def req_json(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return {"exception": str(e)}

print("=== 1. SUBSCRIBING PAGE TO MESSAGES/WEBHOOKS ===")
sub_url = f"https://graph.facebook.com/v21.0/me/subscribed_apps?subscribed_fields=messages,messaging_postbacks,feed&access_token={META_TOKEN}"
print(json.dumps(req_json(sub_url, method="POST"), indent=2))

print("\n=== 2. CHECKING IG MEDIA & COMMENTS ===")
media_url = f"https://graph.facebook.com/v21.0/{IG_ID}/media?fields=id,caption,comments{{id,text,username,from}}&access_token={META_TOKEN}"
print(json.dumps(req_json(media_url), indent=2))

print("\n=== 3. CHECKING CONVERSATIONS FOLDERS ===")
for folder in ["inbox", "general", "other", "pending"]:
    u = f"https://graph.facebook.com/v21.0/me/conversations?platform=instagram&folder={folder}&access_token={META_TOKEN}"
    print(f"Folder {folder}:", json.dumps(req_json(u)))
