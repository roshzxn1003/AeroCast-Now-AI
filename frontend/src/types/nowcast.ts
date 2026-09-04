export interface RadarStation {
  name: string;
  lat: number;
  lon: number;
  state: string;
  radar_type: string;
  range_km: number;
  freq_ghz: number;
  base_cape?: number;
  base_cin?: number;
  base_shear?: number;
}

export interface StormCell {
  cell_id: string;
  centroid_pixel: [number, number];
  area_km2: number;
  max_dbz: number;
  mean_dbz: number;
  max_vil_kg_m2: number;
  severity: string;
  color: string;
  speed_kmh: number;
  heading_deg: number;
  hail_risk_pct: number;
  projected_15min: [number, number];
  projected_30min: [number, number];
  projected_60min: [number, number];
}

export interface LightningJumpResult {
  jump_detected: boolean;
  status: string;
  sigma_metric: number;
  current_rate_fpm: number;
  dfr_dt: number;
  estimated_lead_time_min: number;
  message: string;
  color: string;
  threat_level: string;
}

export interface SoundingParameters {
  CAPE_J_kg: number;
  CIN_J_kg: number;
  Deep_Layer_Shear_0_6km_kts: number;
  Lifted_Index_C: number;
  Precipitable_Water_mm: number;
  K_Index: number;
  Total_Totals_Index: number;
}

export interface CAPBulletin {
  identifier: string;
  sender: string;
  sent: string;
  status: string;
  msgType: string;
  scope: string;
  info: {
    category: string;
    event: string;
    urgency: string;
    severity: string;
    certainty: string;
    eventCode: string;
    headline: string;
    description: string;
    instruction: string;
    area: {
      areaDesc: string;
      circle: string;
    };
    parameters: {
      CAPE: string;
      Deep_Layer_Shear: string;
      Lightning_Jump_Status: string;
      Active_Convective_Cores: number;
    };
  };
}

export interface ForecastStep {
  lead_time_min: number;
  cells: StormCell[];
  max_dbz: number;
  max_vil: number;
  min_tir_c: number;
  total_flash_rate: number;
}

export interface GridPoint {
  x: number;
  y: number;
  v: number;
}

export interface ForecastGrid {
  lead_time_min: number;
  dbz: GridPoint[];
  vil: GridPoint[];
}

export interface NowcastResponse {
  data_note: string;
  inference_time_ms: number;
  station: string;
  location: { lat: number; lon: number };
  state: string;
  storm_mode: string;
  timestamp: string;
  observation: {
    max_dbz: number;
    max_vil: number;
    min_tir_c: number;
    flash_rate_fpm: number;
    storm_cells: StormCell[];
    dbz_grid: GridPoint[];
  };
  sounding: SoundingParameters;
  forecast: ForecastStep[];
  forecast_grids: ForecastGrid[];
  lightning_jump: LightningJumpResult;
  cap_bulletin: CAPBulletin;
}

export interface FlashTimeSeriesPoint {
  minutes_ago: number;
  total_flash_rate: number;
  ic_flash_rate: number;
  cg_flash_rate: number;
}

export interface ModelMetadata {
  architecture: string;
  input_shape: number[];
  output_shape: number[];
  channels: string[];
  forecast_lead_times_minutes: number[];
  total_parameters: number;
  metrics: {
    reflectivity_mae_dbz: number | null;
    reflectivity_rmse_dbz: number | null;
    training_epochs: number | null;
    training_samples: number | null;
    validation_samples: number | null;
  };
  threshold_metrics: Record<string, Record<string, number>>;
  data_note: string;
}

export interface SystemHealth {
  status: string;
  timestamp: string;
  uptime_since: string;
  model_loaded: boolean;
  model_params: number;
  api_version: string;
  services: {
    nowcasting_engine: string;
    observation_service: string;
    convlstm_model: string;
  };
}

export type ChannelMode = 'dbz' | 'vil' | 'tir' | 'flash';
export type StormScenario = 'Severe Squall Line' | 'Supercell Thunderstorm' | 'Multi-Cell Cluster';
export type ActiveTab = 'nowcast' | 'alerts' | 'storms' | 'risk' | 'more';
export type MoreSubScreen = 'overview' | 'lightning' | 'radar_sat' | 'ai_model' | 'data_sources' | 'system_health' | 'historical' | 'settings' | 'about';
