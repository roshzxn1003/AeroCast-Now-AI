import { create } from 'zustand';
import {
  NowcastResponse,
  RadarStation,
  ChannelMode,
  StormScenario,
  ActiveTab,
  MoreSubScreen,
  ModelMetadata,
  SystemHealth,
  OutputDataSource,
  DataPipelineStatus,
  LivePipelineStatus,
  StormCell,
} from '../types/nowcast';
import {
  fetchStations,
  fetchNowcast,
  fetchLiveNowcast,
  fetchLiveStatus,
  fetchModelInfo,
  fetchHealth,
  fetchDataPipelineStatus,
  DEFAULT_STATIONS,
} from '../services/api';

export interface GlobeLayers {
  earth: boolean;
  radar: boolean;
  lightning: boolean;
  lightningMode: 'flashes' | 'density';
  stormCells: boolean;
  aiPrediction: boolean;
  stormTracks: boolean;
  soundingNodes: boolean;
  districts: boolean;
}

export interface TimeStepLabel {
  index: number;
  label: string;
  shortLabel: string;
  isForecast: boolean;
  leadTimeMin: number;
}

export const TIME_STEPS: TimeStepLabel[] = [
  { index: 0, label: '-45 min [Observed]', shortLabel: '-45m', isForecast: false, leadTimeMin: -45 },
  { index: 1, label: '-30 min [Observed]', shortLabel: '-30m', isForecast: false, leadTimeMin: -30 },
  { index: 2, label: '-15 min [Observed]', shortLabel: '-15m', isForecast: false, leadTimeMin: -15 },
  { index: 3, label: '0 min [NOW - Observed]', shortLabel: 'NOW', isForecast: false, leadTimeMin: 0 },
  { index: 4, label: '+15 min [AI Nowcast]', shortLabel: '+15m', isForecast: true, leadTimeMin: 15 },
  { index: 5, label: '+30 min [AI Nowcast]', shortLabel: '+30m', isForecast: true, leadTimeMin: 30 },
  { index: 6, label: '+45 min [AI Nowcast]', shortLabel: '+45m', isForecast: true, leadTimeMin: 45 },
  { index: 7, label: '+60 min [AI Nowcast]', shortLabel: '+60m', isForecast: true, leadTimeMin: 60 },
  { index: 8, label: '+90 min [AI Nowcast]', shortLabel: '+90m', isForecast: true, leadTimeMin: 90 },
  { index: 9, label: '+120 min [AI Nowcast]', shortLabel: '+120m', isForecast: true, leadTimeMin: 120 },
];

interface NowcastState {
  // Navigation & View
  activeTab: ActiveTab;
  moreSubScreen: MoreSubScreen;
  channelMode: ChannelMode;
  timeIndex: number;
  isPlaying: boolean;

  // UI Mode (Citizen for plain English vs Pro for scientific telemetry)
  uiMode: 'citizen' | 'pro';
  outputDataSource: OutputDataSource;
  soundEnabled: boolean;
  earthTheme: 'night' | 'day';
  selectedCity: string;

  // Parameters
  selectedStation: string;
  stormScenario: StormScenario;
  hasJump: boolean;

  // Data
  stations: RadarStation[];
  nowcastData: NowcastResponse | null;
  modelInfo: ModelMetadata | null;
  systemHealth: SystemHealth | null;
  dataPipelineStatus: DataPipelineStatus | null;
  livePipelineStatus: LivePipelineStatus | null;

  // Globe Layers & Visualization (Phase 6)
  layers: GlobeLayers;
  radarOpacity: number;
  selectedStormCell: StormCell | null;

  // Status
  isLoading: boolean;
  error: string | null;

  // Actions
  setActiveTab: (tab: ActiveTab) => void;
  setMoreSubScreen: (sub: MoreSubScreen) => void;
  setChannelMode: (mode: ChannelMode) => void;
  setTimeIndex: (idx: number) => void;
  togglePlayback: () => void;
  setUiMode: (mode: 'citizen' | 'pro') => void;
  setOutputDataSource: (source: OutputDataSource) => void;
  setSoundEnabled: (enabled: boolean) => void;
  setEarthTheme: (theme: 'night' | 'day') => void;
  setSelectedCity: (cityId: string) => void;
  setSelectedStation: (station: string) => void;
  setStormScenario: (scenario: StormScenario) => void;
  setHasJump: (hasJump: boolean) => void;
  setLayers: (layers: Partial<GlobeLayers>) => void;
  setRadarOpacity: (opacity: number) => void;
  setSelectedStormCell: (cell: StormCell | null) => void;
  loadStations: () => Promise<void>;
  loadNowcast: () => Promise<void>;
  loadModelInfo: () => Promise<void>;
  loadHealth: () => Promise<void>;
  loadDataPipelineStatus: () => Promise<void>;
  loadLiveStatus: () => Promise<void>;
}

