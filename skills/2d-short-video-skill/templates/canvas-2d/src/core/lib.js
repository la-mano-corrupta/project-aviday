// Core canvas helpers, style presets, easings, and organic hand-drawn 2D primitives.
export const cv = document.getElementById('cv');
export const ctx = cv.getContext('2d');

export const STYLES = {
  'sisyphus-sketch': {
    bg: '#F4EFE6',
    bgDark: '#171614',
    ink: '#1B1A17',
    inkMuted: '#6B655B',
    accent: '#D95D39',
    accentAlt: '#E8AA42',
    captionFill: '#FFFFFF',
    captionHighlight: '#FFD166',
    captionStroke: '#1B1A17',
    wobble: 1.5,
    boilFps: 8,
    stroke: 5.5,
  },
  'dark-academia-monograph': {
    bg: '#0E0F12',
    bgDark: '#08090B',
    ink: '#F2EAD8',
    inkMuted: '#9C9484',
    accent: '#D4A853',
    accentAlt: '#9E3B33',
    captionFill: '#F2EAD8',
    captionHighlight: '#D4A853',
    captionStroke: '#08090B',
    wobble: 0.4,
    boilFps: 12,
    stroke: 4.2,
  },
  'school-of-thought': {
    bg: '#FAF5EB',
    bgDark: '#1D2939',
    ink: '#1D2939',
    inkMuted: '#667085',
    accent: '#D66853',
    accentAlt: '#6A8E7F',
    captionFill: '#FFFFFF',
    captionHighlight: '#F5B73B',
    captionStroke: '#1D2939',
    wobble: 0,
    boilFps: 30,
    stroke: 5.0,
  },
  'socratic-duo': {
    bg: '#F7F4EA',
    bgDark: '#18222F',
    ink: '#18222F',
    inkMuted: '#5D697A',
    accent: '#E07A5F',
    accentAlt: '#3D5A80',
    captionFill: '#FFFFFF',
    captionHighlight: '#FFD166',
    captionStroke: '#18222F',
    wobble: 0.8,
    boilFps: 10,
    stroke: 5.0,
  },
};

export let P = STYLES['sisyphus-sketch'];
export function setStylePreset(id) {
  P = STYLES[id] || STYLES['sisyphus-sketch'];
}

export const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
export const lerp = (a, b, k) => a + (b - a) * k;
export const seg = (t, a, b) => clamp((t - a) / Math.max(1e-4, b - a));
export const eo3 = (k) => 1 - (1 - k) ** 3;
export const eob = (k) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * (k - 1) ** 3 + c1 * (k - 1) ** 2;
};

function hash2(n, boilTick) {
  const x = Math.sin(n * 127.1 + boilTick * 311.7) * 43758.5453;
  return (x - Math.floor(x)) * 2 - 1;
}

export function drawPaperBg(t, dark = false) {
  ctx.fillStyle = dark ? P.bgDark : P.bg;
  ctx.fillRect(0, 0, cv.width, cv.height);

  // Subtle ambient radial vignette
  const g = ctx.createRadialGradient(468, 780, 120, 468, 860, 1100);
  g.addColorStop(0, dark ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.22)');
  g.addColorStop(1, dark ? 'rgba(0,0,0,0.45)' : 'rgba(27,26,23,0.08)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, cv.width, cv.height);

  // Minimal sketchy grain marks
  const tick = Math.floor(t * (P.boilFps || 8));
  ctx.fillStyle = dark ? 'rgba(255,255,255,0.04)' : 'rgba(27,26,23,0.035)';
  for (let i = 0; i < 18; i++) {
    const px = 40 + ((i * 197 + tick * 7) % 1000);
    const py = 120 + ((i * 313) % 1680);
    ctx.fillRect(px, py, 3, 3);
  }
}

export function sketchLine(x1, y1, x2, y2, t = 0, seed = 1, color = P.ink, width = P.stroke) {
  const tick = Math.floor(t * P.boilFps);
  const w = P.wobble;
  const mx = (x1 + x2) / 2 + hash2(seed * 3.1, tick) * w * 2.2;
  const my = (y1 + y2) / 2 + hash2(seed * 7.3, tick) * w * 2.2;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();
  ctx.moveTo(x1 + hash2(seed, tick) * w, y1 + hash2(seed + 1, tick) * w);
  ctx.quadraticCurveTo(mx, my, x2 + hash2(seed + 2, tick) * w, y2 + hash2(seed + 3, tick) * w);
  ctx.stroke();
  ctx.restore();
}

export function sketchCircle(cx, cy, r, t = 0, seed = 1, fill = null, stroke = P.ink, width = P.stroke) {
  const tick = Math.floor(t * P.boilFps);
  const w = P.wobble;
  ctx.save();
  ctx.beginPath();
  const steps = 16;
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    const dr = hash2(seed + i * 0.7, tick) * w;
    const x = cx + Math.cos(a) * (r + dr);
    const y = cy + Math.sin(a) * (r + dr);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  if (fill) {
    ctx.fillStyle = fill;
    ctx.fill();
  }
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.stroke();
  }
  ctx.restore();
}
