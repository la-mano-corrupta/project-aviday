// Kinetic 1-3 word captions strictly inside the All-3 safe zone (x=468, y=980..1248).
import { ctx, P, lerp, seg, eob } from './lib.js';
import { SAFE } from './safezone.js';
import { T, lineWords } from './timing.js';

let caps = [];

function autoChunks(text) {
  const clean = text.replace(/\[[^\]]+\]/g, ' ').trim();
  const ws = clean.toUpperCase().split(/\s+/).filter(Boolean);
  const out = [];
  for (let i = 0; i < ws.length; ) {
    const n = ws.length - i === 4 ? 2 : Math.min(3, ws.length - i);
    out.push(ws.slice(i, i + n));
    i += n;
  }
  return out.map((chunk) => {
    const best = chunk.reduce(
      (b, w, idx) => (w.replace(/[^A-Z]/g, '').length > chunk[b].replace(/[^A-Z]/g, '').length ? idx : b),
      0
    );
    return chunk.map((w, idx) => (idx === best ? `*${w}` : w)).join(' ');
  });
}

export function buildCaptions(script) {
  caps = [];
  script.lines.forEach((ln, i) => {
    const chunks = (ln.caps ? ln.caps.split('|') : autoChunks(ln.text))
      .map((s) => s.trim())
      .filter(Boolean);
    const ws = lineWords(i);
    if (!ws.length) return;

    const counts = chunks.map((c) => c.split(/\s+/).length);
    const total = counts.reduce((a, b) => a + b, 0) || 1;
    const nm = (w) => String(w).toLowerCase().replace(/[^a-z0-9']+/g, '');

    let acc = 0;
    let from = 0;
    chunks.forEach((c, j) => {
      const first = nm(c.split(/\s+/)[0]);
      let idx =
        j === 0
          ? 0
          : ws.findIndex((w, k) => k > from && first && (nm(w.w) === first || (first.length > 2 && nm(w.w).startsWith(first))));
      if (idx < 0) {
        idx = Math.max(from + (j ? 1 : 0), Math.min(ws.length - 1, Math.round((acc * ws.length) / total)));
      }
      acc += counts[j];
      from = idx;
      caps.push({
        line: i,
        s: Math.max(0, ws[idx].s - 0.05),
        words: c.split(/\s+/).map((w) => ({ txt: w.replace('*', ''), hi: w.startsWith('*') })),
      });
    });
  });

  caps.forEach((c, k) => {
    const next = caps[k + 1];
    const lEnd = T.lines[c.line]?.end ?? T.dur;
    c.e = next ? (next.s - lEnd > 0.65 && next.line !== c.line ? lEnd + 0.3 : next.s) : T.dur;
  });
  return caps;
}

export const captionList = () => caps;

export function drawCaption(t, darkScene = false) {
  const c = caps.find((x) => t >= x.s && t < x.e);
  if (!c) return;

  const lt = t - c.s;
  const size = 96;
  ctx.save();
  ctx.font = `900 ${size}px -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif`;
  const sp = size * 0.25;
  c.words.forEach((w) => {
    w.w = ctx.measureText(w.txt).width;
  });
  const widthOf = (ws) => ws.reduce((a, w) => a + w.w, 0) + sp * Math.max(0, ws.length - 1);

  let lines = [c.words];
  if (widthOf(c.words) > SAFE.captionMaxW && c.words.length > 1) {
    let best = null;
    for (let i = 1; i < c.words.length; i++) {
      const a = c.words.slice(0, i);
      const b = c.words.slice(i);
      const m = Math.max(widthOf(a), widthOf(b));
      if (!best || m < best.m) best = { m, l: [a, b] };
    }
    lines = best.l;
  }

  const fit = Math.min(1, SAFE.captionMaxW / Math.max(1, ...lines.map(widthOf)));
  const pop = lt < 0.16 ? lerp(0.72, 1, eob(seg(lt, 0, 0.16))) : 1;
  const sc = pop * fit;

  ctx.translate(SAFE.cx, SAFE.captionY);
  ctx.scale(sc, sc);
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'left';
  ctx.lineJoin = 'round';

  const lh = size * 1.04;
  const y0 = -((lines.length - 1) * lh) / 2;
  lines.forEach((ln, li) => {
    let x = -widthOf(ln) / 2;
    const y = y0 + li * lh;
    for (const w of ln) {
      ctx.lineWidth = 20;
      ctx.strokeStyle = darkScene ? '#08090B' : P.captionStroke;
      ctx.strokeText(w.txt, x, y + 6);
      ctx.strokeText(w.txt, x, y);
      ctx.fillStyle = w.hi ? P.captionHighlight : P.captionFill;
      ctx.fillText(w.txt, x, y);
      x += w.w + sp;
    }
  });
  ctx.restore();
}