export const useNowcastStore = create<NowcastState>((set, get) => ({
  activeTab: 'nowcast',
  moreSubScreen: 'overview',
  channelMode: 'dbz',
  timeIndex: 3, // Default to NOW (0 min observed)
  isPlaying: false,

  uiMode: 'citizen', // Default to citizen friendly mode
  outputDataSource: 'all', // Default: Combined Live Observations & AI Model
  soundEnabled: false, // Default muted until user toggles on
  earthTheme: 'night',
  selectedCity: 'chennai',

  selectedStation: 'Chennai DWR (Sriharikota/Port)',
  stormScenario: 'Live Observation',
  hasJump: false,

  // Globe Layers & Visualization Defaults
  layers: {
    earth: true,
    radar: true,
    lightning: true,
    lightningMode: 'flashes',
    stormCells: true,
    aiPrediction: true,
    stormTracks: true,
    soundingNodes: true,
    districts: true,
  },
  radarOpacity: 0.75,
  selectedStormCell: null,

  stations: DEFAULT_STATIONS,
  nowcastData: null,
  modelInfo: null,
  systemHealth: null,
  dataPipelineStatus: null,
  livePipelineStatus: null,

  isLoading: false,
  error: null,

  setActiveTab: (tab) => set({ activeTab: tab }),
  setMoreSubScreen: (sub) => set({ moreSubScreen: sub }),
  setChannelMode: (mode) => set({ channelMode: mode }),
  setTimeIndex: (idx) => set({ timeIndex: Math.max(0, Math.min(9, idx)) }),
  setUiMode: (mode) => set({ uiMode: mode }),
  setOutputDataSource: (source) => set({ outputDataSource: source }),
  setSoundEnabled: (enabled) => set({ soundEnabled: enabled }),
  setEarthTheme: (theme) => set({ earthTheme: theme }),
  setSelectedCity: (cityId) => set({ selectedCity: cityId }),
  setLayers: (updated) => set((s) => ({ layers: { ...s.layers, ...updated } })),
  setRadarOpacity: (opacity) => set({ radarOpacity: Math.max(0.05, Math.min(1.0, opacity)) }),
  setSelectedStormCell: (cell) => set({ selectedStormCell: cell }),

  togglePlayback: () => {
    const { isPlaying } = get();
    set({ isPlaying: !isPlaying });
  },

  setSelectedStation: (station) => {
    set({ selectedStation: station });
    get().loadNowcast();
  },

  setStormScenario: (scenario) => {
    set({ stormScenario: scenario });
    get().loadNowcast();
  },

  setHasJump: (hasJump) => {
    set({ hasJump });
    get().loadNowcast();
  },

  loadStations: async () => {
    try {
      const stations = await fetchStations();
      set({ stations });
    } catch (err: any) {
      console.warn('Using default stations:', err.message);
    }
  },

  loadNowcast: async () => {
    const { selectedStation, stormScenario } = get();
    set({ isLoading: true, error: null });
    try {
      const isSim = stormScenario !== 'Live Observation';
      const data = isSim
        ? await fetchNowcast(selectedStation, stormScenario, 6)
        : await fetchLiveNowcast(selectedStation, stormScenario, 4, 'hybrid');
      set({ nowcastData: data, isLoading: false });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
    }
  },

  loadModelInfo: async () => {
    try {
      const modelInfo = await fetchModelInfo();
      set({ modelInfo });
    } catch (err: any) {
      console.warn('Model info load error:', err.message);
    }
  },

  loadHealth: async () => {
    try {
      const systemHealth = await fetchHealth();
      set({ systemHealth });
    } catch (err: any) {
      console.warn('Health check error:', err.message);
    }
  },

  loadDataPipelineStatus: async () => {
    try {
      const dataPipelineStatus = await fetchDataPipelineStatus();
      set({ dataPipelineStatus });
    } catch (err: any) {
      console.warn('Data pipeline status check error:', err.message);
    }
  },

  loadLiveStatus: async () => {
    try {
      const livePipelineStatus = await fetchLiveStatus();
      set({ livePipelineStatus });
    } catch (err: any) {
      console.warn('Live pipeline status check error:', err.message);
    }
  },
}));

