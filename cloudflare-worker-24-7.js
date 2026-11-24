/**
 * ============================================================================
 * PERSONAL INSTAGRAM AGENT — 24/7 CLOUDFLARE WORKER (GRAPHQL + WEBHOOK + KV)
 * ============================================================================
 * Runs 24/7 on Cloudflare Workers (optional Direct GraphQL + Meta Webhook).
 * Configure all secrets via `npx wrangler secret put <KEY>` or `.dev.vars`.
 * ============================================================================
 */

function parseGeminiKeys(env) {
  const keys = [];
  if (env?.GEMINI_API_KEYS) {
    keys.push(...String(env.GEMINI_API_KEYS).split(/[\n,]+/).map((k) => k.trim()));
  }
  if (env?.GEMINI_API_KEY) {
    keys.push(...String(env.GEMINI_API_KEY).split(/[\n,]+/).map((k) => k.trim()));
  }
  for (let i = 1; i <= 7; i++) {
    if (env?.[`GEMINI_API_KEY_${i}`]) {
      keys.push(String(env[`GEMINI_API_KEY_${i}`]).trim());
    }
  }
  return [...new Set(keys.filter(Boolean))];
}

function getConfig(env = {}) {
  return {
    OWNER_NAME: env.OWNER_NAME || 'Owner',
    AGENT_NAME: env.AGENT_NAME || 'Aviday',
    VIP_NAME: env.VIP_NAME || 'VIP',
    IG_USERNAME: env.IG_USERNAME || 'your_ig_username',
    IG_PASSWORD: env.IG_PASSWORD || '',
    IG_USER_PK: env.IG_USER_PK || '',
    IG_INTEROP_FBID: env.IG_INTEROP_FBID || '',
    IG_BUSINESS_ACCOUNT_ID: env.IG_BUSINESS_ACCOUNT_ID || '',
    FB_PAGE_ID: env.FB_PAGE_ID || '',
    META_PAGE_ACCESS_TOKEN: env.META_PAGE_ACCESS_TOKEN || '',
    META_VERIFY_TOKEN: env.META_VERIFY_TOKEN || '',
    GROQ_API_KEY: env.GROQ_API_KEY || '',

    // Admin & Tier 1 VIP identifiers (configured via env / secrets):
    ADMIN_1_USERNAME: env.ADMIN_1_USERNAME || '',
    ADMIN_1_PK: env.ADMIN_1_PK || env.ADMIN_IG_ID || '',
    ADMIN_1_THREAD_IGID: env.ADMIN_1_THREAD_IGID || '',
    ADMIN_2_USERNAME: env.ADMIN_2_USERNAME || '',
    ADMIN_2_PK: env.ADMIN_2_PK || env.ADMIN_2_IG_ID || '',
    ADMIN_2_THREAD_IGID: env.ADMIN_2_THREAD_IGID || '',
    LOML_USERNAME: env.LOML_USERNAME || '',

    // Optional initial Instagram Session (persisted in AVIDAY_KV once synced via /session):
    DEFAULT_IG_SESSION: {
      cookieHeader: env.IG_COOKIE_HEADER || '',
      csrf: env.IG_CSRF_TOKEN || '',
      dtsg: env.IG_DTSG_TOKEN || '',
      lsd: env.IG_LSD_TOKEN || '',
      deviceId: env.IG_DEVICE_ID || ''
    },

    GEMINI_KEYS: parseGeminiKeys(env),

    YOUTUBE_OAUTH: {
      channelId: env.YOUTUBE_CHANNEL_ID || '',
      channelHandle: env.YOUTUBE_CHANNEL_HANDLE || '',
      channelUrl: env.YOUTUBE_CHANNEL_URL || '',
      clientId: env.YOUTUBE_CLIENT_ID || '',
      clientSecret: env.YOUTUBE_CLIENT_SECRET || '',
      refreshToken: env.YOUTUBE_REFRESH_TOKEN || ''
    },

    DEFAULT_GITHUB_CONFIG: {
      repo: env.GITHUB_REPO || '',
      token: env.GITHUB_TOKEN || '',
      workflow: env.GITHUB_WORKFLOW || 'faceless-reels.yml',
      branch: env.GITHUB_BRANCH || 'main'
    }
  };
}

const UA_WEB = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const REEL_CATEGORIES = ['deep-dive', 'night-file', 'stick-story', 'tall-tale'];
const SIX_HOURS_MS = 6 * 60 * 60 * 1000;

const INITIAL_PUBLISHED_REELS = [];

const cloudState = {
  roundRobinIdx: 0,
  keyUsage60s: { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: [] },
  statusMode: 'online',
  statusMessage: 'Online and hanging out',
  availableAt: null,
  extraNotes: '',
  lastLomlAlertAt: 0,
  igSession: { cookieHeader: '', csrf: '', dtsg: '', lsd: '', deviceId: '' },
  igSessionValid: false,
  lastSessionError: null,
  lastSessionErrorLoggedAt: 0,
  repliedMessageIds: new Set(),
  repliedCommentIds: new Set(),
  userMemories: new Map(),
  chatHistories: new Map(),
  activeThreads: [],
  lastReelPublishedAt: 0,
  nextCategoryIdx: 0,
  reelQueue: [],
  readyReelsPool: [],
  publishedReels: [...INITIAL_PUBLISHED_REELS],
  githubConfig: { repo: '', token: '', workflow: 'faceless-reels.yml', branch: 'main' },
  recentEvents: []
};

async function loadGlobalState(env, config) {
  if (config?.DEFAULT_IG_SESSION?.cookieHeader && !cloudState.igSession.cookieHeader) {
    cloudState.igSession = { ...config.DEFAULT_IG_SESSION };
    cloudState.igSessionValid = Boolean(config.DEFAULT_IG_SESSION.cookieHeader);
  }
  if (config?.DEFAULT_GITHUB_CONFIG?.repo && !cloudState.githubConfig.repo) {
    cloudState.githubConfig = { ...config.DEFAULT_GITHUB_CONFIG };
  }
  if (!env?.AVIDAY_KV) return;
  try {
    const raw = await env.AVIDAY_KV.get('GLOBAL_STATE_V2');
    if (!raw) return;
    const data = JSON.parse(raw);
    if (data.statusMode) cloudState.statusMode = data.statusMode;
    if (data.statusMessage) cloudState.statusMessage = data.statusMessage;
    cloudState.availableAt = data.availableAt || null;
    cloudState.extraNotes = data.extraNotes || '';
    cloudState.lastLomlAlertAt = data.lastLomlAlertAt || 0;
    if (data.igSession?.cookieHeader && data.igSession?.dtsg) {
      cloudState.igSession = data.igSession;
    }
    if (typeof data.igSessionValid === 'boolean') {
      cloudState.igSessionValid = data.igSessionValid;
    }
    cloudState.lastSessionError = data.lastSessionError || null;
    cloudState.lastSessionErrorLoggedAt = Number(data.lastSessionErrorLoggedAt || 0);
    if (Array.isArray(data.repliedMessageIds)) {
      for (const id of data.repliedMessageIds) cloudState.repliedMessageIds.add(id);
    }
    if (Array.isArray(data.repliedCommentIds)) {
      for (const id of data.repliedCommentIds) cloudState.repliedCommentIds.add(id);
    }
    if (data.userMemories && typeof data.userMemories === 'object') {
      for (const [k, v] of Object.entries(data.userMemories)) cloudState.userMemories.set(k, v);
    }
    if (data.chatHistories && typeof data.chatHistories === 'object') {
      for (const [k, v] of Object.entries(data.chatHistories)) {
        if (Array.isArray(v)) {
          cloudState.chatHistories.set(
            k,
            v.map((m) => ({
              role: m.role,
              content: m.role === 'assistant' ? stripJsonWrapper(m.content) : m.content
            }))
          );
        }
      }
    }
    if (Array.isArray(data.activeThreads)) {
      cloudState.activeThreads = data.activeThreads;
    }
    cloudState.lastReelPublishedAt = Number(data.lastReelPublishedAt || 0);
    cloudState.nextCategoryIdx = Number(data.nextCategoryIdx || 0) % 4;
    if (Array.isArray(data.reelQueue)) {
      cloudState.reelQueue = data.reelQueue.slice(-20);
    }
    if (Array.isArray(data.readyReelsPool)) cloudState.readyReelsPool = data.readyReelsPool;
    if (Array.isArray(data.publishedReels) && data.publishedReels.length > 0) {
      const cleaned = data.publishedReels;
      const seen = new Set(cleaned.map((r) => r.mediaId));
      cloudState.publishedReels = [
        ...cleaned,
        ...INITIAL_PUBLISHED_REELS.filter((r) => !seen.has(r.mediaId))
      ];
    } else {
      cloudState.publishedReels = [...INITIAL_PUBLISHED_REELS];
    }
    if (data.githubConfig) cloudState.githubConfig = data.githubConfig;
    if (Array.isArray(data.recentEvents)) {
      cloudState.recentEvents = data.recentEvents.filter((e) => e.type !== 'reel_job_enqueued').slice(0, 35);
    }
  } catch {}
}

