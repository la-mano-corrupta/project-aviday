export interface StylePreset {
  id: 'sisyphus-sketch' | 'dark-academia-monograph' | 'school-of-thought' | 'socratic-duo';
  bg: string;
  bgDark: string;
  ink: string;
  inkMuted: string;
  accent: string;
  accentAlt: string;
  captionFill: string;
  captionHighlight: string;
  captionStroke: string;
}

export const SAFE = {
  W: 1080,
  H: 1920,
  x0: 60,
  x1: 883,
  cx: 468,
  yTopOrganic: 380,
  yBottom: 1248,
  hookY: 445,
  stageY: 755,
  captionY: 1125,
  citationY: 1215,
} as const;

export const PRESETS: Record<StylePreset['id'], StylePreset> = {
  'sisyphus-sketch': {
    id: 'sisyphus-sketch',
    bg: '#F4EFE6',
    bgDark: '#171614',
    ink: '#1B1A17',
    inkMuted: '#6B655B',
    accent: '#D95D39',
    accentAlt: '#E8AA42',
    captionFill: '#FFFFFF',
    captionHighlight: '#FFD166',
    captionStroke: '#1B1A17',
  },
  'dark-academia-monograph': {
    id: 'dark-academia-monograph',
    bg: '#0E0F12',
    bgDark: '#08090B',
    ink: '#F2EAD8',
    inkMuted: '#9C9484',
    accent: '#D4A853',
    accentAlt: '#9E3B33',
    captionFill: '#F2EAD8',
    captionHighlight: '#D4A853',
    captionStroke: '#08090B',
  },
  'school-of-thought': {
    id: 'school-of-thought',
    bg: '#FAF5EB',
    bgDark: '#1D2939',
    ink: '#1D2939',
    inkMuted: '#667085',
    accent: '#D66853',
    accentAlt: '#6A8E7F',
    captionFill: '#FFFFFF',
    captionHighlight: '#F5B73B',
    captionStroke: '#1D2939',
  },
  'socratic-duo': {
    id: 'socratic-duo',
    bg: '#F7F4EA',
    bgDark: '#18222F',
    ink: '#18222F',
    inkMuted: '#5D697A',
    accent: '#E07A5F',
    accentAlt: '#3D5A80',
    captionFill: '#FFFFFF',
    captionHighlight: '#FFD166',
    captionStroke: '#18222F',
  },
};
