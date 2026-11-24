// Cross-platform 1080x1920 safe zones (Google Ad Spec + Organic Shorts + IG Reels + TikTok).
export const SAFE = {
  W: 1080,
  H: 1920,
  // Strict composite "All-3" safe content box (823 x 868 inside 840 x 960)
  x0: 60,
  x1: 883,
  cx: 468,
  yTopAd: 288,
  yTopOrganic: 380,
  yBottom: 1248,
  hookY: 445,
  stageTop: 515,
  stageCenterY: 775,
  stageBottom: 1005,
  captionY: 1125,
  captionMaxW: 780,
  citationY: 1215,
};

export function drawSafeZoneOverlay(ctx) {
  ctx.save();
  ctx.fillStyle = 'rgba(220, 38, 38, 0.14)';
  ctx.fillRect(0, 0, SAFE.W, SAFE.yTopOrganic);
  ctx.fillRect(0, SAFE.yBottom, SAFE.W, SAFE.H - SAFE.yBottom);
  ctx.fillRect(0, SAFE.yTopOrganic, SAFE.x0, SAFE.yBottom - SAFE.yTopOrganic);
  ctx.fillRect(SAFE.x1, SAFE.yTopOrganic, SAFE.W - SAFE.x1, SAFE.yBottom - SAFE.yTopOrganic);

  ctx.strokeStyle = '#22c55e';
  ctx.lineWidth = 3;
  ctx.setLineDash([12, 8]);
  ctx.strokeRect(SAFE.x0, SAFE.yTopOrganic, SAFE.x1 - SAFE.x0, SAFE.yBottom - SAFE.yTopOrganic);

  ctx.strokeStyle = '#f59e0b';
  ctx.strokeRect(SAFE.x0 + 20, 1020, SAFE.x1 - SAFE.x0 - 40, 200);
  ctx.setLineDash([]);

  ctx.fillStyle = '#22c55e';
  ctx.font = '700 22px sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('ALL-3 SAFE BOX (823x868, cx=468)', SAFE.x0 + 12, SAFE.yTopOrganic + 32);
  ctx.fillStyle = '#f59e0b';
  ctx.fillText('CAPTION SAFE ZONE', SAFE.x0 + 32, 1050);
  ctx.restore();
}
