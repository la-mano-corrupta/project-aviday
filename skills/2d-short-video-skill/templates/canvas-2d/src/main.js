// Bootstraps script, timing, style preset, captions, and exposes window.OP for Headless Chrome capture.
import { cv, ctx, setStylePreset } from './core/lib.js';
import { loadTiming, T } from './core/timing.js';
import { buildCaptions, captionList, drawCaption } from './core/captions.js';
import { drawSafeZoneOverlay } from './core/safezone.js';
import { buildCues, buildShots, drawCoverFrame, drawScene } from './shots.js';

const params = new URLSearchParams(location.search);
const isCapture = params.has('capture');
const showSafeZone = params.has('safezone');

let script = null;
let shots = [];
let cues = [];

function renderAt(t) {
  cv.width = 1080;
  cv.height = 1920;
  const { darkScene } = drawScene(t, script);
  drawCaption(t, darkScene);
  if (showSafeZone) drawSafeZoneOverlay(ctx);
}

window.OP = {
  ready: false,
  bootError: null,
  duration: () => T.dur,
  shots: () => shots,
  cues: () => cues,
  captions: () =>
    captionList().map((c) => ({
      s: c.s,
      e: c.e,
      text: c.words.map((w) => (w.hi ? `*${w.txt}` : w.txt)).join(' '),
    })),
  draw: (t) => renderAt(t),
  frame: (t, q = 0.92) => {
    renderAt(t);
    return cv.toDataURL('image/jpeg', q);
  },
  cover: (aspect = '9:16', q = 0.94) => {
    cv.width = 1080;
    cv.height = aspect === '3:4' ? 1440 : 1920;
    drawCoverFrame(aspect, script);
    const data = cv.toDataURL('image/jpeg', q);
    cv.width = 1080;
    cv.height = 1920;
    return data;
  },
};

(async () => {
  try {
    script = await fetch('./script.json').then((r) => r.json());
    setStylePreset(script.style || 'sisyphus-sketch');
    await loadTiming();
    buildCaptions(script);
    shots = buildShots(script);
    cues = buildCues(script);
    window.OP.ready = true;
    renderAt(0);

    if (!isCapture) {
      let t0 = performance.now();
      const loop = (now) => {
        const t = ((now - t0) / 1000) % Math.max(0.1, T.dur);
        renderAt(t);
        requestAnimationFrame(loop);
      };
      requestAnimationFrame(loop);
    }
  } catch (err) {
    window.OP.bootError = err?.stack || String(err);
    console.error(err);
  }
})();