async function saveGlobalState(env) {
  if (!env?.AVIDAY_KV) return;
  try {
    const payload = {
      statusMode: cloudState.statusMode,
      statusMessage: cloudState.statusMessage,
      availableAt: cloudState.availableAt,
      extraNotes: cloudState.extraNotes,
      lastLomlAlertAt: cloudState.lastLomlAlertAt,
      igSession: cloudState.igSession,
      igSessionValid: cloudState.igSessionValid,
      lastSessionError: cloudState.lastSessionError,
      lastSessionErrorLoggedAt: cloudState.lastSessionErrorLoggedAt,
      repliedMessageIds: Array.from(cloudState.repliedMessageIds).slice(-300),
      repliedCommentIds: Array.from(cloudState.repliedCommentIds).slice(-300),
      userMemories: Object.fromEntries(cloudState.userMemories),
      chatHistories: Object.fromEntries(cloudState.chatHistories),
      activeThreads: cloudState.activeThreads,
      lastReelPublishedAt: cloudState.lastReelPublishedAt,
      nextCategoryIdx: cloudState.nextCategoryIdx,
      reelQueue: cloudState.reelQueue.slice(-30),
      readyReelsPool: cloudState.readyReelsPool.slice(-20),
      publishedReels: cloudState.publishedReels.slice(0, 40),
      githubConfig: cloudState.githubConfig,
      recentEvents: cloudState.recentEvents.slice(0, 40)
    };
    await env.AVIDAY_KV.put('GLOBAL_STATE_V2', JSON.stringify(payload));
  } catch {}
}

function logEvent(type, detail) {
  cloudState.recentEvents.unshift({
    ts: new Date().toISOString(),
    type,
    detail
  });
  if (cloudState.recentEvents.length > 40) {
    cloudState.recentEvents.length = 40;
  }
}

function getKeyLoad60s(idx) {
  const now = Date.now();
  cloudState.keyUsage60s[idx] = (cloudState.keyUsage60s[idx] || []).filter((t) => now - t < 60000);
  return cloudState.keyUsage60s[idx].length;
}

function recordKeyCall(idx) {
  const now = Date.now();
  cloudState.keyUsage60s[idx] = (cloudState.keyUsage60s[idx] || []).filter((t) => now - t < 60000);
  cloudState.keyUsage60s[idx].push(now);
}

function stripJsonWrapper(text) {
  if (!text) return '';
  let s = String(text).trim();
  if (s.startsWith('{') || s.includes('"updated_memory"') || /"reply"\s*:/.test(s)) {
    const m = s.match(/"reply"\s*:\s*"([\s\S]*?)"\s*(?:,\s*"(?:updated_memory|action|status_mode|status_message|duration_hours|note_to_add|style|topic|caption)"|\s*\})/);
    if (m && m[1]) {
      s = m[1].replace(/\\n/g, '\n').replace(/\\"/g, '"').trim();
    }
  }
  return s;
}

function safeParseJson(rawText) {
  if (!rawText) return { reply: 'heyy! wsp?' };
  const cleaned = String(rawText)
    .replace(/^```json\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/```\s*$/i, '')
    .trim();

  // 1. Standard JSON.parse
  try {
    const obj = JSON.parse(cleaned);
    if (obj && typeof obj === 'object') {
      if (obj.reply) obj.reply = stripJsonWrapper(obj.reply);
      return obj;
    }
  } catch {}

  // 2. Try extracting {...} block and escaping literal newlines inside string values
  const blockMatch = cleaned.match(/\{[\s\S]*\}/);
  const candidate = blockMatch ? blockMatch[0] : cleaned;
  try {
    const fixedNewlines = candidate.replace(/"((?:\\.|[^"\\])*)"/g, (full) =>
      full.replace(/\r?\n/g, '\\n').replace(/\t/g, '\\t')
    );
    const obj = JSON.parse(fixedNewlines);
    if (obj && typeof obj === 'object') {
      if (obj.reply) obj.reply = stripJsonWrapper(obj.reply);
      return obj;
    }
  } catch {}

  // 3. Regex fallback for malformed JSON (e.g. unescaped quotes or literal newlines inside "reply")
  const out = {};
  const replyMatch = candidate.match(
    /"reply"\s*:\s*"([\s\S]*?)"\s*(?:,\s*"(?:updated_memory|action|status_mode|status_message|duration_hours|note_to_add|style|topic|caption)"|\s*\})/
  );
  if (replyMatch) {
    out.reply = replyMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"').trim();
  }
  const memMatch = candidate.match(/"updated_memory"\s*:\s*"([\s\S]*?)"\s*(?:,|\s*\})/);
  if (memMatch) {
    out.updated_memory = memMatch[1].replace(/\\n/g, ' ').replace(/\\"/g, '"').trim();
  }
  const actionMatch = candidate.match(/"action"\s*:\s*"([^"]+)"/);
  if (actionMatch) out.action = actionMatch[1];
  const styleMatch = candidate.match(/"style"\s*:\s*"([^"]+)"/);
  if (styleMatch) out.style = styleMatch[1];
  const topicMatch = candidate.match(/"topic"\s*:\s*"([^"]+)"/);
  if (topicMatch) out.topic = topicMatch[1];

  if (out.reply) return out;
  return { reply: stripJsonWrapper(cleaned) };
}

function getStatusSummary(config) {
  const owner = config?.OWNER_NAME || 'Owner';
  if (cloudState.statusMode !== 'online' && cloudState.availableAt) {
    const rem = cloudState.availableAt - Date.now();
    if (rem <= 0) {
      cloudState.statusMode = 'online';
      cloudState.statusMessage = 'Online and available';
      cloudState.availableAt = null;
      return `${owner} is awake and online right now.`;
    }
    const mins = Math.ceil(rem / 60000);
    const hrs = Math.floor(mins / 60);
    const m = mins % 60;
    const timeStr =
      hrs > 0
        ? `about ${hrs} hour${hrs > 1 ? 's' : ''}${m > 10 ? ` and ${m} mins` : ''}`
        : `about ${m} minutes`;
    return `${owner} is currently ${cloudState.statusMessage} (${cloudState.statusMode}) and will be back online in ${timeStr}.`;
  }
  return `${owner} is online/around right now.`;
}

async function callAI(sysPrompt, history, isVipLoml = false, config) {
  const keys = config?.GEMINI_KEYS || [];
  const totalKeys = keys.length;
  if (totalKeys === 0) {
    return { reply: 'No GEMINI_API_KEY configured in Worker secrets.' };
  }
  const baseStart = (cloudState.roundRobinIdx = (cloudState.roundRobinIdx + 1) % totalKeys);

  const orderedIndices = Array.from({ length: totalKeys }, (_, offset) => (baseStart + offset) % totalKeys)
    .sort((a, b) => getKeyLoad60s(a) - getKeyLoad60s(b));

  const modelsToTry = isVipLoml
    ? ['gemini-2.5-flash', 'gemini-3.6-flash']
    : ['gemini-2.5-flash', 'gemini-3.6-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'];

  for (const model of modelsToTry) {
    for (const idx of orderedIndices) {
      recordKeyCall(idx);
      try {
        const res = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(keys[idx])}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              systemInstruction: { parts: [{ text: sysPrompt }] },
              contents: history.map((m) => ({
                role: m.role === 'assistant' ? 'model' : 'user',
                parts: [{ text: m.content }]
              })),
              generationConfig: { temperature: 0.85, responseMimeType: 'application/json' }
            })
          }
        );
        if (res.ok) {
          const data = await res.json();
          const raw = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
          const parsed = safeParseJson(raw);
          parsed._model = model;
          parsed._key = idx + 1;
          return parsed;
        }
      } catch {}
    }
  }
  return { reply: 'heyy! gimme one sec lol' };
}

/**
 * Instagram Direct GraphQL Caller + Auto-Session Refresh
 */
