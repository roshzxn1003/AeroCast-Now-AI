import React from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { MetricCards } from '../components/MetricCards';
import { LightningJumpBanner } from '../components/LightningJumpBanner';
import { RadarViewport } from '../components/RadarViewport';
import { TimeScrubber } from '../components/TimeScrubber';
import { Thermometer, Activity, ArrowRight, Wind, ShieldAlert, Zap } from 'lucide-react';

export const NowcastScreen: React.FC = () => {
  const { nowcastData, setActiveTab, setMoreSubScreen } = useNowcastStore();

  if (!nowcastData) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center space-y-3 min-h-[60vh]">
        <div className="w-10 h-10 rounded-full border-2 border-sky-400 border-t-transparent animate-spin" />
        <p className="text-sm text-slate-400">
          Assembling Multi-Modal Spatio-Temporal Observation Tensor...
        </p>
      </div>
    );
  }

  const sounding = nowcastData.sounding;
  const cells = nowcastData.observation.storm_cells || [];

  return (
    <div className="w-full max-w-7xl mx-auto px-3 py-3 lg:px-6 lg:py-4 space-y-4 pb-24 lg:pb-12 animate-in fade-in duration-300">
      {/* Top 5 Metrics Row (Horizontal scroll on mobile, 5-col grid on desktop) */}
      <MetricCards />

      {/* Main Grid: Left = Radar & Scrubber, Right = Alert Banner, Storm Cells, Sounding */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* Left Column: Interactive Radar Viewport & Timeline Scrubber */}
        <div className="lg:col-span-7 xl:col-span-8 space-y-3">
          <RadarViewport />
          <TimeScrubber />
        </div>

        {/* Right Column: Precursor Alert Banner, SCIT Cells & Sounding */}
        <div className="lg:col-span-5 xl:col-span-4 space-y-3">
          {/* Critical Precursor Alert Banner */}
          <LightningJumpBanner />

          {/* Active Storm Cells Summary Card */}
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-3.5 space-y-2.5 shadow-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-orange-400" />
                <h3 className="font-bold text-xs text-slate-200 uppercase tracking-wide">
                  SCIT Storm Cells ({cells.length} Active)
                </h3>
              </div>
              <button
                onClick={() => setActiveTab('storms')}
                className="text-[11px] text-sky-400 hover:text-sky-300 font-semibold flex items-center gap-0.5"
              >
                Full Tracker
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            {cells.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-2">
                No active convective cells meeting 40 dBZ / 24 km² threshold.
              </p>
            ) : (
              <div className="space-y-2">
                {cells.slice(0, 4).map((cell) => (
                  <div
                    key={cell.cell_id}
                    className="bg-white/5 hover:bg-white/10 border border-white/5 rounded-lg p-2.5 flex items-center justify-between text-xs transition-colors"
                  >
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ backgroundColor: cell.color }}
                        />
                        <span className="font-bold text-slate-200">
                          {cell.cell_id}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {cell.area_km2} km²
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {cell.severity}
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <div className="font-bold text-orange-400 font-mono">
                        {cell.max_dbz} dBZ
                      </div>
                      <div className="text-[10px] text-red-400 font-semibold">
                        Hail Risk {cell.hail_risk_pct}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Atmospheric Sounding Quick Matrix */}
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-3.5 space-y-2.5 shadow-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Thermometer className="w-4 h-4 text-amber-400" />
                <h3 className="font-bold text-xs text-slate-200 uppercase tracking-wide">
                  Atmospheric Sounding Indices
                </h3>
              </div>
              <button
                onClick={() => {
                  setActiveTab('more');
                  setMoreSubScreen('overview');
                }}
                className="text-[11px] text-sky-400 hover:text-sky-300 font-semibold flex items-center gap-0.5"
              >
                Sounding
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                <div className="text-[10px] text-slate-400 font-medium">CAPE</div>
                <div className="font-black text-amber-400 mt-0.5">
                  {sounding.CAPE_J_kg.toFixed(0)} J/kg
                </div>
                <div className="text-[9px] text-slate-500">
                  {sounding.CAPE_J_kg > 2500 ? 'Extreme' : 'Moderate'}
                </div>
              </div>

              <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                <div className="text-[10px] text-slate-400 font-medium">CIN</div>
                <div className="font-black text-red-400 mt-0.5">
                  {sounding.CIN_J_kg.toFixed(0)} J/kg
                </div>
                <div className="text-[9px] text-slate-500">
                  {Math.abs(sounding.CIN_J_kg) < 50 ? 'Cap Broken' : 'Inhibited'}
                </div>
              </div>

              <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                <div className="text-[10px] text-slate-400 font-medium">SHEAR 0-6km</div>
                <div className="font-black text-sky-400 mt-0.5">
                  {sounding.Deep_Layer_Shear_0_6km_kts.toFixed(0)} kts
                </div>
                <div className="text-[9px] text-slate-500">
                  {sounding.Deep_Layer_Shear_0_6km_kts > 25 ? 'Supercell' : 'Multi-cell'}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center text-xs pt-1 border-t border-white/5">
              <div className="bg-white/5 p-1.5 rounded-lg">
                <div className="text-[9px] text-slate-400">Lifted Index</div>
                <div className="font-bold text-emerald-400 text-[11px] mt-0.5">
                  {sounding.Lifted_Index_C}°C
                </div>
              </div>
              <div className="bg-white/5 p-1.5 rounded-lg">
                <div className="text-[9px] text-slate-400">PWAT</div>
                <div className="font-bold text-blue-400 text-[11px] mt-0.5">
                  {sounding.Precipitable_Water_mm} mm
                </div>
              </div>
              <div className="bg-white/5 p-1.5 rounded-lg">
                <div className="text-[9px] text-slate-400">K-Index</div>
                <div className="font-bold text-purple-400 text-[11px] mt-0.5">
                  {sounding.K_Index}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
