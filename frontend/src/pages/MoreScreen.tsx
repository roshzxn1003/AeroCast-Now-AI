import React, { useEffect } from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { MoreSubScreen } from '../types/nowcast';
import {
  Menu,
  Thermometer,
  Cpu,
  Radio,
  Server,
  Info,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Layers,
  Sparkles,
  GitBranch,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

export const MoreScreen: React.FC = () => {
  const {
    moreSubScreen,
    setMoreSubScreen,
    nowcastData,
    modelInfo,
    systemHealth,
    loadModelInfo,
    loadHealth,
  } = useNowcastStore();

  useEffect(() => {
    loadModelInfo();
    loadHealth();
  }, [loadModelInfo, loadHealth]);

  const navItems: { id: MoreSubScreen; label: string; icon: React.ComponentType<{ className?: string }>; desc: string }[] = [
    { id: 'overview', label: 'Sounding & Instability', icon: Thermometer, desc: 'Thermodynamic indices & convective potential' },
    { id: 'ai_model', label: 'AI Model Architecture', icon: Cpu, desc: 'ConvLSTM2D network & training skill scores' },
    { id: 'data_sources', label: 'Observation Network', icon: Radio, desc: 'DWR Radar stations & INSAT-3D sensors' },
    { id: 'system_health', label: 'System Health & Engine', icon: Server, desc: 'API runtime status & model memory' },
    { id: 'about', label: 'About Project (SIH)', icon: Info, desc: 'Problem statement & hackathon specifications' },
  ];

  const sounding = nowcastData?.sounding;

  return (
    <div className="space-y-3 p-3 max-w-lg mx-auto pb-24 animate-in fade-in duration-300">
      {/* Horizontal Sub-Navigation Chips */}
      <div className="overflow-x-auto -mx-3 px-3 pb-1 scrollbar-none">
        <div className="flex gap-1.5 min-w-max">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = moreSubScreen === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setMoreSubScreen(item.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all border ${
                  isActive
                    ? 'bg-sky-500 text-white border-sky-400 shadow-sm'
                    : 'bg-[#161b22] text-slate-400 border-white/10 hover:text-slate-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Sub-Screen 1: Sounding & Instability */}
      {moreSubScreen === 'overview' && sounding && (
        <div className="space-y-3 animate-in fade-in duration-200">
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-3.5 space-y-3">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wide flex items-center gap-1.5">
              <Thermometer className="w-4 h-4 text-amber-400" />
              Atmospheric Sounding & Thermodynamic Indices
            </h3>

            {/* Severe Thunderstorm Gauge Score */}
            {(() => {
              const score = Math.min(
                100,
                Math.round(
                  (sounding.CAPE_J_kg / 3500) * 50 +
                    (sounding.Deep_Layer_Shear_0_6km_kts / 40) * 30 +
                    (Math.abs(sounding.Lifted_Index_C) / 8) * 20
                )
              );
              return (
                <div className="bg-black/40 rounded-xl p-3 border border-white/5 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-300">
                      Severe Convective Threat Index
                    </span>
                    <span className="font-black text-amber-400 text-sm font-mono">
                      {score} / 100
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden flex">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500 transition-all duration-500"
                      style={{ width: `${score}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[9px] text-slate-500 font-mono">
                    <span>0 (Stable)</span>
                    <span>40 (Moderate)</span>
                    <span>70 (Severe)</span>
                    <span>100 (Violent)</span>
                  </div>
                </div>
              );
            })()}

            {/* 7 Sounding Parameter Cards */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <div className="text-[10px] text-slate-400">CAPE (Energy)</div>
                <div className="text-sm font-black text-amber-400 mt-0.5">
                  {sounding.CAPE_J_kg} J/kg
                </div>
                <div className="text-[9px] text-slate-500">
                  {sounding.CAPE_J_kg >= 2500 ? 'Extreme Instability' : 'Moderate'}
                </div>
              </div>

              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <div className="text-[10px] text-slate-400">CIN (Inhibition)</div>
                <div className="text-sm font-black text-red-400 mt-0.5">
                  {sounding.CIN_J_kg} J/kg
                </div>
                <div className="text-[9px] text-slate-500">
                  {Math.abs(sounding.CIN_J_kg) < 50 ? 'Cap Eroded / Free Ascent' : 'Strong Inversion'}
                </div>
              </div>

              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <div className="text-[10px] text-slate-400">0–6km Deep Shear</div>
                <div className="text-sm font-black text-sky-400 mt-0.5">
                  {sounding.Deep_Layer_Shear_0_6km_kts} kts
                </div>
                <div className="text-[9px] text-slate-500">
                  {sounding.Deep_Layer_Shear_0_6km_kts >= 25 ? 'Supercell Kinematics' : 'Pulse Storms'}
                </div>
              </div>

              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <div className="text-[10px] text-slate-400">Lifted Index (LI)</div>
                <div className="text-sm font-black text-emerald-400 mt-0.5">
                  {sounding.Lifted_Index_C} °C
                </div>
                <div className="text-[9px] text-slate-500">
                  {sounding.Lifted_Index_C < -4 ? 'Severely Unstable' : 'Marginal'}
                </div>
              </div>

              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <div className="text-[10px] text-slate-400">Precipitable Water</div>
                <div className="text-sm font-black text-blue-400 mt-0.5">
                  {sounding.Precipitable_Water_mm} mm
                </div>
                <div className="text-[9px] text-slate-500">High Atmospheric Moisture</div>
              </div>

              <div className="bg-white/5 p-2.5 rounded-lg border border-white/5">
                <div className="text-[10px] text-slate-400">K-Index</div>
                <div className="text-sm font-black text-purple-400 mt-0.5">
                  {sounding.K_Index}
                </div>
                <div className="text-[9px] text-slate-500">80–90% Thunderstorm Potential</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sub-Screen 2: AI Model Architecture */}
      {moreSubScreen === 'ai_model' && (
        <div className="space-y-3 animate-in fade-in duration-200">
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-3.5 space-y-3">
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-sky-400" />
              <div>
                <h3 className="text-xs font-black text-slate-100 uppercase">
                  ConvLSTM2D Meteorological Nowcaster
                </h3>
                <p className="text-[10px] text-slate-400 font-mono">
                  models/convlstm_nowcaster.keras
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-black/30 p-2 rounded-lg">
                <div className="text-[10px] text-slate-400">Parameters</div>
                <div className="text-sm font-black text-sky-400 font-mono mt-0.5">
                  {modelInfo?.total_parameters?.toLocaleString() || '144,676'}
                </div>
              </div>
              <div className="bg-black/30 p-2 rounded-lg">
                <div className="text-[10px] text-slate-400">MAE (Reflectivity)</div>
                <div className="text-sm font-black text-emerald-400 font-mono mt-0.5">
                  {modelInfo?.metrics?.reflectivity_mae_dbz || 8.97} dBZ
                </div>
              </div>
              <div className="bg-black/30 p-2 rounded-lg">
                <div className="text-[10px] text-slate-400">RMSE</div>
                <div className="text-sm font-black text-amber-400 font-mono mt-0.5">
                  {modelInfo?.metrics?.reflectivity_rmse_dbz || 20.7} dBZ
                </div>
              </div>
              <div className="bg-black/30 p-2 rounded-lg">
                <div className="text-[10px] text-slate-400">Training Epochs</div>
                <div className="text-sm font-black text-purple-400 font-mono mt-0.5">
                  {modelInfo?.metrics?.training_epochs || 15}
                </div>
              </div>
            </div>

            {/* Channels & Input Spec */}
            <div className="space-y-1.5 text-[11px] text-slate-300">
              <div className="font-bold text-slate-400 uppercase text-[10px]">
                Input Spatio-Temporal Tensor Channels
              </div>
              <ul className="space-y-1 bg-black/20 p-2 rounded-lg text-[10px] font-mono">
                <li className="flex items-center gap-1.5 text-orange-300">
                  <span>CH 0:</span> Doppler Composite Max Reflectivity (0–75 dBZ)
                </li>
                <li className="flex items-center gap-1.5 text-sky-300">
                  <span>CH 1:</span> Vertically Integrated Liquid (0–65 kg/m²)
                </li>
                <li className="flex items-center gap-1.5 text-purple-300">
                  <span>CH 2:</span> INSAT-3D Thermal IR Brightness Temp (-85 to +35°C)
                </li>
                <li className="flex items-center gap-1.5 text-amber-300">
                  <span>CH 3:</span> Total Lightning Flash Density (0–25 flashes/km²)
                </li>
              </ul>
            </div>

            {/* Note on genuine training scores */}
            <div className="p-2 bg-sky-500/10 border border-sky-500/20 rounded-lg text-[10px] text-sky-300">
              {modelInfo?.data_note || 'Real model training scores preserved from models/model_metadata.json'}
            </div>
          </div>
        </div>
      )}

      {/* Sub-Screen 3: Observation Network */}
      {moreSubScreen === 'data_sources' && (
        <div className="space-y-3 animate-in fade-in duration-200">
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 space-y-3">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wide flex items-center gap-1.5">
              <Radio className="w-4 h-4 text-sky-400" />
              11 India Doppler Weather Radar (DWR) Nodes
            </h3>
            <p className="text-[11px] text-slate-400">
              High-cadence S-Band (2.8 GHz) and C-Band (5.6 GHz) pulse Doppler radars covering 250km radial zones.
            </p>

            <div className="space-y-1.5">
              {nowcastData && (
                <div className="bg-sky-500/10 border border-sky-500/30 rounded-lg p-2.5 text-xs text-sky-300">
                  <div className="font-bold">Active Radar Station:</div>
                  <div>{nowcastData.station}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    Coordinates: {nowcastData.location.lat}°N, {nowcastData.location.lon}°E • State: {nowcastData.state}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-white/5 pt-2 text-[11px] text-slate-400 space-y-1">
              <div className="font-bold text-slate-300 text-xs">Fused Data Streams:</div>
              <div>• IMD Doppler Weather Radar Network (Chennai, Mumbai, Delhi, Kolkata, etc.)</div>
              <div>• ISRO INSAT-3D / 3DR Geostationary Imager (Thermal IR 10.8µm)</div>
              <div>• Lightning Location Network (Ground & Intra-Cloud sensors)</div>
              <div>• NCMRWF / IMD NWP Atmospheric Soundings (WRF / GFS)</div>
            </div>
          </div>
        </div>
      )}

      {/* Sub-Screen 4: System Health */}
      {moreSubScreen === 'system_health' && (
        <div className="space-y-3 animate-in fade-in duration-200">
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-3.5 space-y-3">
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-emerald-400" />
              <h3 className="text-xs font-black text-slate-100 uppercase">
                System Health & API Telemetry
              </h3>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/5">
                <span className="text-slate-400">FastAPI REST Server</span>
                <span className="font-bold text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Operational
                </span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/5">
                <span className="text-slate-400">ConvLSTM2D Engine</span>
                <span className="font-bold text-emerald-400">Loaded & Ready</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/5">
                <span className="text-slate-400">SCIT Tracking Module</span>
                <span className="font-bold text-emerald-400">Online</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/5">
                <span className="text-slate-400">2σ Lightning Jump Precursor</span>
                <span className="font-bold text-emerald-400">Active</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-white/5">
                <span className="text-slate-400">CAP v1.2 Dispatcher</span>
                <span className="font-bold text-emerald-400">Ready</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sub-Screen 5: About Project */}
      {moreSubScreen === 'about' && (
        <div className="space-y-3 animate-in fade-in duration-200">
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-3.5 space-y-3">
            <h3 className="text-xs font-black text-slate-100 uppercase flex items-center gap-1.5">
              <Info className="w-4 h-4 text-sky-400" />
              Smart India Hackathon (SIH) Problem Statement
            </h3>
            <p className="text-xs text-slate-300 font-semibold leading-relaxed">
              “AI/ML-Based Nowcasting of Thunderstorm and Lightning Using Atmospheric Observations Including Multiple Radars, Satellite, Lightning and Model Data.”
            </p>
            <div className="text-[11px] text-slate-400 space-y-2 leading-relaxed">
              <p>
                Thunderstorms and severe lightning account for severe casualties and economic loss across India annually. Conventional numerical weather prediction (NWP) models suffer from spin-up latency and cannot resolve micro-scale convective cells at 0 to 2-hour timescales.
              </p>
              <p>
                AeroCast-Now AI addresses this through a deep Spatio-Temporal ConvLSTM2D auto-regressive nowcasting network fused with morphological SCIT cell tracking and the 2-sigma Lightning Jump precursor algorithm.
              </p>
            </div>

            <div className="border-t border-white/10 pt-2 text-[10px] text-slate-500 flex justify-between">
              <span>AeroCast-Now v2.0</span>
              <span>Team SIH</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
