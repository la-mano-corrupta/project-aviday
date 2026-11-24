// Diogenes & Alexander ("Stand Out of My Sun") — 2D Canvas short shot choreography + cues + covers.
import { ctx, P, drawPaperBg, eo3, lerp, seg, sketchLine } from './core/lib.js';
import { SAFE } from './core/safezone.js';
import { cut, lineEnd, T, Wd } from './core/timing.js';
import {
  drawCitationTag,
  drawClayJar,
  drawEmperorShadow,
  drawHookPill,
  drawSageCharacter,
  drawSpeechBubble,
  drawSunburst,
} from './core/draw2d.js';

export function buildShots(script) {
  return [
    { id: 'hook', at: 0, end: cut(1), note: 'Frame-1 Emperor shadow towers over jar' },
    { id: 'jar', at: cut(1), end: cut(2), note: 'Zero money, zero status clay pithos' },
    { id: 'ask', at: cut(2), end: cut(4), note: 'Alexander steps in & blocks the sun' },
    { id: 'reply', at: cut(4), end: cut(5), note: 'Polarity flip -> Out of my sunlight!' },
    { id: 'loop', at: cut(5), end: T.dur, note: 'Own your morning -> loop back to sun' },
  ];
}

export function buildCues(script) {
  return [
    { t: 0.05, type: 'thud', gain: 0 },
    { t: cut(1), type: 'ink', gain: 0 },
    { t: cut(2), type: 'whoosh', gain: -1 },
    { t: cut(3), type: 'pop', gain: 0 },
    { t: Wd('sunlight', 4), type: 'chime', gain: 1 },
    { t: cut(5), type: 'whoosh', gain: -2 },
  ];
}

