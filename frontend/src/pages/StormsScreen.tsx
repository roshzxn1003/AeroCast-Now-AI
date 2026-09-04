import React from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { Activity, Navigation, Wind, ShieldAlert, BarChart3, TrendingUp } from 'lucide-react';
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
    <div className="space-y-3 p-3 max-w-lg mx-auto pb-24 animate-in fade-in duration-300">
      {/* Screen Header */}
      <div>
        <h2 className="text-base font-extrabold text-slate-100 flex items-center gap-1.5">
          <Activity className="w-5 h-5 text-orange-400" />
          SCIT Storm Cell Tracking & Kinematics
        </h2>
        <p className="text-[11px] text-slate-400">
          Morphological Segmentation, Centroid Tracking & Trajectory Cones
        </p>
      </div>

      {/* Overview Stat Bar */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-[#161b22] border border-white/10 rounded-xl p-2.5 text-center">
          <div className="text-[10px] text-slate-400 font-bold uppercase">
            Active Cores
          </div>
          <div className="text-lg font-black text-orange-400 font-mono mt-0.5">
            {cells.length}
          </div>
          <div className="text-[9px] text-slate-500">Threshold ≥ 40 dBZ</div>
        </div>

        <div className="bg-[#161b22] border border-white/10 rounded-xl p-2.5 text-center">
          <div className="text-[10px] text-slate-400 font-bold uppercase">
            Mean Velocity
          </div>
          <div className="text-lg font-black text-sky-400 font-mono mt-0.5">
            42 km/h
          </div>
          <div className="text-[9px] text-slate-500">Vector ENE (65°)</div>
        </div>

        <div className="bg-[#161b22] border border-white/10 rounded-xl p-2.5 text-center">
          <div className="text-[10px] text-slate-400 font-bold uppercase">
            Max Core dBZ
          </div>
          <div className="text-lg font-black text-red-400 font-mono mt-0.5">
            {nowcastData.observation.max_dbz.toFixed(1)}
          </div>
          <div className="text-[9px] text-slate-500">VIL {nowcastData.observation.max_vil.toFixed(1)} kg/m²</div>
        </div>
      </div>

      {/* Convective Cells Cards */}
      <div className="space-y-2">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
          Tracked Convective Clusters
        </h3>

        {cells.map((cell) => (
          <div
            key={cell.cell_id}
            className="bg-[#161b22] border border-white/10 rounded-xl p-3 space-y-2.5"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: cell.color }}
                  />
                  <span className="font-extrabold text-sm text-slate-100">
                    {cell.cell_id}
                  </span>
                  <span
                    className="text-[9px] font-black uppercase px-1.5 py-0.5 rounded"
                    style={{
                      backgroundColor: `${cell.color}25`,
                      color: cell.color,
                    }}
                  >
                    {cell.severity}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
                  Centroid: Pixel ({cell.centroid_pixel[0]}, {cell.centroid_pixel[1]}) • Area: {cell.area_km2} km²
                </div>
              </div>

              <div className="text-right">
                <span className="text-sm font-black text-orange-400 font-mono">
                  {cell.max_dbz} dBZ
                </span>
                <div className="text-[10px] font-bold text-red-400">
                  Hail Risk: {cell.hail_risk_pct}%
                </div>
              </div>
            </div>

            {/* Cell Kinematics Row */}
            <div className="grid grid-cols-4 gap-1 pt-2 border-t border-white/5 text-center text-[10px]">
              <div className="bg-black/30 rounded p-1">
                <div className="text-slate-400">Mean dBZ</div>
                <div className="font-bold text-slate-200 mt-0.5">
                  {cell.mean_dbz}
                </div>
              </div>
              <div className="bg-black/30 rounded p-1">
                <div className="text-slate-400">VIL Mass</div>
                <div className="font-bold text-sky-400 mt-0.5">
                  {cell.max_vil_kg_m2} kg/m²
                </div>
              </div>
              <div className="bg-black/30 rounded p-1">
                <div className="text-slate-400">Speed</div>
                <div className="font-bold text-emerald-400 mt-0.5">
                  {cell.speed_kmh} km/h
                </div>
              </div>
              <div className="bg-black/30 rounded p-1">
                <div className="text-slate-400">Heading</div>
                <div className="font-bold text-amber-400 mt-0.5">
                  {cell.heading_deg}° ENE
                </div>
              </div>
            </div>

            {/* Projected Trajectory Path */}
            <div className="bg-black/40 rounded-lg p-2 text-[10px] space-y-1">
              <div className="flex items-center gap-1 text-slate-400 font-bold uppercase">
                <Navigation className="w-3 h-3 text-red-400" />
                Projected Centroid Trajectory (SCIT/TITAN)
              </div>
              <div className="grid grid-cols-3 gap-1 font-mono text-slate-300">
                <div>+15m: ({cell.projected_15min[0]}, {cell.projected_15min[1]})</div>
                <div>+30m: ({cell.projected_30min[0]}, {cell.projected_30min[1]})</div>
                <div>+60m: ({cell.projected_60min[0]}, {cell.projected_60min[1]})</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Intensity & Hail Risk Bar Charts */}
      <div className="grid grid-cols-1 gap-3">
        {/* Core Reflectivity Chart */}
        <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 space-y-2">
          <div className="text-xs font-bold text-slate-200">
            Convective Intensity by Storm Cell (Max dBZ)
          </div>
          <div className="h-36 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} />
                <YAxis stroke="#94a3b8" fontSize={10} domain={[0, 75]} />
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
        <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 space-y-2">
          <div className="text-xs font-bold text-slate-200">
            Hail Risk Probability (%) by Storm Cell
          </div>
          <div className="h-36 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} />
                <YAxis stroke="#94a3b8" fontSize={10} domain={[0, 100]} />
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
      </div>
    </div>
  );
};
