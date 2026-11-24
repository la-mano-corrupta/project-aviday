import json
import os
import ssl
import urllib.parse
import urllib.request

ctx = ssl._create_unverified_context()

META_TOKEN = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
IG_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
if not META_TOKEN or not IG_ID:
    raise SystemExit("Set META_PAGE_ACCESS_TOKEN and IG_BUSINESS_ACCOUNT_ID in your environment.")

def get_json(url):
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return {"exception": str(e)}

print("=== 1. CHECKING PAGE & IG ACCOUNT ===")
print(json.dumps(get_json(f"https://graph.facebook.com/v21.0/me?fields=id,name,instagram_business_account{{id,username}}&access_token={META_TOKEN}"), indent=2))

print("\n=== 2. CHECKING TOKEN SCOPES (debug_token) ===")
print(json.dumps(get_json(f"https://graph.facebook.com/v21.0/debug_token?input_token={META_TOKEN}&access_token={META_TOKEN}"), indent=2))

print("\n=== 3. CHECKING /me/conversations?platform=instagram ===")
print(json.dumps(get_json(f"https://graph.facebook.com/v21.0/me/conversations?platform=instagram&fields=participants,messages.limit(2){{id,from,message,created_time}}&access_token={META_TOKEN}"), indent=2))

print("\n=== 4. CHECKING /{IG_ID}/conversations ===")
print(json.dumps(get_json(f"https://graph.facebook.com/v21.0/{IG_ID}/conversations?platform=instagram&fields=participants,messages.limit(2){{id,from,message,created_time}}&access_token={META_TOKEN}"), indent=2))
