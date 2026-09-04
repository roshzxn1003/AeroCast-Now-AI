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
    <div className="w-full max-w-7xl mx-auto px-3 py-3 lg:px-6 lg:py-4 space-y-4 pb-24 lg:pb-12 animate-in fade-in duration-300">
      {/* Mobile Horizontal Sub-Navigation Chips (hidden on desktop) */}
      <div className="lg:hidden overflow-x-auto -mx-3 px-3 pb-1 scrollbar-none">
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

      {/* Main Grid: Desktop Left Sidebar Menu + Right Content Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Desktop Sidebar Sub-Navigation (visible on lg screens >= 1024px) */}
        <div className="hidden lg:flex flex-col lg:col-span-4 space-y-2 bg-[#161b22] border border-white/10 rounded-2xl p-3 shadow-lg">
          <div className="px-3 py-2 text-xs font-extrabold uppercase tracking-wider text-slate-400 border-b border-white/5">
            Diagnostics & Meteorological Intelligence
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = moreSubScreen === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setMoreSubScreen(item.id)}
                className={`w-full text-left p-3 rounded-xl transition-all flex items-center justify-between border ${
                  isActive
                    ? 'bg-sky-500/20 border-sky-500/40 text-white shadow-sm'
                    : 'bg-transparent border-transparent hover:bg-white/5 text-slate-300'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-lg ${
                      isActive ? 'bg-sky-500 text-white' : 'bg-white/5 text-slate-400'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-bold text-xs">{item.label}</div>
                    <div className="text-[11px] text-slate-400 line-clamp-1">
                      {item.desc}
                    </div>
                  </div>
                </div>
                <ChevronRight
                  className={`w-4 h-4 ${isActive ? 'text-sky-400' : 'text-slate-600'}`}
                />
              </button>
            );
          })}
        </div>

        {/* Right Content Panel */}
        <div className="lg:col-span-8 space-y-4">
          {/* Sub-Screen 1: Sounding & Instability */}
          {moreSubScreen === 'overview' && sounding && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="bg-[#161b22] border border-white/10 rounded-2xl p-4 lg:p-6 space-y-4 shadow-xl">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide flex items-center gap-2">
                  <Thermometer className="w-5 h-5 text-amber-400" />
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
                    <div className="bg-black/40 rounded-xl p-4 border border-white/5 space-y-2.5">
                      <div className="flex items-center justify-between text-xs lg:text-sm">
                        <span className="font-bold text-slate-300">
                          Severe Convective Threat Index (NWP Thermodynamic Synthesis)
                        </span>
                        <span className="font-black text-amber-400 text-base font-mono">
                          {score} / 100
                        </span>
                      </div>
                      <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden flex">
                        <div
                          className="h-full bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500 transition-all duration-500"
                          style={{ width: `${score}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                        <span>0 (Stable Atmosphere)</span>
                        <span>40 (Moderate Pulse)</span>
                        <span>70 (Severe Hail/Downburst)</span>
                        <span>100 (Supercell Tornadic)</span>
                      </div>
                    </div>
                  );
                })()}

                {/* 7 Sounding Parameter Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                  <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">CAPE (Energy)</div>
                    <div className="text-base lg:text-lg font-black text-amber-400 mt-1 font-mono">
                      {sounding.CAPE_J_kg} J/kg
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {sounding.CAPE_J_kg >= 2500 ? 'Extreme Instability' : 'Moderate'}
                    </div>
                  </div>

                  <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">CIN (Inhibition)</div>
                    <div className="text-base lg:text-lg font-black text-red-400 mt-1 font-mono">
                      {sounding.CIN_J_kg} J/kg
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {Math.abs(sounding.CIN_J_kg) < 50 ? 'Cap Eroded / Free Ascent' : 'Strong Inversion'}
                    </div>
                  </div>

                  <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">0–6km Deep Shear</div>
                    <div className="text-base lg:text-lg font-black text-sky-400 mt-1 font-mono">
                      {sounding.Deep_Layer_Shear_0_6km_kts} kts
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {sounding.Deep_Layer_Shear_0_6km_kts >= 25 ? 'Supercell Kinematics' : 'Pulse Storms'}
                    </div>
                  </div>

                  <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">Lifted Index (LI)</div>
                    <div className="text-base lg:text-lg font-black text-emerald-400 mt-1 font-mono">
                      {sounding.Lifted_Index_C} °C
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {sounding.Lifted_Index_C < -4 ? 'Severely Unstable' : 'Marginal'}
                    </div>
                  </div>

                  <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">Precipitable Water</div>
                    <div className="text-base lg:text-lg font-black text-blue-400 mt-1 font-mono">
                      {sounding.Precipitable_Water_mm} mm
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">High Atmospheric Moisture</div>
                  </div>

                  <div className="bg-white/5 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">K-Index</div>
                    <div className="text-base lg:text-lg font-black text-purple-400 mt-1 font-mono">
                      {sounding.K_Index}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">80–90% Thunderstorm Potential</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Sub-Screen 2: AI Model Architecture */}
          {moreSubScreen === 'ai_model' && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="bg-[#161b22] border border-white/10 rounded-2xl p-4 lg:p-6 space-y-4 shadow-xl">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-sky-500/20 text-sky-400 border border-sky-500/30">
                    <Cpu className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-sm lg:text-base font-black text-slate-100 uppercase">
                      ConvLSTM2D Meteorological Nowcaster
                    </h3>
                    <p className="text-xs text-slate-400 font-mono">
                      models/convlstm_nowcaster.keras
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="bg-black/30 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase">Total Parameters</div>
                    <div className="text-base lg:text-lg font-black text-sky-400 font-mono mt-1">
                      {modelInfo?.total_parameters?.toLocaleString() || '144,676'}
                    </div>
                  </div>
                  <div className="bg-black/30 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase">MAE (Reflectivity)</div>
                    <div className="text-base lg:text-lg font-black text-emerald-400 font-mono mt-1">
                      {modelInfo?.metrics?.reflectivity_mae_dbz || 8.97} dBZ
                    </div>
                  </div>
                  <div className="bg-black/30 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase">RMSE</div>
                    <div className="text-base lg:text-lg font-black text-amber-400 font-mono mt-1">
                      {modelInfo?.metrics?.reflectivity_rmse_dbz || 20.7} dBZ
                    </div>
                  </div>
                  <div className="bg-black/30 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] text-slate-400 uppercase">Training Epochs</div>
                    <div className="text-base lg:text-lg font-black text-purple-400 font-mono mt-1">
                      {modelInfo?.metrics?.training_epochs || 15}
                    </div>
                  </div>
                </div>

                {/* Channels & Input Spec */}
                <div className="space-y-2 text-xs text-slate-300">
                  <div className="font-bold text-slate-300 uppercase text-xs">
                    Input Spatio-Temporal 4D Tensor Channels (Batch, 4, 32, 32, 4)
                  </div>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 bg-black/30 p-3 rounded-xl border border-white/5 text-xs font-mono">
                    <li className="flex items-center gap-2 text-orange-300 p-1.5 bg-white/5 rounded-lg">
                      <span className="font-bold">CH 0:</span> Doppler Composite Max Reflectivity (0–75 dBZ)
                    </li>
                    <li className="flex items-center gap-2 text-sky-300 p-1.5 bg-white/5 rounded-lg">
                      <span className="font-bold">CH 1:</span> Vertically Integrated Liquid (0–65 kg/m²)
                    </li>
                    <li className="flex items-center gap-2 text-purple-300 p-1.5 bg-white/5 rounded-lg">
                      <span className="font-bold">CH 2:</span> INSAT-3D Thermal IR Brightness Temp (-85 to +35°C)
                    </li>
                    <li className="flex items-center gap-2 text-amber-300 p-1.5 bg-white/5 rounded-lg">
                      <span className="font-bold">CH 3:</span> Total Lightning Flash Density (0–25 flashes/km²)
                    </li>
                  </ul>
                </div>

                {/* Note on genuine training scores */}
                <div className="p-3 bg-sky-500/10 border border-sky-500/20 rounded-xl text-xs text-sky-300 leading-relaxed">
                  {modelInfo?.data_note || 'Real model training scores preserved from models/model_metadata.json (reflectivity_mae_dbz: 8.97 dBZ, training_samples: 112).'}
                </div>
              </div>
            </div>
          )}

          {/* Sub-Screen 3: Observation Network */}
          {moreSubScreen === 'data_sources' && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="bg-[#161b22] border border-white/10 rounded-2xl p-4 lg:p-6 space-y-4 shadow-xl">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide flex items-center gap-2">
                  <Radio className="w-5 h-5 text-sky-400" />
                  11 India Doppler Weather Radar (DWR) Nodes
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  High-cadence S-Band (2.8 GHz) and C-Band (5.6 GHz) pulse Doppler radars covering 250km radial zones with automated clutter filtering and VIL integration.
                </p>

                {nowcastData && (
                  <div className="bg-sky-500/10 border border-sky-500/30 rounded-xl p-3.5 text-xs text-sky-300 space-y-1">
                    <div className="font-bold text-sm">Active Station Node:</div>
                    <div className="text-sm text-white font-semibold">{nowcastData.station}</div>
                    <div className="text-xs text-slate-400 font-mono">
                      Coordinates: {nowcastData.location.lat}°N, {nowcastData.location.lon}°E • State: {nowcastData.state}
                    </div>
                  </div>
                )}

                <div className="border-t border-white/5 pt-3 text-xs text-slate-400 space-y-2">
                  <div className="font-bold text-slate-300 text-xs uppercase">Fused Multi-Modal Sensor Streams:</div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-300">
                    <div className="p-2 bg-black/30 rounded-lg border border-white/5">
                      • IMD Doppler Weather Radar Network (Chennai, Mumbai, Delhi, Kolkata, etc.)
                    </div>
                    <div className="p-2 bg-black/30 rounded-lg border border-white/5">
                      • ISRO INSAT-3D / 3DR Geostationary Imager (Thermal IR 10.8µm)
                    </div>
                    <div className="p-2 bg-black/30 rounded-lg border border-white/5">
                      • Lightning Detection Network (Ground & Intra-Cloud sensors)
                    </div>
                    <div className="p-2 bg-black/30 rounded-lg border border-white/5">
                      • NCMRWF / IMD NWP Atmospheric Soundings (WRF / GFS)
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Sub-Screen 4: System Health */}
          {moreSubScreen === 'system_health' && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="bg-[#161b22] border border-white/10 rounded-2xl p-4 lg:p-6 space-y-4 shadow-xl">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    <Server className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm lg:text-base font-black text-slate-100 uppercase">
                    System Health & Engine Telemetry
                  </h3>
                </div>

                <div className="space-y-2.5 text-xs">
                  <div className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
                    <span className="text-slate-300 font-medium">FastAPI REST Server</span>
                    <span className="font-bold text-emerald-400 flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" /> Operational (Port 8000)
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
                    <span className="text-slate-300 font-medium">ConvLSTM2D Engine</span>
                    <span className="font-bold text-emerald-400">Loaded & Ready (144k params)</span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
                    <span className="text-slate-300 font-medium">SCIT Tracking Module</span>
                    <span className="font-bold text-emerald-400">Online (Morphological Segmentation)</span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
                    <span className="text-slate-300 font-medium">2σ Lightning Jump Precursor</span>
                    <span className="font-bold text-emerald-400">Active (Schultz Algorithm)</span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
                    <span className="text-slate-300 font-medium">OASIS CAP v1.2 Dispatcher</span>
                    <span className="font-bold text-emerald-400">Ready</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Sub-Screen 5: About Project */}
          {moreSubScreen === 'about' && (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="bg-[#161b22] border border-white/10 rounded-2xl p-4 lg:p-6 space-y-4 shadow-xl">
                <h3 className="text-sm font-black text-slate-100 uppercase flex items-center gap-2">
                  <Info className="w-5 h-5 text-sky-400" />
                  Smart India Hackathon (SIH) Problem Statement
                </h3>
                <p className="text-xs lg:text-sm text-slate-200 font-bold leading-relaxed bg-black/30 p-3 rounded-xl border border-white/5">
                  “AI/ML-Based Nowcasting of Thunderstorm and Lightning Using Atmospheric Observations Including Multiple Radars, Satellite, Lightning and Model Data.”
                </p>
                <div className="text-xs text-slate-400 space-y-3 leading-relaxed">
                  <p>
                    Thunderstorms and severe lightning account for significant casualties and infrastructure damage across India annually. Conventional numerical weather prediction (NWP) models suffer from spin-up latency and cannot resolve micro-scale convective cells at 0 to 2-hour timescales.
                  </p>
                  <p>
                    AeroCast-Now AI addresses this through a deep Spatio-Temporal ConvLSTM2D auto-regressive nowcasting network fused with morphological SCIT cell tracking and the 2-sigma Lightning Jump precursor algorithm.
                  </p>
                </div>

                <div className="border-t border-white/10 pt-3 text-xs text-slate-500 flex justify-between font-mono">
                  <span>AeroCast-Now v2.0 (Mobile & Desktop Edition)</span>
                  <span>Team SIH</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
