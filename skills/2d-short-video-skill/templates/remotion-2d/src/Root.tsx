import React from 'react';
import { Composition } from 'remotion';
import { CoverGrid } from './CoverGrid';
import { PhilosophyShort } from './PhilosophyShort';
import sampleData from './data/sample-script.json';

const FPS = 30;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Main"
        component={PhilosophyShort}
        durationInFrames={Math.round(sampleData.durationSec * FPS)}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={{
          styleId: 'dark-academia-monograph' as const,
          showSafeZone: false,
        }}
      />
      <Composition
        id="Cover3x4"
        component={CoverGrid}
        durationInFrames={1}
        fps={FPS}
        width={1080}
        height={1440}
        defaultProps={{
          styleId: 'dark-academia-monograph' as const,
        }}
      />
    </>
  );
};
