#!/usr/bin/env node
/**
 * Syncs a fresh Instagram web session into both local ig_session.json
 * and an optional 24/7 Cloudflare Worker (/session -> KV), then triggers an immediate /poll.
 *
 * Usage:
 *   node sync_ig_session.mjs --cookie "<sessionid value OR full Cookie header>"
 *   node sync_ig_session.mjs --login   (opens a clean visible Chrome window to log in manually)
 */
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const WORKER_URL = (process.env.AVIDAY_WORKER_URL || '').replace(/\/+$/, '');
const VERIFY_TOKEN = process.env.META_VERIFY_TOKEN || '';
const TARGET_USER_PK = process.env.IG_USER_PK || '';
const CHROME = [
  process.env.CHROME,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].find((p) => p && fs.existsSync(p));

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--login') out.login = true;
    else if (argv[i] === '--cookie' && argv[i + 1]) out.cookie = argv[++i];
    else if (argv[i] === '--help' || argv[i] === '-h') out.help = true;
  }
  return out;
}

function buildCookiePayload(rawInput, extra = {}) {
  const trimmed = String(rawInput || '').trim();
  const base = {
    csrftoken: extra.csrftoken || '',
    ds_user_id: extra.ds_user_id || TARGET_USER_PK,
    ig_did: extra.ig_did || crypto.randomUUID().toUpperCase(),
    mid: extra.mid || '',
    sessionid: extra.sessionid || '',
  };
  if (trimmed.includes('=')) {
    for (const part of trimmed.split(';')) {
      const idx = part.indexOf('=');
      if (idx <= 0) continue;
      const k = part.slice(0, idx).trim();
      const v = part.slice(idx + 1).trim();
      if (k in base && v) base[k] = v;
    }
  } else if (trimmed) {
    base.sessionid = trimmed;
  }
  if (!base.sessionid) throw new Error('Missing sessionid value.');
  const cookieHeader = Object.entries(base)
    .filter(([, v]) => Boolean(v))
    .map(([k, v]) => `${k}=${v}`)
    .join('; ');
  return { ...base, cookieHeader, csrf: base.csrftoken, deviceId: base.ig_did };
}

async function pushToWorker(sessionObj) {
  fs.writeFileSync(path.join(ROOT, 'ig_session.json'), JSON.stringify(sessionObj, null, 2));
  if (!WORKER_URL || !VERIFY_TOKEN) {
    console.log('Saved ig_session.json locally. Set AVIDAY_WORKER_URL and META_VERIFY_TOKEN to push to Worker.');
    return;
  }
  const res = await fetch(`${WORKER_URL}/session`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-verify-token': VERIFY_TOKEN,
    },
    body: JSON.stringify(sessionObj),
  });
  const data = await res.json();
  console.log('Worker /session response:', JSON.stringify(data, null, 2));
  if (!data.ok) process.exitCode = 1;
}

async function captureViaVisibleChrome() {
  if (!CHROME) throw new Error('Google Chrome not found.');
  const profDir = path.join(ROOT, '.chrome-profile');
  fs.mkdirSync(profDir, { recursive: true });
  const portFile = path.join(profDir, 'DevToolsActivePort');
  if (fs.existsSync(portFile)) fs.unlinkSync(portFile);
  const chrome = spawn(
    CHROME,
    [
      '--remote-debugging-port=0',
      `--user-data-dir=${profDir}`,
      '--no-first-run',
      '--no-default-browser-check',
      'https://www.instagram.com/direct/inbox/',
    ],
    { stdio: 'ignore' }
  );

  // Wait for DevToolsActivePort written by Chrome
  let wsUrl = '';
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 250));
    if (fs.existsSync(portFile)) {
      const [port] = fs.readFileSync(portFile, 'utf8').trim().split('\n');
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((p) => p.type === 'page') || list[0];
      if (page?.webSocketDebuggerUrl) {
        wsUrl = page.webSocketDebuggerUrl;
        break;
      }
    }
  }
  if (!wsUrl) throw new Error('Could not attach to Chrome DevTools WebSocket.');

  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let msgId = 0;
  const cdp = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++msgId;
      const onMsg = (ev) => {
        const d = JSON.parse(ev.data);
        if (d.id === id) {
          ws.removeEventListener('message', onMsg);
          d.error ? reject(new Error(d.error.message)) : resolve(d.result);
        }
      };
      ws.addEventListener('message', onMsg);
      ws.send(JSON.stringify({ id, method, params }));
    });

  console.log('Waiting for Instagram login & /direct/inbox/ in Chrome (up to 5 mins)...');
  for (let i = 0; i < 300; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    const { cookies } = await cdp('Network.getCookies', { urls: ['https://www.instagram.com'] });
    const byName = Object.fromEntries((cookies || []).map((c) => [c.name, c.value]));
    if (byName.sessionid && (!TARGET_USER_PK || byName.ds_user_id === TARGET_USER_PK) && byName.csrftoken) {
      await new Promise((r) => setTimeout(r, 2000));
      const { cookies: fresh } = await cdp('Network.getCookies', { urls: ['https://www.instagram.com'] });
      const freshByName = Object.fromEntries((fresh || []).map((c) => [c.name, c.value]));
      const evalRes = await cdp('Runtime.evaluate', {
        expression: `(() => ({ url: location.href, lsd: typeof require === 'function' ? (require('LSD')?.token || '') : '', dtsg: typeof require === 'function' ? (require('DTSGInitialData')?.token || '') : '' }))()`,
        returnByValue: true,
      }).catch(() => null);
      const info = evalRes?.result?.value || {};
      if (info.url && info.url.includes('/accounts/login')) continue;
      const payload = buildCookiePayload('', freshByName);
      if (info.lsd) payload.lsd = info.lsd;
      if (info.dtsg) payload.dtsg = info.dtsg;
      console.log('Captured authenticated cookies for ds_user_id', freshByName.ds_user_id);
      await pushToWorker(payload);
      ws.close();
      chrome.kill('SIGTERM');
      return;
    }
  }
  chrome.kill('SIGTERM');
  throw new Error('Timed out waiting for Instagram login.');
}

const args = parseArgs(process.argv.slice(2));
if (args.help || (!args.cookie && !args.login)) {
  console.log('Usage:\n  node sync_ig_session.mjs --cookie "<sessionid>"\n  node sync_ig_session.mjs --login');
} else if (args.cookie) {
  await pushToWorker(buildCookiePayload(args.cookie));
} else if (args.login) {
  await captureViaVisibleChrome();
}
