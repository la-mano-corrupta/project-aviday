import React, { useMemo } from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { CaptionChunk, KineticCaptions } from './components/KineticCaptions';
import { PhilosophyScene, SceneMode } from './components/PhilosophyScenes';
import { SafeZoneOverlay } from './components/SafeZoneOverlay';
import sampleData from './data/sample-script.json';
import { PRESETS, SAFE, StylePreset } from './styles/tokens';

export interface PhilosophyShortProps {
  styleId?: StylePreset['id'];
  showSafeZone?: boolean;
}

export const PhilosophyShort: React.FC<PhilosophyShortProps> = ({
  styleId = 'dark-academia-monograph',
  showSafeZone = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const preset = PRESETS[styleId] || PRESETS['dark-academia-monograph'];

  const activeLine =
    sampleData.lines.find((l) => t >= l.start && t <= l.end) ||
    sampleData.lines[sampleData.lines.length - 1];

  const captionChunks = useMemo<CaptionChunk[]>(() => {
    const out: CaptionChunk[] = [];
    for (const ln of sampleData.lines) {
      const parts = ln.caps.split('|').map((s) => s.trim()).filter(Boolean);
      const span = (ln.end - ln.start) / Math.max(1, parts.length);
      parts.forEach((p, idx) => {
        out.push({
          s: ln.start + idx * span,
          e: ln.start + (idx + 1) * span,
          words: p.split(/\s+/).map((w) => ({ txt: w.replace('*', ''), hi: w.startsWith('*') })),
        });
      });
    }
    return out;
  }, []);

  const sceneStartFrame = Math.round(activeLine.start * fps);

  return (
    <AbsoluteFill style={{ backgroundColor: preset.bg }}>
      <PhilosophyScene
        mode={(activeLine.mode as SceneMode) || 'metaphor'}
        preset={preset}
        sceneStartFrame={sceneStartFrame}
        label={activeLine.label}
      />

      <KineticCaptions chunks={captionChunks} preset={preset} />

      <div
        style={{
          position: 'absolute',
          left: SAFE.x0,
          width: SAFE.x1 - SAFE.x0,
          top: SAFE.citationY - 18,
          textAlign: 'center',
          fontFamily: 'Georgia, serif',
          fontSize: 26,
          color: preset.inkMuted,
        }}
      >
        {sampleData.citation}
      </div>

      <SafeZoneOverlay visible={showSafeZone} />
    </AbsoluteFill>
  );
};
