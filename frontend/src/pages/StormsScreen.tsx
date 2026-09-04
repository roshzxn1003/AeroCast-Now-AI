import React from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { Activity, Navigation, Wind, ShieldAlert, BarChart3, TrendingUp, Compass } from 'lucide-react';
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

export const StormsScreen: React.FC = () => {
  const { nowcastData } = useNowcastStore();

  if (!nowcastData) return null;

  const cells = nowcastData.observation.storm_cells || [];

  const chartData = cells.map((c) => ({
    name: c.cell_id,
    max_dbz: c.max_dbz,
    vil: c.max_vil_kg_m2,
    hail_risk: c.hail_risk_pct,
    color: c.color,
  }));

  return (
    <div className="w-full max-w-7xl mx-auto px-3 py-3 lg:px-6 lg:py-4 space-y-4 pb-24 lg:pb-12 animate-in fade-in duration-300">
      {/* Screen Header */}
      <div>
        <h2 className="text-base lg:text-lg font-extrabold text-slate-100 flex items-center gap-2">
          <Activity className="w-5 h-5 text-orange-400" />
          SCIT Storm Cell Tracking & Kinematics
        </h2>
        <p className="text-xs text-slate-400">
          Morphological Segmentation, Centroid Tracking & Trajectory Cones (SCIT / TITAN)
        </p>
      </div>

      {/* Overview Stat Bar */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 text-center shadow">
          <div className="text-[10px] lg:text-xs text-slate-400 font-bold uppercase">
            Active Cores
          </div>
          <div className="text-xl lg:text-2xl font-black text-orange-400 font-mono mt-0.5">
            {cells.length}
          </div>
          <div className="text-[10px] text-slate-500">Threshold ≥ 40 dBZ</div>
        </div>

        <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 text-center shadow">
          <div className="text-[10px] lg:text-xs text-slate-400 font-bold uppercase">
            Mean Velocity
          </div>
          <div className="text-xl lg:text-2xl font-black text-sky-400 font-mono mt-0.5">
            42 km/h
          </div>
          <div className="text-[10px] text-slate-500">Vector ENE (65°)</div>
        </div>

        <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 text-center shadow">
          <div className="text-[10px] lg:text-xs text-slate-400 font-bold uppercase">
            Max Core dBZ
          </div>
          <div className="text-xl lg:text-2xl font-black text-red-400 font-mono mt-0.5">
            {nowcastData.observation.max_dbz.toFixed(1)}
          </div>
          <div className="text-[10px] text-slate-500">VIL {nowcastData.observation.max_vil.toFixed(1)} kg/m²</div>
        </div>
      </div>

      {/* Desktop 2-Column Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Tracked Convective Clusters Cards */}
        <div className="lg:col-span-7 space-y-3">
          <h3 className="text-xs lg:text-sm font-bold text-slate-300 uppercase tracking-wider">
            Tracked Convective Clusters ({cells.length})
          </h3>

          {cells.map((cell) => (
            <div
              key={cell.cell_id}
              className="bg-[#161b22] border border-white/10 rounded-xl p-3.5 space-y-3 shadow-lg"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: cell.color }}
                    />
                    <span className="font-extrabold text-sm lg:text-base text-slate-100">
                      {cell.cell_id}
                    </span>
                    <span
                      className="text-[9px] font-black uppercase px-2 py-0.5 rounded"
                      style={{
                        backgroundColor: `${cell.color}25`,
                        color: cell.color,
                      }}
                    >
                      {cell.severity}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1 font-mono">
                    Centroid: Pixel ({cell.centroid_pixel[0]}, {cell.centroid_pixel[1]}) • Area: {cell.area_km2} km²
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-base font-black text-orange-400 font-mono">
                    {cell.max_dbz} dBZ
                  </span>
                  <div className="text-xs font-bold text-red-400">
                    Hail Risk: {cell.hail_risk_pct}%
                  </div>
                </div>
              </div>

              {/* Cell Kinematics Row */}
              <div className="grid grid-cols-4 gap-1.5 pt-2 border-t border-white/5 text-center text-xs">
                <div className="bg-black/30 rounded-lg p-1.5">
                  <div className="text-[10px] text-slate-400">Mean dBZ</div>
                  <div className="font-bold text-slate-200 mt-0.5">
                    {cell.mean_dbz}
                  </div>
                </div>
                <div className="bg-black/30 rounded-lg p-1.5">
                  <div className="text-[10px] text-slate-400">VIL Mass</div>
                  <div className="font-bold text-sky-400 mt-0.5">
                    {cell.max_vil_kg_m2} kg/m²
                  </div>
                </div>
                <div className="bg-black/30 rounded-lg p-1.5">
                  <div className="text-[10px] text-slate-400">Speed</div>
                  <div className="font-bold text-emerald-400 mt-0.5">
                    {cell.speed_kmh} km/h
                  </div>
                </div>
                <div className="bg-black/30 rounded-lg p-1.5">
                  <div className="text-[10px] text-slate-400">Heading</div>
                  <div className="font-bold text-amber-400 mt-0.5">
                    {cell.heading_deg}° ENE
                  </div>
                </div>
              </div>

              {/* Projected Trajectory Path */}
              <div className="bg-black/40 rounded-lg p-2.5 text-xs space-y-1.5">
                <div className="flex items-center gap-1.5 text-slate-400 font-bold uppercase text-[10px]">
                  <Navigation className="w-3.5 h-3.5 text-red-400" />
                  Projected Centroid Trajectory (SCIT/TITAN Extrapolation)
                </div>
                <div className="grid grid-cols-3 gap-2 font-mono text-slate-300 text-xs">
                  <div className="bg-black/30 p-1 rounded text-center">
                    <span className="text-slate-500 block text-[9px]">+15 MIN</span>
                    ({cell.projected_15min[0]}, {cell.projected_15min[1]})
                  </div>
                  <div className="bg-black/30 p-1 rounded text-center">
                    <span className="text-slate-500 block text-[9px]">+30 MIN</span>
                    ({cell.projected_30min[0]}, {cell.projected_30min[1]})
                  </div>
                  <div className="bg-black/30 p-1 rounded text-center">
                    <span className="text-slate-500 block text-[9px]">+60 MIN</span>
                    ({cell.projected_60min[0]}, {cell.projected_60min[1]})
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Right Column: Intensity & Hail Risk Bar Charts */}
        <div className="lg:col-span-5 space-y-4">
          {/* Core Reflectivity Chart */}
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-4 space-y-3 shadow-lg">
            <div className="text-xs lg:text-sm font-bold text-slate-200">
              Convective Intensity by Storm Cell (Max dBZ)
            </div>
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 75]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0d1117',
                      borderColor: 'rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                      fontSize: '11px',
                    }}
                  />
                  <Bar dataKey="max_dbz" name="Max dBZ" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Hail Risk Probability Chart */}
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-4 space-y-3 shadow-lg">
            <div className="text-xs lg:text-sm font-bold text-slate-200">
              Hail Risk Probability (%) by Storm Cell
            </div>
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0d1117',
                      borderColor: 'rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                      fontSize: '11px',
                    }}
                  />
                  <Bar dataKey="hail_risk" name="Hail Risk %" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Radar Motion Kinematics Card */}
          <div className="bg-[#161b22] border border-white/10 rounded-xl p-3.5 space-y-2 text-xs text-slate-300">
            <div className="flex items-center gap-2 font-bold text-sky-300">
              <Compass className="w-4 h-4 text-sky-400" />
              <span>Convective Steering Flow</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Mid-tropospheric steering wind vector steers convective squall cores along ENE heading (65° azimuth) at ~42 km/h across the 250 km DWR coverage basin.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
