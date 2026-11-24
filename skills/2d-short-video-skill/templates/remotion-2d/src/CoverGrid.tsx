import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import sampleData from './data/sample-script.json';
import { PRESETS, StylePreset } from './styles/tokens';

export const CoverGrid: React.FC<{ styleId?: StylePreset['id'] }> = ({
  styleId = 'dark-academia-monograph',
}) => {
  const { width, height } = useVideoConfig();
  const preset = PRESETS[styleId] || PRESETS['dark-academia-monograph'];
  const cy = height / 2;

  return (
    <AbsoluteFill style={{ backgroundColor: preset.bg }}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <radialGradient id="coverGlow" cx="43%" cy="46%" r="48%">
            <stop offset="0%" stopColor={preset.accent} stopOpacity="0.35" />
            <stop offset="100%" stopColor={preset.bg} stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width={width} height={height} fill="url(#coverGlow)" />
        {/* Middle-third focal icon surviving 4:5, 1:1, and 3:4 crops */}
        <g transform={`translate(468, ${cy - 70}) scale(1.25)`}>
          <path
            d="M 0 -170 L 145 -105 L 125 65 C 110 140 50 185 0 210 C -50 185 -110 140 -125 65 L -145 -105 Z"
            fill="none"
            stroke={preset.accent}
            strokeWidth={12}
          />
          <circle cx={0} cy={-15} r={46} fill={preset.ink} />
          <path d="M -68 115 C -68 45 68 45 68 115" fill={preset.ink} />
        </g>
        <text
          x={468}
          y={cy + 275}
          textAnchor="middle"
          fontFamily="Inter, system-ui, sans-serif"
          fontWeight={900}
          fontSize={106}
          fill={preset.accent}
        >
          {sampleData.cover.headline}
        </text>
        <text
          x={468}
          y={cy + 355}
          textAnchor="middle"
          fontFamily="Georgia, serif"
          fontSize={34}
          fill={preset.ink}
        >
          {sampleData.cover.sublabel}
        </text>
      </svg>
    </AbsoluteFill>
  );
};
