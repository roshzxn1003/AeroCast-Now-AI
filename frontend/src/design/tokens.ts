/**
 * Design tokens mirrored from index.css.
 *
 * Canvas and WebGL surfaces cannot read CSS custom properties cheaply per
 * frame, so the values the globe and radar renderers need live here as plain
 * strings. index.css remains the source of truth for anything the DOM styles;
 * these constants must be kept in step with it.
 */

export const SURFACE = {
  void: '#06080b',
  base: '#0b0f14',
  raised: '#121820',
  overlay: '#18202a',
} as const;

export const INK = {
  primary: '#e9eef4',
  muted: '#96a3b2',
  faint: '#5d6a78',
} as const;

export const ACCENT = '#4cc2ff';

/** Ordered convective severity ramp. Index order is meaningful. */
export const SEVERITY_LEVELS = [
  'STABLE',
  'MARGINAL',
  'MODERATE',
  'SEVERE',
  'EXTREME',
] as const;

export type SeverityLevel = (typeof SEVERITY_LEVELS)[number];

export const SEVERITY_COLOR: Record<SeverityLevel, string> = {
  STABLE: '#4b8ea8',
  MARGINAL: '#3fae8f',
  MODERATE: '#d4a13a',
  SEVERE: '#e2703a',
  EXTREME: '#d9434e',
};

export const severityColor = (level: string): string =>
  SEVERITY_COLOR[(level as SeverityLevel)] ?? SEVERITY_COLOR.STABLE;

/**
 * Reflectivity ramp in dBZ. Stops are the operational break points used by the
 * IMD radar product suite, so the rendered field reads the same way a duty
 * forecaster expects.
 */
export const DBZ_STOPS: { dbz: number; color: string; label: string }[] = [
  { dbz: 5, color: '#1f4e6b', label: 'Trace' },
  { dbz: 20, color: '#2f8f6e', label: 'Light' },
  { dbz: 30, color: '#9dbf3f', label: 'Moderate' },
  { dbz: 40, color: '#e0b93c', label: 'Heavy' },
  { dbz: 50, color: '#e2743a', label: 'Intense' },
  { dbz: 60, color: '#d1394b', label: 'Severe' },
  { dbz: 70, color: '#b84fc4', label: 'Extreme' },
];

/** Nearest ramp colour for a reflectivity value. */
export const dbzColor = (dbz: number): string => {
  let chosen = DBZ_STOPS[0].color;
  for (const stop of DBZ_STOPS) {
    if (dbz >= stop.dbz) chosen = stop.color;
  }
  return chosen;
};

export const FLASH = {
  /** Cloud-to-ground: the flashes that reach people and infrastructure. */
  cg: '#ffd45e',
  /** Intra-cloud: aloft, an electrification precursor. */
  ic: '#7fb6ff',
} as const;

/**
 * Data provenance. The UI must never let measured, derived and modelled values
 * look alike, so every surfaced figure resolves to one of these.
 */
export type Provenance = 'LIVE' | 'LIVE_REAL_DATA' | 'HYBRID' | 'SIMULATION' | 'LIVE-DERIVED' | 'MODEL' | 'STALE' | 'UNAVAILABLE';

export const PROVENANCE: Record<
  Provenance,
  { color: string; label: string; description: string }
> = {
  LIVE: {
    color: '#3fae8f',
    label: 'LIVE',
    description: 'Measured by an upstream observation network.',
  },
  LIVE_REAL_DATA: {
    color: '#10b981',
    label: 'LIVE REAL DATA',
    description: 'Authentic live IMD/RainViewer radar, INSAT-3D satellite, and Blitzortung LDN.',
  },
  HYBRID: {
    color: '#f59e0b',
    label: 'HYBRID',
    description: 'Real-world live observations with continuous convective background alignment.',
  },
  SIMULATION: {
    color: '#a855f7',
    label: 'SIMULATION',
    description: 'Procedural synthetic convective scenario for testing and demonstration.',
  },
  'LIVE-DERIVED': {
    color: '#d4a13a',
    label: 'DERIVED',
    description: 'Computed from live measurements, not directly observed.',
  },
  MODEL: {
    color: '#8b93a0',
    label: 'MODEL',
    description: 'Produced by the nowcasting model or its simulated observation layer.',
  },
  STALE: {
    color: '#e2703a',
    label: 'STALE',
    description: 'Upstream provider unreachable — showing the last good retrieval.',
  },
  UNAVAILABLE: {
    color: '#d9434e',
    label: 'OFFLINE',
    description: 'Provider has not responded within the timeout window.',
  },
};

/**
 * Categorical chart series colours.
 *
 * Stepped for this dark chart surface (#0b0f14) and validated: OKLCH lightness
 * band 0.48-0.67, chroma floor cleared, worst adjacent CVD Delta-E 9.4
 * (deutan), normal-vision Delta-E 26.5, all above 3:1 contrast on the surface.
 *
 * Assigned in fixed order and never cycled — a metric keeps its colour no
 * matter how many series a view happens to show.
 */
export const CHART_SERIES = ['#3987e5', '#d95926', '#199e70'] as const;

/** Recessive chart furniture: grid lines and axis ink. */
export const CHART_GRID = 'rgba(255,255,255,0.07)';
export const CHART_AXIS_INK = '#5d6a78';
