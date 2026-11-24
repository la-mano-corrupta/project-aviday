import React from 'react';
import { spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { SAFE, StylePreset } from '../styles/tokens';

export interface CaptionChunk {
  s: number;
  e: number;
  words: Array<{ txt: string; hi: boolean }>;
}

export const KineticCaptions: React.FC<{
  chunks: CaptionChunk[];
  preset: StylePreset;
}> = ({ chunks, preset }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const active = chunks.find((c) => t >= c.s && t < c.e);
  if (!active) return null;

  const pop = spring({
    frame: Math.max(0, Math.round((t - active.s) * fps)),
    fps,
    config: { damping: 14, stiffness: 220 },
    from: 0.78,
    to: 1,
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: SAFE.x0,
        width: SAFE.x1 - SAFE.x0,
        top: SAFE.captionY - 85,
        height: 170,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '18px',
        transform: `scale(${pop})`,
        textAlign: 'center',
      }}
    >
      {active.words.map((w, i) => (
        <span
          key={`${active.s}-${i}`}
          style={{
            fontFamily: 'Inter, system-ui, sans-serif',
            fontWeight: 900,
            fontSize: 82,
            lineHeight: 1.05,
            color: w.hi ? preset.captionHighlight : preset.captionFill,
            WebkitTextStroke: `12px ${preset.captionStroke}`,
            paintOrder: 'stroke fill',
            textShadow: `0 6px 0 ${preset.captionStroke}`,
          }}
        >
          {w.txt}
        </span>
      ))}
    </div>
  );
};
