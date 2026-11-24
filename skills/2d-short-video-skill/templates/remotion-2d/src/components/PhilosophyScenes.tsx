import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { SAFE, StylePreset } from '../styles/tokens';

export type SceneMode = 'metaphor' | 'diagram' | 'chart';

export const PhilosophyScene: React.FC<{
  mode: SceneMode;
  preset: StylePreset;
  sceneStartFrame: number;
  label: string;
}> = ({ mode, preset, sceneStartFrame, label }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const localFrame = Math.max(0, frame - sceneStartFrame);
  const enter = spring({ frame: localFrame, fps, config: { damping: 16, stiffness: 120 } });
  const drawProgress = interpolate(localFrame, [0, 35], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <svg
      width={SAFE.W}
      height={SAFE.H}
      viewBox={`0 0 ${SAFE.W} ${SAFE.H}`}
      style={{ position: 'absolute', inset: 0 }}
    >
      {/* Top safe hook pill */}
      <g transform={`translate(${SAFE.cx}, ${SAFE.hookY}) scale(${0.92 + enter * 0.08})`}>
        <rect x={-320} y={-36} width={640} height={72} rx={18} fill={preset.accent} />
        <text
          x={0}
          y={11}
          textAnchor="middle"
          fontFamily="Inter, system-ui, sans-serif"
          fontWeight={900}
          fontSize={34}
          fill={preset.bgDark}
        >
          {label}
        </text>
      </g>

      {mode === 'metaphor' && (
        <g transform={`translate(${SAFE.cx}, ${SAFE.stageY}) scale(${0.9 + enter * 0.1})`}>
          {/* Inner Citadel shield metaphor */}
          <path
            d="M 0 -170 L 145 -105 L 125 65 C 110 140 50 185 0 210 C -50 185 -110 140 -125 65 L -145 -105 Z"
            fill="none"
            stroke={preset.accent}
            strokeWidth={10}
            strokeDasharray={900}
            strokeDashoffset={(1 - drawProgress) * 900}
          />
          <circle cx={0} cy={-15} r={48} fill={preset.ink} />
          <path d="M -68 115 C -68 45 68 45 68 115" fill={preset.ink} />
        </g>
      )}

      {mode === 'diagram' && (
        <g transform={`translate(${SAFE.cx}, ${SAFE.stageY})`}>
          {/* Event -> Judgment -> Calm Line Diagram */}
          <rect x={-310} y={-130} width={220} height={90} rx={18} fill="none" stroke={preset.inkMuted} strokeWidth={5} />
          <text x={-200} y={-76} textAnchor="middle" fontFamily="Inter, sans-serif" fontWeight={800} fontSize={30} fill={preset.inkMuted}>
            CHAOS
          </text>
          <line
            x1={-80}
            y1={-85}
            x2={interpolate(drawProgress, [0, 1], [-80, 75])}
            y2={-85}
            stroke={preset.accent}
            strokeWidth={6}
          />
          <rect x={90} y={-130} width={220} height={90} rx={18} fill={preset.accent} />
          <text x={200} y={-76} textAnchor="middle" fontFamily="Inter, sans-serif" fontWeight={900} fontSize={30} fill={preset.bgDark}>
            CHOICE
          </text>
          <text x={0} y={70} textAnchor="middle" fontFamily="Georgia, serif" fontSize={34} fill={preset.ink}>
            "Only your view disturbs you."
          </text>
        </g>
      )}

      {mode === 'chart' && (
        <g transform={`translate(${SAFE.cx}, ${SAFE.stageY})`}>
          {/* Hero contrast bars: Noise vs Inner Citadel */}
          <line x1={-280} y1={140} x2={280} y2={140} stroke={preset.inkMuted} strokeWidth={4} />
          <rect x={-190} y={140 - 250 * drawProgress} width={120} height={250 * drawProgress} rx={12} fill={preset.inkMuted} />
          <text x={-130} y={185} textAnchor="middle" fontFamily="Inter, sans-serif" fontWeight={700} fontSize={26} fill={preset.inkMuted}>
            OUTRAGE
          </text>
          <rect x={70} y={140 - 300 * drawProgress} width={120} height={300 * drawProgress} rx={12} fill={preset.accent} />
          <text x={130} y={185} textAnchor="middle" fontFamily="Inter, sans-serif" fontWeight={900} fontSize={26} fill={preset.accent}>
            CONTROL
          </text>
        </g>
      )}
    </svg>
  );
};
