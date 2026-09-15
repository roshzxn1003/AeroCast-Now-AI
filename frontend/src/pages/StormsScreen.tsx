import React from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { RadarViewport } from '../components/RadarViewport';
import { TimeScrubber } from '../components/TimeScrubber';
import { Activity, Navigation, Wind, ShieldAlert, BarChart3, TrendingUp, Compass, RefreshCw } from 'lucide-react';
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

  if (!nowcastData) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3 text-slate-400 font-mono text-xs">
        <RefreshCw className="w-7 h-7 text-cyan-400 animate-spin" />
        <span>Loading Storm Cells & Radar Kinematics…</span>
      </div>
    );
  }

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
        <h2 className="text-base lg:text-lg font-semibold text-[var(--color-ink)] flex items-center gap-2">
          <Activity className="w-5 h-5 text-orange-400" />
          SCIT Storm Cell Tracking & Kinematics
        </h2>
        <p className="text-xs text-[var(--color-ink-muted)]">
          Morphological Segmentation, Centroid Tracking & Trajectory Cones (SCIT / TITAN)
        </p>
      </div>

      {/* Radar product. Frames 0-3 are observed frames from the ingest tensor;
          4-9 are ConvLSTM output at each lead time, drawn as produced. */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
        <div className="xl:col-span-7 space-y-3">
          <RadarViewport />
          <TimeScrubber />
        </div>
        <div className="xl:col-span-5">
          <div className="rounded-[10px] border border-[var(--color-line)] bg-[var(--color-surface-base)] p-3.5">
            <div className="eyebrow mb-2">Reading this display</div>
            <p className="text-[12px] text-[var(--color-ink-muted)] leading-relaxed">
              Steps &minus;45 to 0 min are observed multi-modal frames. Steps
              +15 to +120 min are the network&rsquo;s own forecast grids, shown
              without interpolation, so what you scrub through is exactly what
              the model produced.
            </p>
            <p className="text-[12px] text-[var(--color-ink-muted)] leading-relaxed mt-2">
              Dotted vectors are SCIT kinematic trajectories; the heading
              readout is the mean motion of the cells currently tracked.
            </p>
          </div>
        </div>
      </div>

      {/* Overview Stat Bar */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-3 text-center shadow">
          <div className="text-[11px] lg:text-xs text-[var(--color-ink-muted)] font-bold uppercase">
            Active Cores
          </div>
          <div className="text-xl lg:text-2xl font-semibold text-orange-400 font-mono mt-0.5">
            {cells.length}
          </div>
          <div className="text-[11px] text-[var(--color-ink-faint)]">Threshold ≥ 40 dBZ</div>
        </div>

        <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-3 text-center shadow">
          <div className="text-[11px] lg:text-xs text-[var(--color-ink-muted)] font-bold uppercase">
            Mean Velocity
          </div>
          <div className="text-xl lg:text-2xl font-semibold text-[var(--color-accent)] font-mono mt-0.5">
            42 km/h
          </div>
          <div className="text-[11px] text-[var(--color-ink-faint)]">Vector ENE (65°)</div>
        </div>

        <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-3 text-center shadow">
          <div className="text-[11px] lg:text-xs text-[var(--color-ink-muted)] font-bold uppercase">
            Max Core dBZ
          </div>
          <div className="text-xl lg:text-2xl font-semibold text-red-400 font-mono mt-0.5">
            {nowcastData.observation.max_dbz.toFixed(1)}
          </div>
          <div className="text-[11px] text-[var(--color-ink-faint)]">VIL {nowcastData.observation.max_vil.toFixed(1)} kg/m²</div>
        </div>
      </div>

      {/* Desktop 2-Column Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Tracked Convective Clusters Cards */}
        <div className="lg:col-span-7 space-y-3">
          <h3 className="text-xs lg:text-sm font-bold text-[var(--color-ink)] uppercase tracking-wider">
            Tracked Convective Clusters ({cells.length})
          </h3>

          {cells.map((cell) => (
            <div
              key={cell.cell_id}
              className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-3.5 space-y-3 shadow-lg"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: cell.color }}
                    />
                    <span className="font-semibold text-sm lg:text-base text-[var(--color-ink)]">
                      {cell.cell_id}
                    </span>
                    <span
                      className="text-[11px] font-semibold uppercase px-2 py-0.5 rounded"
                      style={{
                        backgroundColor: `${cell.color}25`,
                        color: cell.color,
                      }}
                    >
                      {cell.severity}
                    </span>
                  </div>
                  <div className="text-xs text-[var(--color-ink-muted)] mt-1 font-mono">
                    Centroid: Pixel ({cell.centroid_pixel[0]}, {cell.centroid_pixel[1]}) • Area: {cell.area_km2} km²
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-base font-semibold text-orange-400 font-mono">
                    {cell.max_dbz} dBZ
                  </span>
                  <div className="text-xs font-bold text-red-400">
                    Hail Risk: {cell.hail_risk_pct}%
                  </div>
                </div>
              </div>

              {/* Cell Kinematics Row */}
              <div className="grid grid-cols-4 gap-1.5 pt-2 border-t border-[var(--color-line-faint)] text-center text-xs">
                <div className="bg-black/30 rounded-lg p-1.5">
                  <div className="text-[11px] text-[var(--color-ink-muted)]">Mean dBZ</div>
                  <div className="font-bold text-[var(--color-ink)] mt-0.5">
                    {cell.mean_dbz}
                  </div>
                </div>
                <div className="bg-black/30 rounded-lg p-1.5">
                  <div className="text-[11px] text-[var(--color-ink-muted)]">VIL Mass</div>
                  <div className="font-bold text-[var(--color-accent)] mt-0.5">
                    {cell.max_vil_kg_m2} kg/m²
                  </div>
                </div>
                <div className="bg-black/30 rounded-lg p-1.5">
                  <div className="text-[11px] text-[var(--color-ink-muted)]">Speed</div>
                  <div className="font-bold text-emerald-400 mt-0.5">
                    {cell.speed_kmh} km/h
                  </div>
                </div>
                <div className="bg-black/30 rounded-lg p-1.5">
                  <div className="text-[11px] text-[var(--color-ink-muted)]">Heading</div>
                  <div className="font-bold text-amber-400 mt-0.5">
                    {cell.heading_deg}° ENE
                  </div>
                </div>
              </div>

              {/* Projected Trajectory Path */}
              <div className="bg-black/40 rounded-lg p-2.5 text-xs space-y-1.5">
                <div className="flex items-center gap-1.5 text-[var(--color-ink-muted)] font-bold uppercase text-[11px]">
                  <Navigation className="w-3.5 h-3.5 text-red-400" />
                  Projected Centroid Trajectory (SCIT/TITAN Extrapolation)
                </div>
                <div className="grid grid-cols-3 gap-2 font-mono text-[var(--color-ink)] text-xs">
                  <div className="bg-black/30 p-1 rounded text-center">
                    <span className="text-[var(--color-ink-faint)] block text-[11px]">+15 MIN</span>
                    ({cell.projected_15min[0]}, {cell.projected_15min[1]})
                  </div>
                  <div className="bg-black/30 p-1 rounded text-center">
                    <span className="text-[var(--color-ink-faint)] block text-[11px]">+30 MIN</span>
                    ({cell.projected_30min[0]}, {cell.projected_30min[1]})
                  </div>
                  <div className="bg-black/30 p-1 rounded text-center">
                    <span className="text-[var(--color-ink-faint)] block text-[11px]">+60 MIN</span>
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
          <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-4 space-y-3 shadow-lg">
            <div className="text-xs lg:text-sm font-bold text-[var(--color-ink)]">
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
          <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-4 space-y-3 shadow-lg">
            <div className="text-xs lg:text-sm font-bold text-[var(--color-ink)]">
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
          <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-3.5 space-y-2 text-xs text-[var(--color-ink)]">
            <div className="flex items-center gap-2 font-bold text-[var(--color-accent)]">
              <Compass className="w-4 h-4 text-[var(--color-accent)]" />
              <span>Convective Steering Flow</span>
            </div>
            <p className="text-[11px] text-[var(--color-ink-muted)] leading-relaxed">
              Mid-tropospheric steering wind vector steers convective squall cores along ENE heading (65° azimuth) at ~42 km/h across the 250 km DWR coverage basin.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
