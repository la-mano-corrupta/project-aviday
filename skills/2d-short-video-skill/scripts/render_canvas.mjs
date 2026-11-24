// Zero-dependency Node 22+ Headless Chrome + FFmpeg renderer for 2D Shorts/Reels.
// Run from inside a canvas-2d project directory:
//   node tools/render_canvas.mjs check
//   node tools/render_canvas.mjs cues
//   node tools/render_canvas.mjs sheet review/sheet.jpg [step=0.5] [cols=8]
//   node tools/render_canvas.mjs frames review/frames "0.1,3.5,12.0"
//   node tools/render_canvas.mjs cover review/cover    -> writes review/cover-9x16.jpg & review/cover-3x4.jpg
//   node tools/render_canvas.mjs video renders/out.mp4 [start end] [--draft]
//   node tools/render_canvas.mjs preview

import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FPS = +(process.env.FPS || 30);
const CHROME = [
  process.env.CHROME,
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].find((p) => p && fs.existsSync(p));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const args = process.argv.slice(2);
const flags = new Set(args.filter((a) => a.startsWith('--')));
const [mode, ...rest] = args.filter((a) => !a.startsWith('--'));

const MIME = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.json': 'application/json',
  '.otf': 'font/otf',
  '.ttf': 'font/ttf',
  '.woff2': 'font/woff2',
  '.wav': 'audio/wav',
  '.mp3': 'audio/mpeg',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
};

function serve(port = 0) {
  return new Promise((res) => {
    const srv = http.createServer((req, r) => {
      const u = decodeURIComponent(req.url.split('?')[0]);
      const f = path.join(ROOT, u === '/' ? 'index.html' : u);
      if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) {
        r.writeHead(404);
        r.end();
        return;
      }
      r.writeHead(200, {
        'Content-Type': MIME[path.extname(f)] || 'application/octet-stream',
        'Cache-Control': 'no-store',
      });
      fs.createReadStream(f).pipe(r);
    });
    srv.listen(port, '127.0.0.1', () => res(srv));
  });
}

async function openPage(port) {
  if (!CHROME) throw new Error('Chrome not found: install Google Chrome or set CHROME=/path/to/chrome');
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), '2dshort-chrome-'));
  const chrome = spawn(
    CHROME,
    [
      '--headless=new',
      '--remote-debugging-port=0',
      `--user-data-dir=${prof}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--hide-scrollbars',
      '--window-size=1080,1920',
      '--disable-background-timer-throttling',
      '--disable-renderer-backgrounding',
      'about:blank',
    ],
    { stdio: 'ignore' }
  );

  let dbg;
  for (let i = 0; i < 200 && !dbg; i++) {
    try {
      dbg = fs.readFileSync(path.join(prof, 'DevToolsActivePort'), 'utf8').split('\n')[0].trim();
    } catch {
      await sleep(100);
    }
  }
  if (!dbg) throw new Error('Chrome did not start');

  const qs = flags.has('--safezone') ? '&safezone=1' : '';
  const targetUrl = `http://127.0.0.1:${port}/index.html?capture=1${qs}`;
  const resp = await fetch(`http://127.0.0.1:${dbg}/json/new?${encodeURIComponent(targetUrl)}`, { method: 'PUT' });
  const target = await resp.json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.onopen = res;
    ws.onerror = rej;
  });

  let id = 0;
  const pend = new Map();
  const logs = [];
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) {
      const p = pend.get(m.id);
      pend.delete(m.id);
      m.error ? p.rej(new Error(m.error.message)) : p.res(m.result);
    } else if (m.method === 'Runtime.exceptionThrown') {
      logs.push('EXCEPTION ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
    } else if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      logs.push('ERROR ' + m.params.args.map((a) => a.value ?? a.description).join(' '));
    }
  };

  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const i = ++id;
      pend.set(i, { res, rej });
      ws.send(JSON.stringify({ id: i, method, params }));
    });

  const ev = async (expression) => {
    const x = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (x.exceptionDetails) {
      throw new Error(x.exceptionDetails.exception?.description || x.exceptionDetails.text);
    }
    return x.result.value;
  };

  await send('Runtime.enable');
  for (let i = 0; ; i++) {
    const st = await ev('window.OP ? (OP.bootError ? "ERR:" + OP.bootError : OP.ready) : false').catch(() => false);
    if (st === true) break;
    if (typeof st === 'string') throw new Error('boot failed: ' + st + '\n' + logs.join('\n'));
    if (i > 600) throw new Error('boot timeout\n' + logs.join('\n'));
    await sleep(100);
  }

  const close = () => {
    try { ws.close(); } catch {}
    chrome.kill('SIGKILL');
    setTimeout(() => { try { fs.rmSync(prof, { recursive: true, force: true }); } catch {} }, 300);
  };
  return { ev, logs, close };
}

