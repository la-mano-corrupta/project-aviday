// Reusable 2D philosophy character & metaphor components inside the 823x868 All-3 safe box.
import { ctx, P, sketchCircle, sketchLine } from './lib.js';
import { SAFE } from './safezone.js';

export function drawHookPill(text, t, alpha = 1, dark = false) {
  if (!text || alpha <= 0.01) return;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.font = '900 40px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
  const padX = 32;
  const w = Math.min(760, ctx.measureText(text).width + padX * 2);
  const h = 76;
  const x = SAFE.cx - w / 2;
  const y = SAFE.hookY - h / 2;

  ctx.fillStyle = dark ? P.accent : P.ink;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, 18);
  ctx.fill();

  ctx.fillStyle = dark ? '#111318' : '#FAF6EE';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, SAFE.cx, SAFE.hookY + 2, w - 24);
  ctx.restore();
}

export function drawCitationTag(text, alpha = 0.85, dark = false) {
  if (!text || alpha <= 0.01) return;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.font = '600 24px Georgia, serif';
  ctx.fillStyle = dark ? 'rgba(242,234,216,0.72)' : P.inkMuted;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, SAFE.cx, SAFE.citationY);
  ctx.restore();
}

export function drawSunburst(cx, cy, r, t, color = P.accentAlt, dark = false) {
  ctx.save();
  const rayStroke = dark ? '#F5B73B' : P.ink;
  const glow = ctx.createRadialGradient(cx, cy, r * 0.2, cx, cy, r * 3.1);
  glow.addColorStop(0, 'rgba(232, 170, 66, 0.55)');
  glow.addColorStop(1, 'rgba(232, 170, 66, 0)');
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(cx, cy, r * 3.1, 0, Math.PI * 2);
  ctx.fill();

  sketchCircle(cx, cy, r, t, 11, color, rayStroke, 4.5);
  for (let i = 0; i < 10; i++) {
    const a = (i / 10) * Math.PI * 2 + t * 0.35;
    const x1 = cx + Math.cos(a) * (r + 16);
    const y1 = cy + Math.sin(a) * (r + 16);
    const x2 = cx + Math.cos(a) * (r + 44 + Math.sin(t * 3 + i) * 8);
    const y2 = cy + Math.sin(a) * (r + 44 + Math.sin(t * 3 + i) * 8);
    sketchLine(x1, y1, x2, y2, t, 30 + i, rayStroke, 4);
  }
  ctx.restore();
}

