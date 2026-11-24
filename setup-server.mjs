import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { handleIncomingDM } from './src/index.js';

const PORT = 3333;
const DEV_VARS_PATH = path.join(process.cwd(), '.dev.vars');
const GRAPH_BASE = 'https://graph.facebook.com/v21.0';

function loadEnv() {
  const env = {
    META_VERIFY_TOKEN: process.env.META_VERIFY_TOKEN || 'CHANGE_ME_VERIFY_TOKEN',
    ADMIN_IG_ID: 'admin_acc1',
    LOML_IG_ID: 'vip_acc'
  };
  if (fs.existsSync(DEV_VARS_PATH)) {
    const lines = fs.readFileSync(DEV_VARS_PATH, 'utf8').split('\n');
    for (const line of lines) {
      const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
      if (match) {
        env[match[1]] = match[2].replace(/^["']|["']$/g, '').trim();
      }
    }
  }
  return env;
}

function saveEnv(updates) {
  const current = loadEnv();
  const merged = { ...current, ...updates };
  const content = Object.entries(merged)
    .map(([k, v]) => `${k}="${v || ''}"`)
    .join('\n');
  fs.writeFileSync(DEV_VARS_PATH, content + '\n', 'utf8');
  return merged;
}

const HTML_PAGE = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Personal IG Agent — Control & Setup Center</title>
  <style>
    * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { margin: 0; background: #0b0f19; color: #f1f5f9; padding: 28px; }
    .container { max-width: 960px; margin: 0 auto; display: grid; gap: 22px; }
    .card { background: #151c2c; border: 1px solid #26324d; border-radius: 14px; padding: 22px; }
    h1 { margin: 0 0 6px; font-size: 24px; color: #fff; }
    h2 { margin: 0 0 12px; font-size: 18px; color: #60a5fa; }
    p { margin: 6px 0 14px; color: #94a3b8; font-size: 14px; line-height: 1.5; }
    label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; color: #cbd5e1; }
    input, select, textarea {
      width: 100%; padding: 11px 14px; border-radius: 8px; border: 1px solid #334155;
      background: #0f172a; color: #f8fafc; font-size: 14px; margin-bottom: 12px;
    }
    button {
      background: #2563eb; color: #fff; border: none; padding: 11px 18px;
      border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px;
    }
    button:hover { background: #1d4ed8; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
    .ok { background: #065f46; color: #6ee7b7; }
    .warn { background: #78350f; color: #fcd34d; }
    .result-box {
      margin-top: 12px; padding: 12px; border-radius: 8px; background: #0f172a;
      border: 1px solid #334155; font-family: monospace; font-size: 13px; white-space: pre-wrap;
    }
    .sim-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .chat-log {
      height: 290px; overflow-y: auto; background: #090d16; border: 1px solid #26324d;
      border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 10px;
    }
    .bubble { padding: 9px 13px; border-radius: 10px; max-width: 85%; font-size: 13.5px; line-height: 1.4; }
    .bubble.user { background: #2563eb; align-self: flex-end; }
    .bubble.bot { background: #1e293b; border: 1px solid #334155; align-self: flex-start; }
    .role-tag { font-size: 11px; opacity: 0.75; margin-bottom: 3px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h1>🤖 24/7 Personal Instagram Agent — 1-Click Setup & Live Tester</h1>
      <p>No complicated Meta JSON queries needed. Paste your <strong>2-Month Token</strong> below and click the button — this server will automatically extract your <strong>Permanent (Never-Expiring) Page Token</strong> and your <strong>Instagram Business Account ID</strong>!</p>
      <div id="statusBadges">Loading current setup...</div>
    </div>

    <div class="card">
      <h2>Step 1: Convert Your 2-Month Token into a Permanent (Expires: Never) Token</h2>
      <p>Paste the 2-Month token you got when you clicked "Extend Access Token" on Meta:</p>
      <label>Your 2-Month Meta Token (starts with EAA...)</label>
      <input id="twoMonthToken" type="password" placeholder="EAABwzLixnjYBO..." />
      <button onclick="convertMetaToken()">⚡ Auto-Extract Permanent Page Token & IG Account ID</button>
      <div id="metaResult" class="result-box" style="display:none;"></div>
    </div>

    <div class="card">
      <h2>Step 2: Paste Your Free Gemini API Key</h2>
      <p>Get a free API key in 2 clicks from <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#60a5fa;">Google AI Studio (aistudio.google.com/apikey)</a> and paste it here:</p>
      <label>GEMINI_API_KEY (starts with AIza...)</label>
      <input id="geminiKey" type="password" placeholder="AIzaSy..." />
      <button onclick="saveGeminiKey()">💾 Save Gemini API Key</button>
      <div id="geminiResult" class="result-box" style="display:none;"></div>
    </div>

    <div class="card">
      <h2>Step 3: Test Your Running Bot Right Now (3-Tier Identity Simulator)</h2>
      <p>Test how your bot replies when texted by <strong>Your VIP Contact</strong>, <strong>Your Admin Control Account</strong>, or a <strong>Public Follower</strong>:</p>
      <div class="sim-grid">
        <div>
          <label>Send DM As:</label>
          <select id="simRole">
            <option value="vip_acc">❤️ Tier 1: VIP Contact (Highest Priority)</option>
            <option value="admin_acc1">🛠️ Tier 2: Admin Control Center (Sleep/Busy Commands)</option>
            <option value="public_friend_1">🌍 Tier 3: Public Follower / Friend (@friend_1)</option>
          </select>
          <label>Message Text:</label>
          <textarea id="simText" rows="3" placeholder="Try: 'hey' as VIP, or 'going to sleep for 8 hours' as Admin, or 'is the owner awake?' as Public!"></textarea>
          <button onclick="sendSimMessage()">🚀 Send Test DM to Bot</button>
        </div>
        <div>
          <label>Live DM Conversation Feed:</label>
          <div id="chatLog" class="chat-log"></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    async function refreshStatus() {
      const res = await fetch('/api/status');
      const data = await res.json();
      const el = document.getElementById('statusBadges');
      el.innerHTML = \`
        <span class="badge \${data.hasMetaToken ? 'ok' : 'warn'}">Meta Permanent Token: \${data.hasMetaToken ? '✅ Connected' : '⏳ Not Set Yet'}</span>
        <span class="badge \${data.igBusinessId ? 'ok' : 'warn'}">IG Business ID: \${data.igBusinessId ? '✅ ' + data.igBusinessId : '⏳ Not Set Yet'}</span>
        <span class="badge \${data.hasGeminiKey ? 'ok' : 'warn'}">Gemini API Key: \${data.hasGeminiKey ? '✅ Connected' : '⏳ Not Set Yet'}</span>
      \`;
    }

    async function convertMetaToken() {
      const token = document.getElementById('twoMonthToken').value.trim();
      const box = document.getElementById('metaResult');
      box.style.display = 'block';
      box.textContent = '⏳ Calling Meta Graph API to extract your Permanent Page Token & Instagram ID...';
      const res = await fetch('/api/convert-meta-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
      });
      const data = await res.json();
      box.textContent = JSON.stringify(data, null, 2);
      refreshStatus();
    }

    async function saveGeminiKey() {
      const geminiKey = document.getElementById('geminiKey').value.trim();
      const box = document.getElementById('geminiResult');
      box.style.display = 'block';
      const res = await fetch('/api/save-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ GEMINI_API_KEY: geminiKey })
      });
      const data = await res.json();
      box.textContent = data.message || JSON.stringify(data);
      refreshStatus();
    }

    async function sendSimMessage() {
      const senderId = document.getElementById('simRole').value;
      const text = document.getElementById('simText').value.trim();
      if (!text) return;
      const log = document.getElementById('chatLog');
      log.innerHTML += \`<div class="bubble user"><div class="role-tag">You (\${senderId})</div>\${text}</div>\`;
      document.getElementById('simText').value = '';
      log.scrollTop = log.scrollHeight;

      const res = await fetch('/api/sim-dm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ senderId, text })
      });
      const data = await res.json();
      if (data.error) {
        log.innerHTML += \`<div class="bubble bot"><div class="role-tag">⚠️ Error</div>\${data.error}</div>\`;
      } else {
        log.innerHTML += \`<div class="bubble bot"><div class="role-tag">🤖 Bot [\${data.tier}]</div>\${data.reply}</div>\`;
      }
      log.scrollTop = log.scrollHeight;
    }

    refreshStatus();
  </script>
</body>
</html>`;

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname === '/' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(HTML_PAGE);
    return;
  }

  if (url.pathname === '/api/status' && req.method === 'GET') {
    const env = loadEnv();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(
      JSON.stringify({
        hasMetaToken: Boolean(env.META_PAGE_ACCESS_TOKEN),
        igBusinessId: env.IG_BUSINESS_ACCOUNT_ID || null,
        hasGeminiKey: Boolean(env.GEMINI_API_KEY)
      })
    );
    return;
  }

  if (url.pathname === '/api/convert-meta-token' && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) body += chunk;
    try {
      const { token } = JSON.parse(body);
      const pagesUrl = `${GRAPH_BASE}/me/accounts?fields=id,name,access_token,instagram_business_account{id,username,name}&access_token=${encodeURIComponent(token.trim())}`;
      const pagesRes = await fetch(pagesUrl);
      const pagesData = await pagesRes.json();

      if (pagesData.error) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: pagesData.error.message }));
        return;
      }

      if (!pagesData.data || pagesData.data.length === 0) {
        // Fallback: Check if the token pasted is ALREADY a Page Access Token!
        const meUrl = `${GRAPH_BASE}/me?fields=id,name,instagram_business_account{id,username}&access_token=${encodeURIComponent(token.trim())}`;
        const meRes = await fetch(meUrl);
        const meData = await meRes.json();
        if (meData.instagram_business_account?.id) {
          saveEnv({
            META_PAGE_ACCESS_TOKEN: token.trim(),
            IG_BUSINESS_ACCOUNT_ID: meData.instagram_business_account.id
          });
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(
            JSON.stringify({
              ok: true,
              note: 'Token was already a Page Access Token! Saved permanently.',
              pageName: meData.name,
              igUsername: meData.instagram_business_account.username,
              igBusinessId: meData.instagram_business_account.id
            })
          );
          return;
        }

        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            ok: false,
            message:
              'No Facebook Pages found on this token. When you click Generate Access Token in Graph API Explorer, make sure you check the permissions: pages_show_list, pages_messaging, instagram_basic, instagram_manage_messages, instagram_manage_comments.',
            raw: pagesData
          })
        );
        return;
      }

      const linkedPage =
        pagesData.data.find((p) => p.instagram_business_account?.id) || pagesData.data[0];

      saveEnv({
        META_PAGE_ACCESS_TOKEN: linkedPage.access_token,
        IG_BUSINESS_ACCOUNT_ID: linkedPage.instagram_business_account?.id || ''
      });

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(
        JSON.stringify({
          ok: true,
          message: '✅ Permanent (Expires: Never) Page Token & Instagram ID saved!',
          pageName: linkedPage.name,
          pageId: linkedPage.id,
          igUsername: linkedPage.instagram_business_account?.username || 'Not linked',
          igBusinessId: linkedPage.instagram_business_account?.id || null
        })
      );
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, error: err.message }));
    }
    return;
  }

  if (url.pathname === '/api/save-keys' && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) body += chunk;
    const updates = JSON.parse(body);
    saveEnv(updates);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, message: '✅ Saved to .dev.vars!' }));
    return;
  }

  if (url.pathname === '/api/sim-dm' && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) body += chunk;
    try {
      const { senderId, text } = JSON.parse(body);
      const env = loadEnv();
      // For local simulator, don't actually call Meta send message unless real IG IDs
      const simEnv = { ...env, META_PAGE_ACCESS_TOKEN: '' };
      const result = await handleIncomingDM({ env: simEnv, senderId, text });
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  res.writeHead(404);
  res.end('Not Found');
});

server.listen(PORT, () => {
  console.log(`🚀 Setup & Bot Simulator UI running at http://localhost:${PORT}`);
});