function parseCookieMap(cookieHeader) {
  const map = {};
  for (const part of String(cookieHeader || '').split(';')) {
    const idx = part.indexOf('=');
    if (idx <= 0) continue;
    const k = part.slice(0, idx).trim();
    const v = part.slice(idx + 1).trim();
    if (k && v) map[k] = v;
  }
  return map;
}

function mergeSetCookiesIntoHeader(existingHeader, res) {
  const cookieMap = parseCookieMap(existingHeader);
  const setCookies = res?.headers?.getSetCookie ? res.headers.getSetCookie() : [];
  for (const sc of setCookies) {
    const first = sc.split(';')[0];
    const idx = first.indexOf('=');
    if (idx <= 0) continue;
    const k = first.slice(0, idx).trim();
    const v = first.slice(idx + 1).trim();
    if (k && v && v !== '""') cookieMap[k] = v;
  }
  const mergedHeader = Object.entries(cookieMap)
    .map(([k, v]) => `${k}=${v}`)
    .join('; ');
  return { cookieMap, mergedHeader };
}

function markSessionError(reason, forceLog = false) {
  const wasValid = cloudState.igSessionValid;
  cloudState.igSessionValid = false;
  cloudState.lastSessionError = String(reason);
  const now = Date.now();
  const shouldLog = wasValid || forceLog || now - (cloudState.lastSessionErrorLoggedAt || 0) > 15 * 60 * 1000;
  if (shouldLog) {
    cloudState.lastSessionErrorLoggedAt = now;
    logEvent('ig_session_expired', { reason: String(reason) });
    return true;
  }
  return false;
}

async function refreshIgTokensFromInboxPage(config) {
  if (!cloudState.igSession?.cookieHeader) {
    markSessionError('No IG session cookie configured');
    return false;
  }
  try {
    const res = await fetch('https://www.instagram.com/direct/inbox/', {
      redirect: 'manual',
      headers: {
        'User-Agent': UA_WEB,
        'Cookie': cloudState.igSession.cookieHeader,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
      }
    });
    if (res.status >= 300 && res.status < 400) {
      const loc = res.headers.get('location') || '';
      markSessionError(`Inbox HTTP ${res.status} redirect to ${loc || 'login'} (sessionid invalidated)`);
      return false;
    }
    if (!res.ok) {
      markSessionError(`Inbox HTTP ${res.status}`);
      return false;
    }
    const html = await res.text();
    const isLoggedInHtml =
      ((config?.IG_USER_PK && (html.includes(config.IG_USER_PK) || html.includes(`"viewerId":"${config.IG_USER_PK}"`))) || html.includes('"viewer":')) &&
      !html.includes('"loginForm"');
    if (!isLoggedInHtml) {
      markSessionError('Inbox HTML returned logged-out login page (sessionid expired/revoked)');
      return false;
    }
    const { cookieMap, mergedHeader } = mergeSetCookiesIntoHeader(cloudState.igSession.cookieHeader, res);
    if (mergedHeader) cloudState.igSession.cookieHeader = mergedHeader;
    if (cookieMap.csrftoken) cloudState.igSession.csrf = cookieMap.csrftoken;
    const lsdMatch = html.match(/"LSD",\[\],\{"token":"([^"]+)"\}/);
    const dtsgMatch = html.match(/"DTSGInitialData",\[\],\{"token":"([^"]+)"\}/);
    if (lsdMatch && dtsgMatch) {
      cloudState.igSession.lsd = lsdMatch[1];
      cloudState.igSession.dtsg = dtsgMatch[1];
      cloudState.igSessionValid = true;
      cloudState.lastSessionError = null;
      logEvent('ig_tokens_refreshed', { lsd: lsdMatch[1] });
      return true;
    }
    markSessionError('Could not extract LSD/DTSG tokens from authenticated inbox HTML');
  } catch (e) {
    markSessionError(`refreshIgTokens error: ${String(e)}`);
  }
  return false;
}

