import React from 'react';
import { AbsoluteFill } from 'remotion';
import { SAFE } from '../styles/tokens';

export const SafeZoneOverlay: React.FC<{ visible?: boolean }> = ({ visible = false }) => {
  if (!visible) return null;
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <div
        style={{
          position: 'absolute',
          left: SAFE.x0,
          top: SAFE.yTopOrganic,
          width: SAFE.x1 - SAFE.x0,
          height: SAFE.yBottom - SAFE.yTopOrganic,
          border: '3px dashed #22c55e',
          boxSizing: 'border-box',
        }}
      >
        <span style={{ color: '#22c55e', fontSize: 20, fontWeight: 700, padding: 8, display: 'block' }}>
          ALL-3 SAFE BOX (823x868, cx=468)
        </span>
      </div>
    </AbsoluteFill>
  );
};