export function drawScene(t, script) {
  const s4 = cut(4);
  const darkPhase = t >= cut(2) && t < Wd('sunlight', 4);
  drawPaperBg(t, darkPhase);

  // Continuous gentle camera push inside safe frame
  const zoom = 1 + 0.03 * Math.sin((t / Math.max(1, T.dur)) * Math.PI);
  ctx.save();
  ctx.translate(SAFE.cx, SAFE.stageCenterY);
  ctx.scale(zoom, zoom);
  ctx.translate(-SAFE.cx, -SAFE.stageCenterY);

  // Ground ink horizon line well clear of captions (y=925 vs captions y=1125)
  sketchLine(SAFE.x0 + 30, 925, SAFE.x1 - 30, 925, t, 99, darkPhase ? '#F2EAD8' : P.ink, 4.5);

  if (t < cut(1)) {
    // Beat 1 (0-3s): Emperor silhouette + crown towering over Diogenes in jar
    const k = eo3(seg(t, 0, 0.45));
    drawSunburst(SAFE.x1 - 120, 560, 44, t);
    drawEmperorShadow(SAFE.cx - 110, lerp(835, 735, k), 0.88, t);
    drawClayJar(SAFE.cx + 170, 820, 0.72, t, false);
    drawSageCharacter(SAFE.cx + 120, 790, 0.58, t, { mood: 'deadpan', pose: 'sit' });
    drawHookPill(script.lines[0]?.hookText || 'OFFERED ANYTHING', t, 1, false);
  } else if (t < cut(2)) {
    // Beat 2: Bare Object — Clay Jar & Zero Status
    const k = eo3(seg(t, cut(1), cut(1) + 0.4));
    drawClayJar(SAFE.cx, 790, lerp(0.85, 1.0, k), t, false);
    drawSageCharacter(SAFE.cx - 85, 780, 0.76, t, { mood: 'calm', pose: 'sit' });
    drawSpeechBubble(SAFE.cx + 150, 600, 'ZERO RENT', t, false);
    drawHookPill('DIOGENES OF SINOPE', t, 0.9, false);
  } else if (t < cut(4)) {
    // Beat 3-4: Dark polarity flip — Alexander blocks the sun
    const shadowX = lerp(SAFE.cx - 210, SAFE.cx - 35, eo3(seg(t, cut(2), cut(3))));
    drawSunburst(SAFE.cx + 210, 550, 40, t, '#9C9484', true);
    // Cast dark diagonal shadow beam across Diogenes
    ctx.save();
    ctx.fillStyle = 'rgba(8, 9, 11, 0.68)';
    ctx.beginPath();
    ctx.moveTo(shadowX - 60, 600);
    ctx.lineTo(SAFE.cx + 250, 925);
    ctx.lineTo(SAFE.cx - 250, 925);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    drawEmperorShadow(shadowX, 720, 0.86, t);
    drawSageCharacter(SAFE.cx + 165, 810, 0.7, t, { mood: 'deadpan', dark: true });
    if (t >= cut(3)) {
      drawSpeechBubble(SAFE.cx - 35, 550, '"NAME ONE FAVOR"', t, true);
    }
    drawHookPill('PLUTARCH · ALEXANDER 14', t, 0.85, true);
  } else if (t < cut(5)) {
    // Beat 5: Sun bursts back when Diogenes answers
    const sunTrigger = Wd('sunlight', 4);
    const k = eo3(seg(t, sunTrigger, sunTrigger + 0.45));
    const empX = lerp(SAFE.cx - 50, SAFE.x0 - 240, k);
    drawSunburst(SAFE.cx + 185, 555, lerp(48, 72, k), t);
    if (empX > SAFE.x0 - 220) {
      drawEmperorShadow(empX, 730, 0.84, t);
    }
    drawSageCharacter(SAFE.cx - 10, 790, 0.92, t, {
      mood: t >= sunTrigger ? 'smile' : 'deadpan',
      pose: 'point',
      blink: Math.sin(t * 7) > 0.95,
    });
    drawSpeechBubble(SAFE.cx - 20, 575, '"OUT OF MY SUN"', t, true);
  } else {
    // Beat 6: Loop-ready calm close dissolving back toward Frame-1 sun
    const k = eo3(seg(t, cut(5), lineEnd(5)));
    drawSunburst(SAFE.cx, 575, 68 + k * 8, t);
    drawSageCharacter(SAFE.cx, 790, 0.95, t, { mood: 'smile', pose: 'sit' });
    drawHookPill('OWN YOUR MORNING', t, 1, false);
  }

  ctx.restore();
  drawCitationTag('Plutarch · Life of Alexander 14', 0.8, darkPhase);

  return { darkScene: darkPhase };
}

export function drawCoverFrame(aspect = '9:16', script) {
  const w = 1080;
  const h = aspect === '3:4' ? 1440 : 1920;
  const cy = h / 2;

  // High-contrast nocturnal dark charcoal + warm gold sun separation
  ctx.fillStyle = '#0E0F12';
  ctx.fillRect(0, 0, w, h);

  const glow = ctx.createRadialGradient(468, cy - 80, 40, 468, cy - 80, 560);
  glow.addColorStop(0, 'rgba(232, 170, 66, 0.48)');
  glow.addColorStop(1, 'rgba(14, 15, 18, 0)');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, w, h);

  // Keep focal subject & 2-word headline inside middle third so 4:5 / 1:1 / 3:4 crops never slice
  drawSunburst(640, cy - 195, 58, 0.5, '#E8AA42', true);
  drawSageCharacter(468, cy - 15, 1.38, 0.2, { mood: 'deadpan', pose: 'point', dark: true });

  ctx.save();
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = '900 104px -apple-system, BlinkMacSystemFont, "Inter", sans-serif';
  const headline = script.cover?.headline || 'OWN NOTHING.';
  ctx.lineWidth = 22;
  ctx.strokeStyle = '#08090B';
  ctx.strokeText(headline, 468, cy + 255);
  ctx.fillStyle = '#F5B73B';
  ctx.fillText(headline, 468, cy + 255);

  ctx.font = '700 36px Georgia, serif';
  ctx.fillStyle = '#F2EAD8';
  ctx.fillText(script.cover?.sublabel || 'Diogenes of Sinope', 468, cy + 340);
  ctx.restore();
}