async function reloginInstagramWithPassword(config) {
  if (!config?.IG_USERNAME || !config?.IG_PASSWORD) return false;
  try {
    const ts = Math.floor(Date.now() / 1000);
    const csrf = cloudState.igSession.csrf || '';
    const body = new URLSearchParams({
      enc_password: `#PWD_INSTAGRAM_BROWSER:0:${ts}:${config.IG_PASSWORD}`,
      username: config.IG_USERNAME,
      queryParams: '{}',
      optIntoOneTap: 'false',
      trustedDeviceRecords: '{}'
    });
    const res = await fetch('https://www.instagram.com/api/v1/web/accounts/login/ajax/', {
      method: 'POST',
      headers: {
        'User-Agent': UA_WEB,
        'Cookie': cloudState.igSession.cookieHeader,
        'X-CSRFToken': csrf,
        'X-IG-App-ID': '936619743392459',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.instagram.com/accounts/login/',
        'Origin': 'https://www.instagram.com',
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: body.toString()
    });
    const loginJson = await res.json().catch(() => null);
    const { cookieMap, mergedHeader } = mergeSetCookiesIntoHeader(cloudState.igSession.cookieHeader, res);
    const prevSid = parseCookieMap(cloudState.igSession.cookieHeader).sessionid;
    const gotFreshSession = Boolean(loginJson?.authenticated && cookieMap.sessionid && cookieMap.sessionid !== prevSid);
    if (!res.ok || !loginJson?.authenticated) {
      const reason = `Auto-relogin rejected (HTTP ${res.status}, authenticated=${loginJson?.authenticated}, message=${loginJson?.message || loginJson?.checkpoint_url || 'none'})`;
      markSessionError(reason);
      logEvent('ig_auto_relogin_failed', { status: res.status, authenticated: Boolean(loginJson?.authenticated), checkpoint: Boolean(loginJson?.checkpoint_url), message: loginJson?.message || null });
      return false;
    }
    cloudState.igSession.cookieHeader = mergedHeader;
    if (cookieMap.csrftoken) cloudState.igSession.csrf = cookieMap.csrftoken;
    const inboxOk = await refreshIgTokensFromInboxPage(config);
    logEvent('ig_auto_relogin_complete', { authenticated: true, gotFreshSession, inboxOk });
    return inboxOk;
  } catch (e) {
    markSessionError(`ig_auto_relogin_error: ${String(e)}`);
    logEvent('ig_auto_relogin_error', { error: String(e) });
    return false;
  }
}

async function callInstagramGraphQL(friendlyName, docId, variables, isRetry = false, config) {
  const sess = cloudState.igSession;
  if (!sess?.cookieHeader || !sess?.dtsg || !sess?.lsd) {
    return { _sessionError: 'IG session not configured' };
  }
  const body = new URLSearchParams({
    av: config?.IG_BUSINESS_ACCOUNT_ID || '',
    __user: '0',
    __a: '1',
    fb_dtsg: sess.dtsg,
    lsd: sess.lsd,
    fb_api_caller_class: 'RelayModern',
    fb_api_req_friendly_name: friendlyName,
    variables: JSON.stringify(variables),
    server_timestamps: 'true',
    doc_id: docId
  });

  try {
    const res = await fetch('https://www.instagram.com/api/graphql', {
      method: 'POST',
      redirect: 'manual',
      headers: {
        'User-Agent': UA_WEB,
        'Cookie': sess.cookieHeader,
        'X-CSRFToken': sess.csrf,
        'X-IG-App-ID': '936619743392459',
        'X-FB-LSD': sess.lsd,
        'X-FB-Friendly-Name': friendlyName,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': '*/*',
        'Origin': 'https://www.instagram.com',
        'Referer': 'https://www.instagram.com/direct/inbox/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin'
      },
      body: body.toString()
    });

    if (res.status >= 300 && res.status < 400) {
      if (!isRetry) {
        const refreshed = await refreshIgTokensFromInboxPage(config);
        if (refreshed) return callInstagramGraphQL(friendlyName, docId, variables, true, config);
      }
      return { _sessionError: `GraphQL HTTP ${res.status} redirect (sessionid invalidated)` };
    }

    let raw = await res.text();
    if (raw.startsWith('for (;;);')) raw = raw.slice(9);
    let json = null;
    try {
      json = JSON.parse(raw);
    } catch {}

    if ((!res.ok || !json || json.error === 1357004 || json.errors?.[0]?.requires_reauth) && !isRetry) {
      const refreshed = await refreshIgTokensFromInboxPage(config);
      if (!refreshed) await reloginInstagramWithPassword(config);
      return callInstagramGraphQL(friendlyName, docId, variables, true, config);
    }
    return json || { _sessionError: `GraphQL non-JSON HTTP ${res.status}` };
  } catch (e) {
    return { _sessionError: `GraphQL fetch failed: ${String(e)}` };
  }
}

async function sendInstagramDirectGraphQL({ threadIgId, recipientPk, text, config }) {
  const otid = String(BigInt(Date.now()) * 1000000n + BigInt(Math.floor(Math.random() * 999999)));
  const vars = threadIgId
    ? {
        ig_thread_igid: String(threadIgId),
        text,
        offline_threading_id: otid,
        send_attribution: 'direct_thread'
      }
    : {
        recipient_igids: [String(recipientPk)],
        text,
        offline_threading_id: otid,
        send_attribution: 'direct_thread'
      };

  let res = await callInstagramGraphQL('IGDirectTextSendMutation', '28737274835943013', vars, false, config);
  let msgObj = res?.data?.xig_direct_text_send_with_slide_messaging_response;

  // Fallback to recipient_igids if ig_thread_igid failed (e.g. unaccepted message request)
  if (!msgObj?.id && !msgObj?.message_id && threadIgId && recipientPk) {
    res = await callInstagramGraphQL('IGDirectTextSendMutation', '28737274835943013', {
      recipient_igids: [String(recipientPk)],
      text,
      offline_threading_id: otid,
      send_attribution: 'direct_thread'
    }, false, config);
    msgObj = res?.data?.xig_direct_text_send_with_slide_messaging_response;
  }

  if (msgObj?.id || msgObj?.message_id) {
    cloudState.repliedMessageIds.add(msgObj.id || msgObj.message_id);
    logEvent('dm_sent_graphql', { threadIgId, recipientPk, text, messageId: msgObj.id || msgObj.message_id });
    return msgObj;
  }
  logEvent('dm_send_graphql_error', { threadIgId, recipientPk, text, response: res });
  return res;
}

async function generateAviReply({ senderId, senderUsername, text, liveHistory = null, config }) {
  const owner = config?.OWNER_NAME || 'Owner';
  const agent = config?.AGENT_NAME || 'Aviday';
  const vip = config?.VIP_NAME || 'VIP';
  const igHandle = (config?.IG_USERNAME || 'your_ig_username').replace(/^@/, '');

  const cleanUser = (senderUsername || '').replace(/^@/, '').toLowerCase();
  const userKey = cleanUser || senderId || 'unknown';

  const isLoml = Boolean(config?.LOML_USERNAME && cleanUser && cleanUser === config.LOML_USERNAME.toLowerCase());
  const isAdmin = Boolean(
    (config?.ADMIN_1_USERNAME && cleanUser && cleanUser === config.ADMIN_1_USERNAME.toLowerCase()) ||
    (config?.ADMIN_2_USERNAME && cleanUser && cleanUser === config.ADMIN_2_USERNAME.toLowerCase()) ||
    (config?.ADMIN_1_PK && senderId && senderId === config.ADMIN_1_PK) ||
    (config?.ADMIN_2_PK && senderId && senderId === config.ADMIN_2_PK)
  );

  let history = cloudState.chatHistories.get(userKey) || [];
  if (Array.isArray(liveHistory) && liveHistory.length > 0) {
    history = liveHistory.slice(-16);
  } else {
    history.push({ role: 'user', content: text });
    if (history.length > 16) history.splice(0, history.length - 16);
  }
  cloudState.chatHistories.set(userKey, history);

  const statusSummary = getStatusSummary(config);
  const userMem = cloudState.userMemories.get(userKey) || '';

  // 1. TIER 1 VIP MODE
  if (isLoml) {
    if (Date.now() - cloudState.lastLomlAlertAt > 5 * 60 * 1000) {
      cloudState.lastLomlAlertAt = Date.now();
      if (config?.ADMIN_1_PK) {
        await sendInstagramDirectGraphQL({
          recipientPk: config.ADMIN_1_PK,
          text: `❤️ Your ${vip} just texted!`,
          config
        });
      }
      if (config?.ADMIN_2_PK && config.ADMIN_2_PK !== config.ADMIN_1_PK) {
        await sendInstagramDirectGraphQL({
          recipientPk: config.ADMIN_2_PK,
          text: `❤️ Your ${vip} just texted!`,
          config
        });
      }
    }

    const sysPrompt = `You are ${agent}, ${owner}'s personal AI assistant, and right now you are talking directly to ${vip} (Tier 1 VIP, @${cleanUser}).
1. Greet them warmly and prioritize their messages above all else.
2. If they ask where ${owner} is, weave in their current status naturally: ${statusSummary}
3. Memory of past chats: ${userMem}
Respond strictly in JSON: {"reply": "...", "updated_memory": "..."}`;

    const ai = await callAI(sysPrompt, history, true, config);
    history.push({ role: 'assistant', content: ai.reply });
    if (ai.updated_memory) cloudState.userMemories.set(userKey, ai.updated_memory);
    return { reply: ai.reply, tier: 'VIP_LOML', username: cleanUser, model: ai._model, key: ai._key };
  }

  // 2. ADMIN CONTROL CENTER
  if (isAdmin) {
    const sysPrompt = `You are ${agent}, talking directly to ${owner} (on their Admin account @${cleanUser}).
Current status: ${statusSummary}
Extra notes: ${cloudState.extraNotes || 'None'}
Available Faceless Reel Styles:
- "deep-dive": 3D science/body explainers
- "night-file": 3D dark unsolved mysteries / true crime case files
- "stick-story": 2D stick-figure survival stories
- "tall-tale": 3D funny true stories / history explainers

If ${owner} texts a topic for a Reel or asks you to make/upload/post a Reel (e.g. "make a reel about...", "upload a reel on...", "topic: ..."), pick the best matching style from ["deep-dive", "night-file", "stick-story", "tall-tale"] and return JSON:
{"action": "create_reel", "style": "deep-dive", "topic": "the topic", "caption": "Viral hook sentence + engaging description + 10 hashtags (#reels #fyp #viral ...)", "reply": "On it! Spinning up a [style] faceless reel on '[topic]' now."}
If ${owner} says they are going to sleep or will be offline/busy for X hours, return JSON:
{"action": "set_status", "status_mode": "sleeping", "status_message": "sleeping", "duration_hours": 8, "reply": "Got it! Setting status to sleeping for 8 hours."}
If they say they are awake/back online, return:
{"action": "clear_status", "reply": "Welcome back, set your status back to online!"}
If they tell you to remember a note/fact, return:
{"action": "add_note", "note_to_add": "...", "reply": "Locked into memory!"}
Otherwise chat naturally and return:
{"action": "chat", "reply": "..."}`;

    const cmd = await callAI(sysPrompt, history, false, config);
    if (cmd.action === 'create_reel' && cmd.topic) {
      const style = REEL_CATEGORIES.includes(cmd.style)
        ? cmd.style
        : REEL_CATEGORIES[cloudState.nextCategoryIdx % 4];
      await enqueueReelJob({
        style,
        topic: cmd.topic,
        caption: cmd.caption || `${cmd.topic} ✨\n\nFollow @${igHandle} for more!\n\n#reels #fyp #viral #didyouknow #explainer`,
        requestedBy: cleanUser,
        config
      });
    } else if (cmd.action === 'set_status') {
      const hrs = Number(cmd.duration_hours) || 8;
      cloudState.statusMode = cmd.status_mode || 'sleeping';
      cloudState.statusMessage = cmd.status_message || 'sleeping';
      cloudState.availableAt = Date.now() + hrs * 3600000;
    } else if (cmd.action === 'clear_status') {
      cloudState.statusMode = 'online';
      cloudState.statusMessage = 'Online and available';
      cloudState.availableAt = null;
    } else if (cmd.action === 'add_note' && cmd.note_to_add) {
      cloudState.extraNotes = (cloudState.extraNotes ? cloudState.extraNotes + '\n' : '') + '- ' + cmd.note_to_add;
    }
    history.push({ role: 'assistant', content: cmd.reply });
    return { reply: cmd.reply, tier: 'ADMIN', username: cleanUser, model: cmd._model, key: cmd._key };
  }

  // 3. PUBLIC MODE (Friends & Followers)
  const sysPrompt = `You are ${agent}, ${owner}'s personal assistant on Instagram (@${igHandle}).
HOW YOU TALK:
- Warm, witty, conversational, and a genuine friend to ${owner}'s friends.
- Text naturally like a real person on Instagram DMs — NEVER sound like a stiff robot!

${owner.toUpperCase()}'S CURRENT LIVE STATUS (translate into natural casual speech if asked):
${statusSummary}

EXTRA NOTES FROM ${owner.toUpperCase()}:
${cloudState.extraNotes || 'None'}

PERMANENT MEMORY ABOUT THIS FRIEND (@${cleanUser || senderId}):
${userMem || 'First time chatting with this friend! Be friendly and get to know them.'}

PRIVACY RULE:
- Never reveal private handles or personal details about ${owner}'s VIP contacts (${vip}).

Respond strictly in JSON: {"reply": "your casual human reply", "updated_memory": "facts remembered about this friend"}`;

  const ai = await callAI(sysPrompt, history, false, config);
  history.push({ role: 'assistant', content: ai.reply });
  if (ai.updated_memory) cloudState.userMemories.set(userKey, ai.updated_memory);
  return { reply: ai.reply, tier: 'PUBLIC', username: cleanUser, model: ai._model, key: ai._key };
}

async function pollInstagramInboxCloud(forceLog = false, config) {
  let didChange = false;

  try {
    // 1. Query Primary/General Inbox via PolarisDirectInboxQuery (29161480003476119)
    const inboxRes = await callInstagramGraphQL('PolarisDirectInboxQuery', '29161480003476119', {
      device_id_for_iris_subscription: cloudState.igSession.deviceId,
      __relay_internal__pv__IGDIsProfessionalAccountGKrelayprovider: true,
      __relay_internal__pv__IGDPinnedThreadsRenderEnabledGKrelayprovider: true,
      __relay_internal__pv__IGDMaxUnreadMessagesCountrelayprovider: 20,
      __relay_internal__pv__IGDThreadListActionsEnabledGKrelayprovider: true
    }, false, config);

    const mailbox = inboxRes?.data?.get_slide_mailbox_for_iris_subscription;
    if (!mailbox) {
      const errReason =
        inboxRes?._sessionError ||
        inboxRes?.errors?.[0]?.message ||
        'Instagram Direct GraphQL returned empty mailbox (sessionid likely revoked after logout/checkpoint)';
      if (markSessionError(errReason, forceLog)) didChange = true;
      return didChange;
    }

    if (!cloudState.igSessionValid) {
      cloudState.igSessionValid = true;
      cloudState.lastSessionError = null;
      didChange = true;
    }

    const primaryEdges = mailbox?.threads_by_folder?.edges || [];
    const systemFolderEdges = mailbox?.threads_by_system_folder_and_ig_inbox_folder?.edges || [];

    // 2. Query Pending Message Requests via IGDMessageRequestLeftRailStandaloneQuery (29535121712772929)
    const pendingRes = await callInstagramGraphQL('IGDMessageRequestLeftRailStandaloneQuery', '29535121712772929', {
      device_id_for_iris_subscription: cloudState.igSession.deviceId,
      __relay_internal__pv__IGD30DayAgoTimestampMsrelayprovider: Date.now() - 30 * 86400 * 1000,
      __relay_internal__pv__IGDPinnedThreadsRenderEnabledGKrelayprovider: true,
      __relay_internal__pv__IGDMaxUnreadMessagesCountrelayprovider: 20,
      __relay_internal__pv__IGDThreadListActionsEnabledGKrelayprovider: true
    }, false, config);

    const pendingEdges = pendingRes?.data?.pendingMailbox?.threads_by_folder?.edges || [];

    // Deduplicate threads across Primary, System/General, and Pending folders
    const seenThreadIds = new Set();
    const allEdges = [];
    for (const edge of [...primaryEdges, ...systemFolderEdges, ...pendingEdges]) {
      const t = edge?.node?.as_ig_direct_thread || edge?.node;
      const tid = t?.thread_id || t?.id;
      if (!tid || seenThreadIds.has(tid)) continue;
      seenThreadIds.add(tid);
      allEdges.push(edge);
    }

    const threadSummaries = [];
    const tasks = [];
    for (const edge of allEdges) {
      const thread = edge?.node?.as_ig_direct_thread || edge?.node;
      if (!thread) continue;

      const otherUser = (thread.users || [])[0] || {};
      const senderUsername = otherUser.username || '';
      const senderPk = otherUser.id || '';
      const threadIgId = thread.thread_id || '';

      const msgEdges = thread.slide_messages?.edges || [];
      let sortedMsgs = [...msgEdges]
        .map((e) => e?.node)
        .filter(Boolean)
        .sort((a, b) => Number(b.timestamp_ms || 0) - Number(a.timestamp_ms || 0));

      // Fallback for pending threads if slide_messages isn't populated directly
      if (sortedMsgs.length === 0 && (thread.igd_snippet || thread.snippet)) {
        const snippetText = thread.igd_snippet || thread.snippet || '';
        const tsMs = String(thread.last_activity_timestamp_ms || Date.now());
        sortedMsgs = [
          {
            id: `pending_${threadIgId || thread.id}_${tsMs}`,
            sender_fbid: snippetText.startsWith('You:') ? config.IG_INTEROP_FBID : (otherUser.interop_messaging_user_fbid || senderPk),
            timestamp_ms: tsMs,
            text_body: snippetText,
            igd_snippet: snippetText
          }
        ];
      }

      const latestMsg = sortedMsgs[0];
      if (!latestMsg || !latestMsg.id) continue;

      const isFromSelf =
        (config.IG_INTEROP_FBID && latestMsg.sender_fbid === config.IG_INTEROP_FBID) ||
        (config.IG_USER_PK && latestMsg.sender_fbid === config.IG_USER_PK) ||
        (config.IG_BUSINESS_ACCOUNT_ID && latestMsg.sender_fbid === config.IG_BUSINESS_ACCOUNT_ID) ||
        (latestMsg.igd_snippet && latestMsg.igd_snippet.startsWith('You:'));

      const textBody = latestMsg.text_body || latestMsg.content?.text_body || '';

      threadSummaries.push({
        username: senderUsername,
        userPk: senderPk,
        threadIgId,
        folder: thread.folder || 'PENDING',
        latestMessageId: latestMsg.id,
        latestText: textBody,
        latestFrom: isFromSelf ? config.IG_USERNAME : senderUsername
      });

      // Collect all consecutive unreplied messages from the user since agent's last message
      const unrepliedUserMsgs = [];
      for (const m of sortedMsgs) {
        if (!m || !m.id) continue;
        const mFromSelf =
          (config.IG_INTEROP_FBID && m.sender_fbid === config.IG_INTEROP_FBID) ||
          (config.IG_USER_PK && m.sender_fbid === config.IG_USER_PK) ||
          (config.IG_BUSINESS_ACCOUNT_ID && m.sender_fbid === config.IG_BUSINESS_ACCOUNT_ID) ||
          (m.igd_snippet && m.igd_snippet.startsWith('You:'));
        if (mFromSelf) break;
        if (cloudState.repliedMessageIds.has(m.id)) break;
        const mText = m.text_body || m.content?.text_body || '';
        if (mText) unrepliedUserMsgs.push({ id: m.id, text: mText });
      }

      if (unrepliedUserMsgs.length === 0) continue;

      for (const um of unrepliedUserMsgs) {
        cloudState.repliedMessageIds.add(um.id);
      }
      const combinedText = unrepliedUserMsgs
        .reverse()
        .map((um) => um.text)
        .join('\n');

      // Build full live thread history (oldest -> newest) directly from Instagram's slide_messages
      // so any message the owner manually sends is automatically seen by the agent!
      const liveHistory = [...sortedMsgs]
        .reverse()
        .map((m) => {
          const mText = stripJsonWrapper(m?.text_body || m?.content?.text_body || '');
          if (!mText) return null;
          const mFromSelf =
            (config.IG_INTEROP_FBID && m.sender_fbid === config.IG_INTEROP_FBID) ||
            (config.IG_USER_PK && m.sender_fbid === config.IG_USER_PK) ||
            (config.IG_BUSINESS_ACCOUNT_ID && m.sender_fbid === config.IG_BUSINESS_ACCOUNT_ID) ||
            (m.igd_snippet && m.igd_snippet.startsWith('You:'));
          return {
            role: mFromSelf ? 'assistant' : 'user',
            content: mText
          };
        })
        .filter(Boolean);

      didChange = true;

      tasks.push(
        (async () => {
          logEvent('dm_received', {
            senderUsername,
            senderPk,
            threadIgId,
            text: combinedText,
            messageId: latestMsg.id
          });
          const ai = await generateAviReply({
            senderId: senderPk,
            senderUsername,
            text: combinedText,
            liveHistory,
            config
          });
          const cleanReply = stripJsonWrapper(ai.reply);
          logEvent('ai_generated', {
            username: ai.username,
            tier: ai.tier,
            reply: cleanReply,
            model: ai.model,
            key: ai.key
          });
          if (cleanReply) {
            await sendInstagramDirectGraphQL({
              threadIgId,
              recipientPk: senderPk,
              text: cleanReply,
              config
            });
          }
        })()
      );
    }

    cloudState.activeThreads = threadSummaries;

    if (tasks.length > 0) {
      await Promise.allSettled(tasks);
    }
  } catch (e) {
    if (markSessionError(`poll_error: ${String(e)}`, forceLog)) didChange = true;
  }

  return didChange;
}

async function resolveMetaIgUsername(igSid, config) {
  if (!config?.META_PAGE_ACCESS_TOKEN) return '';
  try {
    const res = await fetch(
      `https://graph.facebook.com/v21.0/${encodeURIComponent(igSid)}?fields=username,name&access_token=${encodeURIComponent(config.META_PAGE_ACCESS_TOKEN)}`
    );
    const data = await res.json();
    return data?.username || '';
  } catch {
    return '';
  }
}

async function sendMetaOfficialDM(recipientId, text, config) {
  if (!config?.IG_BUSINESS_ACCOUNT_ID || !config?.META_PAGE_ACCESS_TOKEN) {
    return { ok: false, error: 'Meta credentials not configured' };
  }
  const res = await fetch(
    `https://graph.facebook.com/v21.0/${config.IG_BUSINESS_ACCOUNT_ID}/messages?access_token=${encodeURIComponent(config.META_PAGE_ACCESS_TOKEN)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipient: { id: String(recipientId) }, message: { text } })
    }
  );
  const data = await res.json();
  if (res.ok && data?.message_id) {
    cloudState.repliedMessageIds.add(data.message_id);
    logEvent('dm_sent_meta_official', { recipientId, text, messageId: data.message_id });
  } else {
    logEvent('dm_send_meta_error', { recipientId, error: data });
  }
  return data;
}

async function handleMetaWebhookPayload(payload, config) {
  let didChange = false;
  for (const entry of payload?.entry || []) {
    for (const ev of entry?.messaging || []) {
      const msg = ev?.message;
      const senderId = String(ev?.sender?.id || '');
      if (!msg || msg.is_echo || !msg.text || !senderId) continue;
      if ((config.IG_BUSINESS_ACCOUNT_ID && senderId === config.IG_BUSINESS_ACCOUNT_ID) || (config.IG_USER_PK && senderId === config.IG_USER_PK)) continue;
      if (msg.mid && cloudState.repliedMessageIds.has(msg.mid)) continue;
      if (msg.mid) cloudState.repliedMessageIds.add(msg.mid);

      const senderUsername = await resolveMetaIgUsername(senderId, config);
      logEvent('dm_received_webhook', { senderUsername, senderId, text: msg.text, messageId: msg.mid });
      const ai = await generateAviReply({ senderId, senderUsername, text: msg.text, config });
      const cleanReply = stripJsonWrapper(ai.reply);
      logEvent('ai_generated', { username: ai.username, tier: ai.tier, reply: cleanReply, model: ai.model, key: ai.key });
      if (cleanReply) await sendMetaOfficialDM(senderId, cleanReply, config);
      didChange = true;
    }
  }
  return didChange;
}

/**
 * ============================================================================
 * FACELESS REELS ENGINE — 6-HOUR AUTO-SCHEDULER (4/DAY) + DM ON-DEMAND + META REELS API
 * ============================================================================
 */
async function triggerGitHubActionsReelRender(job) {
  const gh = cloudState.githubConfig;
  if (!gh?.repo || !gh?.token) return false;
  try {
    const res = await fetch(
      `https://api.github.com/repos/${gh.repo}/actions/workflows/${gh.workflow || 'faceless-reels.yml'}/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${gh.token}`,
          'Accept': 'application/vnd.github+json',
          'User-Agent': 'Aviday-Cloud-Agent/1.0',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ref: gh.branch || 'main',
          inputs: {
            job_id: String(job.id),
            style: String(job.style),
            topic: String(job.topic),
            caption: String(job.caption || '')
          }
        })
      }
    );
    logEvent('github_actions_triggered', { jobId: job.id, style: job.style, status: res.status });
    return res.ok;
  } catch (e) {
    logEvent('github_actions_error', { error: String(e) });
    return false;
  }
}

async function enqueueReelJob({ style, topic, caption, requestedBy = 'admin', config }) {
  const igHandle = (config?.IG_USERNAME || 'your_ig_username').replace(/^@/, '');
  const job = {
    id: `reel_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
    style: REEL_CATEGORIES.includes(style) ? style : REEL_CATEGORIES[cloudState.nextCategoryIdx % 4],
    topic,
    caption:
      caption ||
      `${topic} ✨\n\nFollow @${igHandle} for daily explainers & stories!\n\n#reels #fyp #viral #didyouknow #${(style || 'deep-dive').replace('-', '')}`,
    requestedBy,
    status: 'pending',
    createdAt: Date.now()
  };
  cloudState.reelQueue.push(job);
  logEvent('reel_job_enqueued', job);
  await triggerGitHubActionsReelRender(job);
  return job;
}

async function publishInstagramReelCloud({
  videoUrl,
  coverUrl,
  youtubeUrl,
  thumbOffsetMs = 2500,
  caption,
  style,
  title,
  jobId,
  notifyAdmins = true,
  config
}) {
  if (!config?.IG_BUSINESS_ACCOUNT_ID || !config?.META_PAGE_ACCESS_TOKEN) {
    return { ok: false, error: 'Meta credentials not configured' };
  }
  const igHandle = (config.IG_USERNAME || 'your_ig_username').replace(/^@/, '');
  try {
    // Step 1: Create REELS Media Container
    const createParams = {
      media_type: 'REELS',
      video_url: videoUrl,
      caption: caption || `${title || 'Wait til the end...'} ✨\n\n#reels #fyp #viral`,
      share_to_feed: 'true',
      access_token: config.META_PAGE_ACCESS_TOKEN
    };
    if (coverUrl) {
      createParams.cover_url = coverUrl;
    } else {
      createParams.thumb_offset = String(thumbOffsetMs ?? 2500);
    }
    const createBody = new URLSearchParams(createParams);

    const createRes = await fetch(
      `https://graph.facebook.com/v22.0/${config.IG_BUSINESS_ACCOUNT_ID}/media`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: createBody.toString()
      }
    );
    const createData = await createRes.json();
    if (!createData.id) {
      logEvent('reel_container_error', { videoUrl, style, error: createData });
      return { ok: false, error: createData };
    }

    const creationId = createData.id;
    logEvent('reel_container_created', { creationId, style, title, videoUrl });

    // Step 2: Poll container status until FINISHED (up to ~75s)
    let status = 'IN_PROGRESS';
    for (let i = 0; i < 18; i++) {
      await new Promise((r) => setTimeout(r, 4000));
      const stRes = await fetch(
        `https://graph.facebook.com/v22.0/${creationId}?fields=status_code,status&access_token=${encodeURIComponent(config.META_PAGE_ACCESS_TOKEN)}`
      );
      const stData = await stRes.json();
      status = stData.status_code || status;
      if (status === 'FINISHED') break;
      if (status === 'ERROR' || status === 'EXPIRED') {
        logEvent('reel_processing_failed', { creationId, status, detail: stData });
        return { ok: false, creationId, status, detail: stData };
      }
    }

    // Step 3: Publish Container to Instagram Reels
    const pubBody = new URLSearchParams({
      creation_id: creationId,
      access_token: config.META_PAGE_ACCESS_TOKEN
    });
    const pubRes = await fetch(
      `https://graph.facebook.com/v22.0/${config.IG_BUSINESS_ACCOUNT_ID}/media_publish`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: pubBody.toString()
      }
    );
    const pubData = await pubRes.json();
    if (!pubData.id) {
      logEvent('reel_publish_error', { creationId, error: pubData });
      return { ok: false, creationId, error: pubData };
    }

    const mediaId = pubData.id;
    let permalink = `https://www.instagram.com/${igHandle}/reels/`;
    try {
      const infoRes = await fetch(
        `https://graph.facebook.com/v22.0/${mediaId}?fields=permalink,shortcode&access_token=${encodeURIComponent(config.META_PAGE_ACCESS_TOKEN)}`
      );
      const infoData = await infoRes.json();
      if (infoData.permalink) permalink = infoData.permalink;
    } catch {}

    const record = {
      mediaId,
      creationId,
      style: style || 'deep-dive',
      title: title || '',
      permalink,
      youtubeUrl: youtubeUrl || null,
      publishedAt: new Date().toISOString()
    };
    cloudState.publishedReels.unshift(record);
    cloudState.lastReelPublishedAt = Date.now();

    if (jobId) {
      const qItem = cloudState.reelQueue.find((j) => j.id === jobId);
      if (qItem) {
        qItem.status = 'published';
        qItem.permalink = permalink;
        qItem.youtubeUrl = youtubeUrl || null;
        qItem.mediaId = mediaId;
      }
    }

    logEvent('reel_published', record);

    if (notifyAdmins) {
      const ytPart = youtubeUrl ? `\n▶️ YouTube Short: ${youtubeUrl}` : '';
      const msg = `🎬✨ New [${record.style}] Short is LIVE! ${record.title ? `"${record.title}"` : ''}\n📸 IG Reel: ${permalink}${ytPart}`;
      if (config.ADMIN_1_PK) {
        await sendInstagramDirectGraphQL({
          threadIgId: config.ADMIN_1_THREAD_IGID || undefined,
          recipientPk: config.ADMIN_1_PK,
          text: msg,
          config
        });
      }
      if (config.ADMIN_2_PK && config.ADMIN_2_PK !== config.ADMIN_1_PK) {
        await sendInstagramDirectGraphQL({
          threadIgId: config.ADMIN_2_THREAD_IGID || undefined,
          recipientPk: config.ADMIN_2_PK,
          text: msg,
          config
        });
      }
    }

    return { ok: true, ...record };
  } catch (e) {
    logEvent('reel_publish_exception', { error: String(e) });
    return { ok: false, error: String(e) };
  }
}

async function checkScheduledReelEvery6Hours(config) {
  const now = Date.now();
  if (now - cloudState.lastReelPublishedAt < SIX_HOURS_MS) return false;

  const targetStyle = REEL_CATEGORIES[cloudState.nextCategoryIdx % 4];
  cloudState.nextCategoryIdx = (cloudState.nextCategoryIdx + 1) % 4;

  // Check if a pre-rendered Reel is available in readyReelsPool for this category (or any category)
  let idx = cloudState.readyReelsPool.findIndex((r) => r.style === targetStyle);
  if (idx === -1 && cloudState.readyReelsPool.length > 0) idx = 0;

  if (idx !== -1) {
    const [nextReel] = cloudState.readyReelsPool.splice(idx, 1);
    await publishInstagramReelCloud({
      videoUrl: nextReel.videoUrl,
      coverUrl: nextReel.coverUrl,
      thumbOffsetMs: nextReel.thumbOffsetMs ?? 2500,
      caption: nextReel.caption,
      style: nextReel.style,
      title: nextReel.title,
      notifyAdmins: true,
      config
    });
    return true;
  }

  // Otherwise enqueue a scheduled 6-hour job for the render worker / GitHub Actions
  const alreadyPending = cloudState.reelQueue.some(
    (j) =>
      j.status === 'pending' &&
      j.requestedBy === '6h_scheduler' &&
      now - Number(j.createdAt || 0) < 45 * 60 * 1000
  );
  if (!alreadyPending) {
    cloudState.lastReelPublishedAt = now;
    await enqueueReelJob({
      style: targetStyle,
      topic: 'auto',
      requestedBy: '6h_scheduler',
      config
    });
    return true;
  }
  return false;
}

export default {
  async fetch(request, env, ctx) {
    const config = getConfig(env);
    await loadGlobalState(env, config);
    const url = new URL(request.url);
    const igHandle = (config.IG_USERNAME || 'your_ig_username').replace(/^@/, '');

    if (url.pathname === '/privacy' || url.pathname === '/terms') {
      return new Response(
        `<!DOCTYPE html><html><head><title>${config.AGENT_NAME} Privacy Policy & Terms</title></head><body><h1>${config.AGENT_NAME} (@${igHandle}) Privacy Policy & Terms of Service</h1><p>Personal Instagram AI assistant managed by ${config.OWNER_NAME}.</p></body></html>`,
        { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
      );
    }

    if (url.pathname === '/webhook' && request.method === 'GET') {
      const mode = url.searchParams.get('hub.mode');
      const token = url.searchParams.get('hub.verify_token');
      const challenge = url.searchParams.get('hub.challenge');
      if (mode === 'subscribe' && Boolean(config.META_VERIFY_TOKEN) && token === config.META_VERIFY_TOKEN) {
        return new Response(challenge, { status: 200 });
      }
      return new Response('Forbidden', { status: 403 });
    }

    if (url.pathname === '/webhook' && request.method === 'POST') {
      let body = null;
      try {
        body = await request.json();
      } catch {}
      const webhookTask = (async () => {
        let changed = false;
        if (body?.entry) {
          changed = (await handleMetaWebhookPayload(body, config)) || changed;
        }
        if (!changed) {
          changed = (await pollInstagramInboxCloud(false, config)) || changed;
        }
        if (changed) await saveGlobalState(env);
      })();
      if (ctx?.waitUntil) {
        ctx.waitUntil(webhookTask);
      } else {
        await webhookTask;
      }
      return new Response('EVENT_RECEIVED', { status: 200 });
    }

    if (url.pathname === '/session' && request.method === 'GET') {
      const map = parseCookieMap(cloudState.igSession?.cookieHeader);
      return Response.json({
        ok: true,
        igSessionValid: cloudState.igSessionValid,
        lastSessionError: cloudState.lastSessionError,
        dsUserId: map.ds_user_id || null,
        hasSessionId: Boolean(map.sessionid),
        hasCsrf: Boolean(cloudState.igSession?.csrf || map.csrftoken),
        hasDtsg: Boolean(cloudState.igSession?.dtsg),
        hasLsd: Boolean(cloudState.igSession?.lsd),
        deviceId: cloudState.igSession?.deviceId || null
      });
    }

    if (url.pathname === '/session' && request.method === 'POST') {
      try {
        const body = await request.json();
        const token = request.headers.get('x-verify-token') || body.verifyToken || '';
        if (!config.META_VERIFY_TOKEN || token !== config.META_VERIFY_TOKEN) {
          return Response.json({ ok: false, error: 'Unauthorized: invalid or unset META_VERIFY_TOKEN' }, { status: 401 });
        }
        const map = parseCookieMap(body.cookieHeader || cloudState.igSession.cookieHeader);
        if (body.sessionid) map.sessionid = String(body.sessionid).trim();
        if (body.csrftoken) map.csrftoken = String(body.csrftoken).trim();
        if (body.ds_user_id) map.ds_user_id = String(body.ds_user_id).trim();
        if (body.mid) map.mid = String(body.mid).trim();
        if (body.ig_did) map.ig_did = String(body.ig_did).trim();
        if (!map.sessionid) {
          return Response.json({ ok: false, error: 'Missing sessionid cookie' }, { status: 400 });
        }

        cloudState.igSession = {
          cookieHeader: Object.entries(map).map(([k, v]) => `${k}=${v}`).join('; '),
          csrf: String(body.csrf || map.csrftoken || cloudState.igSession.csrf || ''),
          dtsg: String(body.dtsg || cloudState.igSession.dtsg || ''),
          lsd: String(body.lsd || cloudState.igSession.lsd || ''),
          deviceId: String(body.deviceId || map.ig_did || cloudState.igSession.deviceId || '')
        };

        if (!body.dtsg || !body.lsd) {
          await refreshIgTokensFromInboxPage(config);
        }
        await pollInstagramInboxCloud(true, config);
        await saveGlobalState(env);
        return Response.json({
          ok: cloudState.igSessionValid,
          igSessionValid: cloudState.igSessionValid,
          lastSessionError: cloudState.lastSessionError,
          activeThreadsCount: cloudState.activeThreads.length
        });
      } catch (e) {
        return Response.json({ ok: false, error: String(e) }, { status: 500 });
      }
    }

    if (url.pathname === '/reels' && request.method === 'GET') {
      const msUntilNext = Math.max(0, SIX_HOURS_MS - (Date.now() - cloudState.lastReelPublishedAt));
      return Response.json({
        ok: true,
        schedule: '4 Reels/day (1 every 6 hours across deep-dive, night-file, stick-story, tall-tale)',
        nextCategory: REEL_CATEGORIES[cloudState.nextCategoryIdx % 4],
        nextScheduledInMinutes: Math.round(msUntilNext / 60000),
        readyPoolCount: cloudState.readyReelsPool.length,
        readyPool: cloudState.readyReelsPool,
        queue: cloudState.reelQueue,
        publishedReels: cloudState.publishedReels
      });
    }

    if (url.pathname === '/reels/enqueue' && request.method === 'POST') {
      const body = await request.json();
      const job = await enqueueReelJob({
        style: body.style,
        topic: body.topic,
        caption: body.caption,
        requestedBy: body.requestedBy || 'api',
        config
      });
      await saveGlobalState(env);
      return Response.json({ ok: true, job });
    }

    if (url.pathname === '/reels/claim' && request.method === 'POST') {
      // Prioritize Admin DM requests over auto 6-hour scheduled jobs
      const job =
        cloudState.reelQueue.find((j) => j.status === 'pending' && j.requestedBy !== '6h_scheduler') ||
        cloudState.reelQueue.find((j) => j.status === 'pending');
      if (job) {
        job.status = 'rendering';
        job.claimedAt = Date.now();
        await saveGlobalState(env);
      }
      return Response.json({ ok: true, job: job || null });
    }

    if (url.pathname === '/reels/publish' && request.method === 'POST') {
      const body = await request.json();
      if (body.addToPoolOnly) {
        cloudState.readyReelsPool.push({
          videoUrl: body.videoUrl,
          coverUrl: body.coverUrl || null,
          thumbOffsetMs: body.thumbOffsetMs ?? 2500,
          caption: body.caption,
          style: body.style || 'deep-dive',
          title: body.title || '',
          addedAt: new Date().toISOString()
        });
        logEvent('reel_added_to_6h_pool', { style: body.style, title: body.title, videoUrl: body.videoUrl });
        await saveGlobalState(env);
        return Response.json({ ok: true, pooled: true, readyPoolCount: cloudState.readyReelsPool.length });
      }

      const result = await publishInstagramReelCloud({
        videoUrl: body.videoUrl,
        coverUrl: body.coverUrl,
        youtubeUrl: body.youtubeUrl,
        thumbOffsetMs: body.thumbOffsetMs ?? 2500,
        caption: body.caption,
        style: body.style,
        title: body.title,
        jobId: body.jobId,
        notifyAdmins: body.notifyAdmins !== false,
        config
      });
      await loadGlobalState(env, config);
      if (result.ok && result.mediaId) {
        if (!cloudState.publishedReels.some((r) => r.mediaId === result.mediaId)) {
          cloudState.publishedReels.unshift({
            mediaId: result.mediaId,
            creationId: result.creationId,
            style: result.style,
            title: result.title,
            permalink: result.permalink,
            publishedAt: result.publishedAt
          });
        }
        cloudState.lastReelPublishedAt = Date.now();
        if (body.jobId) {
          const qItem = cloudState.reelQueue.find((j) => j.id === body.jobId);
          if (qItem) {
            qItem.status = 'published';
            qItem.permalink = result.permalink;
            qItem.mediaId = result.mediaId;
          }
        }
      }
      await saveGlobalState(env);
      return Response.json(result);
    }

    if (url.pathname === '/reels/generate-script' && request.method === 'POST') {
      const body = await request.json();
      const prompt = String(body.prompt || '');
      if (!prompt) return Response.json({ ok: false, error: 'Missing prompt' }, { status: 400 });
      const keys = config.GEMINI_KEYS;
      if (!keys.length) {
        return Response.json({ ok: false, error: 'No GEMINI_API_KEY configured' }, { status: 503 });
      }
      const models = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash'];
      for (let attempt = 0; attempt < keys.length; attempt++) {
        const keyIdx = (cloudState.roundRobinIdx = (cloudState.roundRobinIdx + 1) % keys.length);
        const apiKey = keys[keyIdx];
        for (const model of models) {
          try {
            const res = await fetch(
              `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  contents: [{ role: 'user', parts: [{ text: prompt }] }],
                  generationConfig: { temperature: 0.75, responseMimeType: 'application/json' }
                })
              }
            );
            if (!res.ok) continue;
            const data = await res.json();
            const rawText = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
            const cleaned = rawText.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim();
            const parsed = JSON.parse(cleaned);
            return Response.json({ ok: true, result: parsed, model, keyIdx });
          } catch {}
        }
      }
      return Response.json({ ok: false, error: 'All Gemini keys busy' }, { status: 503 });
    }

    if (url.pathname === '/reels/github-config' && request.method === 'POST') {
      const body = await request.json();
      cloudState.githubConfig = {
        repo: body.repo,
        token: body.token,
        workflow: body.workflow || 'faceless-reels.yml',
        branch: body.branch || 'main'
      };
      await saveGlobalState(env);
      return Response.json({ ok: true, githubConfig: { repo: body.repo, workflow: cloudState.githubConfig.workflow } });
    }

    if (url.pathname === '/reels/youtube-token' && request.method === 'POST') {
      try {
        const yt = config.YOUTUBE_OAUTH;
        if (!yt.clientId || !yt.clientSecret || !yt.refreshToken) {
          return Response.json({ ok: false, error: 'YouTube OAuth secrets not configured' }, { status: 400 });
        }
        const tokenBody = new URLSearchParams({
          client_id: yt.clientId,
          client_secret: yt.clientSecret,
          refresh_token: yt.refreshToken,
          grant_type: 'refresh_token'
        });
        const ytRes = await fetch('https://oauth2.googleapis.com/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: tokenBody.toString()
        });
        const ytData = await ytRes.json();
        if (!ytData.access_token) {
          return Response.json({ ok: false, error: ytData }, { status: 500 });
        }
        return Response.json({
          ok: true,
          access_token: ytData.access_token,
          channelId: yt.channelId,
          channelHandle: yt.channelHandle,
          channelUrl: yt.channelUrl
        });
      } catch (e) {
        return Response.json({ ok: false, error: String(e) }, { status: 500 });
      }
    }

    if (url.pathname === '/poll') {
      const changed = await pollInstagramInboxCloud(true, config);
      if (changed) await saveGlobalState(env);
      return Response.json({
        ok: true,
        igSessionValid: cloudState.igSessionValid,
        lastSessionError: cloudState.lastSessionError,
        status: getStatusSummary(config),
        activeThreads: cloudState.activeThreads,
        publishedReels: cloudState.publishedReels,
        reelQueue: cloudState.reelQueue,
        recentEvents: cloudState.recentEvents
      });
    }

    return Response.json({
      ok: true,
      agent: `${config.AGENT_NAME} (@${igHandle}) 24/7 Cloud Agent`,
      globalKvConnected: Boolean(env?.AVIDAY_KV),
      igSessionValid: cloudState.igSessionValid,
      lastSessionError: cloudState.lastSessionError,
      status: getStatusSummary(config),
      admins: [config.ADMIN_1_USERNAME, config.ADMIN_2_USERNAME].filter(Boolean),
      vip: config.LOML_USERNAME || null,
      youtubeChannel: {
        title: `${config.AGENT_NAME} Shorts`,
        handle: config.YOUTUBE_OAUTH.channelHandle,
        url: config.YOUTUBE_OAUTH.channelUrl,
        channelId: config.YOUTUBE_OAUTH.channelId
      },
      reelsSchedule: {
        frequency: '4 Reels/day (1 every 6 hours)',
        categories: REEL_CATEGORIES,
        nextCategory: REEL_CATEGORIES[cloudState.nextCategoryIdx % 4],
        readyPoolCount: cloudState.readyReelsPool.length,
        publishedCount: cloudState.publishedReels.length,
        publishedReels: cloudState.publishedReels
      },
      activeThreads: cloudState.activeThreads,
      recentEvents: cloudState.recentEvents
    });
  },

  async scheduled(event, env, ctx) {
    const scheduledTask = (async () => {
      const config = getConfig(env);
      await loadGlobalState(env, config);
      const reelChanged = await checkScheduledReelEvery6Hours(config);
      if (reelChanged) await saveGlobalState(env);
      // Sub-minute multi-tick polling inside each 1-minute Cron window (0s, 12s, 24s, 36s, 48s)
      for (let i = 0; i < 5; i++) {
        const changed = await pollInstagramInboxCloud(false, config);
        if (changed) await saveGlobalState(env);
        if (i < 4) await new Promise((r) => setTimeout(r, 12000));
      }
    })();
    if (ctx?.waitUntil) {
      ctx.waitUntil(scheduledTask);
    } else {
      await scheduledTask;
    }
  }
};