export function drawClayJar(cx, cy, scale = 1, t = 0, dark = false) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale, scale);
  const stroke = dark ? '#F2EAD8' : P.ink;

  ctx.fillStyle = '#C97B4B';
  ctx.strokeStyle = stroke;
  ctx.lineWidth = P.stroke;
  ctx.beginPath();
  ctx.ellipse(0, 20, 120, 145, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  // Jar opening (dark cavity)
  ctx.fillStyle = '#2B211C';
  ctx.beginPath();
  ctx.ellipse(-65, -20, 58, 72, -0.25, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  // Subtle rim highlight
  sketchLine(-35, -90, 55, -72, t, 9, '#E4A676', 5);
  ctx.restore();
}

export function drawSageCharacter(cx, cy, scale = 1, t = 0, opts = {}) {
  const { mood = 'calm', pose = 'sit', dark = false, blink = false, facing = 1 } = opts;
  const stroke = dark ? '#F2EAD8' : P.ink;
  const faceInk = '#1B1A17';
  const fillFace = dark ? '#EFE5D3' : '#FFFDF7';

  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale * facing, scale);

  const bob = Math.sin(t * 2.4) * 4;
  ctx.translate(0, bob);

  // Body / tunic
  ctx.fillStyle = dark ? '#3B4252' : '#E7DEC8';
  ctx.strokeStyle = stroke;
  ctx.lineWidth = P.stroke;
  ctx.beginPath();
  ctx.roundRect(-48, 30, 96, pose === 'sit' ? 110 : 145, 24);
  ctx.fill();
  ctx.stroke();

  // Arms
  if (pose === 'point') {
    sketchLine(42, 55, 110, 15, t, 5, stroke, P.stroke);
    sketchLine(-42, 55, -75, 95, t, 6, stroke, P.stroke);
  } else {
    sketchLine(-42, 55, -75, 108, t, 5, stroke, P.stroke);
    sketchLine(42, 55, 72, 105, t, 6, stroke, P.stroke);
  }

  // Head
  sketchCircle(0, -32, 64, t, 2, fillFace, stroke, P.stroke);

  // Beard / hair for Diogenes / Sage vibe
  ctx.fillStyle = dark ? '#4A443D' : '#4A443D';
  ctx.beginPath();
  ctx.moveTo(-42, -5);
  ctx.quadraticCurveTo(0, 56, 42, -5);
  ctx.quadraticCurveTo(18, 12, 0, 10);
  ctx.quadraticCurveTo(-18, 12, -42, -5);
  ctx.fill();

  // Eyes (always dark ink on light face!)
  const eyeY = -42;
  if (blink) {
    sketchLine(-28, eyeY, -10, eyeY, t, 10, faceInk, 4.5);
    sketchLine(10, eyeY, 28, eyeY, t, 11, faceInk, 4.5);
  } else {
    sketchCircle(-19, eyeY, 7, t, 12, faceInk, faceInk, 1);
    sketchCircle(19, eyeY, 7, t, 13, faceInk, faceInk, 1);
  }

  // Brows & mouth by mood (always dark ink on light face!)
  if (mood === 'deadpan') {
    sketchLine(-30, eyeY - 16, -8, eyeY - 16, t, 14, faceInk, 4);
    sketchLine(8, eyeY - 16, 30, eyeY - 16, t, 15, faceInk, 4);
    sketchLine(-12, -12, 14, -12, t, 16, faceInk, 4);
  } else if (mood === 'smile') {
    sketchLine(-28, eyeY - 18, -8, eyeY - 22, t, 14, faceInk, 4);
    sketchLine(8, eyeY - 22, 28, eyeY - 18, t, 15, faceInk, 4);
    ctx.beginPath();
    ctx.strokeStyle = faceInk;
    ctx.lineWidth = 4.5;
    ctx.arc(0, -18, 16, 0.2, Math.PI - 0.2);
    ctx.stroke();
  } else {
    sketchLine(-12, -13, 12, -15, t, 16, faceInk, 4);
  }

  ctx.restore();
}

export function drawEmperorShadow(cx, cy, scale = 1, t = 0) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale, scale);

  // Towering silhouette + gold crown
  ctx.fillStyle = '#1B1A17';
  ctx.beginPath();
  ctx.moveTo(-130, 260);
  ctx.lineTo(-95, -40);
  ctx.quadraticCurveTo(0, -140, 95, -40);
  ctx.lineTo(130, 260);
  ctx.closePath();
  ctx.fill();

  // Golden crown
  ctx.fillStyle = '#E8AA42';
  ctx.strokeStyle = '#1B1A17';
  ctx.lineWidth = 4.5;
  ctx.beginPath();
  ctx.moveTo(-62, -98);
  ctx.lineTo(-74, -155);
  ctx.lineTo(-26, -124);
  ctx.lineTo(0, -172);
  ctx.lineTo(26, -124);
  ctx.lineTo(74, -155);
  ctx.lineTo(62, -98);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  // Subtle glow behind crown
  sketchCircle(0, -135, 110 + Math.sin(t * 2) * 5, t, 20, null, 'rgba(232,170,66,0.35)', 3);
  ctx.restore();
}

export function drawSpeechBubble(cx, cy, text, t, accent = false) {
  ctx.save();
  ctx.font = '800 34px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
  const w = Math.min(540, ctx.measureText(text).width + 52);
  const h = 76;
  ctx.fillStyle = accent ? P.accent : '#FFFFFF';
  ctx.strokeStyle = P.ink;
  ctx.lineWidth = 4.5;
  ctx.beginPath();
  ctx.roundRect(cx - w / 2, cy - h / 2, w, h, 20);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = accent ? '#FFFFFF' : P.ink;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, cx, cy + 2, w - 24);
  ctx.restore();
}