const jpgBuf = (d) => Buffer.from(d.slice(d.indexOf(',') + 1), 'base64');
const FRAME_EXPR = (t, q, stamp) => `(() => {
  const d = OP.frame(${t}, ${q});
  ${stamp ? `const cv = document.getElementById('cv'), c = cv.getContext('2d');
  c.setTransform(1,0,0,1,0,0); c.fillStyle='rgba(0,0,0,0.85)'; c.fillRect(0,0,220,76);
  c.fillStyle='#fff'; c.font='700 48px sans-serif'; c.textAlign='left'; c.textBaseline='alphabetic';
  c.fillText('${(+t).toFixed(2)}s', 14, 54); return cv.toDataURL('image/jpeg', ${q});` : 'return d;'}
})()`;

const srv = await serve(mode === 'preview' ? 8765 : 0);
const port = srv.address().port;

if (mode === 'preview') {
  console.log(`Preview running: http://127.0.0.1:${port}/?safezone=1 (Ctrl+C to stop)`);
} else {
  const P = await openPage(port);
  try {
    const dur = await P.ev('OP.duration()');
    if (mode === 'check') {
      console.log(`duration ${dur.toFixed(2)} s`);
      for (const s of await P.ev('OP.shots()')) {
        console.log(`${String(s.id).padEnd(8)} ${s.at.toFixed(2).padStart(6)} -> ${s.end.toFixed(2).padStart(6)} (${(s.end - s.at).toFixed(2)} s) ${s.note || ''}`);
      }
      console.log('captions:');
      for (const c of await P.ev('OP.captions()')) {
        console.log(`  ${c.s.toFixed(2).padStart(6)}-${c.e.toFixed(2).padEnd(6)} ${c.text}`);
      }
      let bad = 0;
      for (let t = 0; t < dur; t += 0.25) {
        try { await P.ev(`OP.draw(${t})`); } catch (e) { bad++; console.log(`ERROR at ${t.toFixed(2)}: ${e.message}`); }
      }
      if (P.logs.length) console.log(P.logs.join('\n'));
      console.log(bad || P.logs.length ? 'CHECK FAILED' : 'CHECK OK');
      if (bad || P.logs.length) process.exitCode = 1;
    } else if (mode === 'cues') {
      const cues = await P.ev('OP.cues()');
      fs.mkdirSync(path.join(ROOT, 'data'), { recursive: true });
      fs.writeFileSync(path.join(ROOT, 'data/cues.json'), JSON.stringify({ duration: dur, cues }, null, 2));
      console.log(`data/cues.json: ${cues.length} cues, ${dur.toFixed(2)} s`);
    } else if (mode === 'frames') {
      const dir = path.resolve(ROOT, rest[0] || 'review/frames');
      fs.mkdirSync(dir, { recursive: true });
      for (const t of (rest[1] || '0').split(',').map(Number)) {
        fs.writeFileSync(path.join(dir, `t${t.toFixed(2)}.jpg`), jpgBuf(await P.ev(FRAME_EXPR(t, 0.93, false))));
      }
      console.log(dir);
    } else if (mode === 'cover') {
      const prefix = path.resolve(ROOT, rest[0] || 'review/cover');
      fs.mkdirSync(path.dirname(prefix), { recursive: true });
      const c916 = await P.ev('OP.cover("9:16", 0.94)');
      const c34 = await P.ev('OP.cover("3:4", 0.94)');
      fs.writeFileSync(`${prefix}-9x16.jpg`, jpgBuf(c916));
      fs.writeFileSync(`${prefix}-3x4.jpg`, jpgBuf(c34));
      console.log(`Wrote ${prefix}-9x16.jpg (1080x1920) & ${prefix}-3x4.jpg (1080x1440)`);
    } else if (mode === 'sheet') {
      const out = path.resolve(ROOT, rest[0] || 'review/sheet.jpg');
      const step = +(rest[1] || 0.5);
      const cols = +(rest[2] || 8);
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), '2dshort-sheet-'));
      let n = 0;
      for (let t = step / 2; t < dur; t += step) {
        fs.writeFileSync(path.join(tmp, `f${String(n++).padStart(4, '0')}.jpg`), jpgBuf(await P.ev(FRAME_EXPR(t, 0.82, true))));
      }
      const rows = Math.ceil(n / cols);
      fs.mkdirSync(path.dirname(out), { recursive: true });
      const r = spawnSync('ffmpeg', [
        '-v', 'error', '-y', '-framerate', '1',
        '-i', path.join(tmp, 'f%04d.jpg'),
        '-vf', `scale=270:480,tile=${cols}x${rows}:padding=4:color=black`,
        '-frames:v', '1', '-q:v', '3', out,
      ]);
      fs.rmSync(tmp, { recursive: true, force: true });
      if (r.status) throw new Error('ffmpeg sheet failed: ' + r.stderr);
      console.log(`${out} (${n} frames, step ${step}s)`);
    } else if (mode === 'video') {
      const out = path.resolve(ROOT, rest[0] || 'renders/out.mp4');
      fs.mkdirSync(path.dirname(out), { recursive: true });
      const mix = path.join(ROOT, 'data/mix.wav');
      const hasMix = fs.existsSync(mix);
      const a0 = rest[1] ? +rest[1] : 0;
      const a1 = rest[2] ? Math.min(+rest[2], dur) : dur;
      const totalFrames = Math.max(1, Math.round((a1 - a0) * FPS));
      const ff = spawn(
        'ffmpeg',
        [
          '-v', 'error', '-y',
          '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
          ...(hasMix ? ['-ss', String(a0), '-t', String(a1 - a0), '-i', mix] : ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']),
          '-map', '0:v', '-map', '1:a',
          '-c:v', 'libx264', '-preset', flags.has('--draft') ? 'ultrafast' : 'veryfast',
          '-crf', flags.has('--draft') ? '27' : '18', '-pix_fmt', 'yuv420p',
          '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out,
        ],
        { stdio: ['pipe', 'inherit', 'inherit'] }
      );
      const t0 = Date.now();
      for (let i = 0; i < totalFrames; i++) {
        const b = jpgBuf(await P.ev(FRAME_EXPR(a0 + i / FPS, flags.has('--draft') ? 0.8 : 0.93, false)));
        if (!ff.stdin.write(b)) await new Promise((r) => ff.stdin.once('drain', r));
        if (i % 150 === 0) process.stdout.write(`\r${i}/${totalFrames} frames`);
      }
      ff.stdin.end();
      await new Promise((r) => ff.on('close', r));
      console.log(`\r${out} (${totalFrames} frames, ${hasMix ? 'with data/mix.wav' : 'SILENT'}, ${((Date.now() - t0) / 1000).toFixed(1)}s)`);
    } else {
      console.log('Usage: render_canvas.mjs <check|cues|sheet|frames|cover|video|preview> [--draft] [--safezone]');
    }
  } finally {
    P.close();
    srv.close();
  }
}
