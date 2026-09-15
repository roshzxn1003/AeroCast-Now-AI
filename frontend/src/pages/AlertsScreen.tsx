import React, { useState, useEffect } from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { fetchLightningJumpTimeseries, fetchDistrictsSummary } from '../services/api';
import { FlashTimeSeriesPoint, DistrictSummaryResponse } from '../types/nowcast';
import {
  Zap,
  Clock,
  Activity,
  AlertTriangle,
  Download,
  Copy,
  Check,
  Info,
  ShieldCheck,
  MapPin,
  Radar,
  Radio,
  RefreshCw,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

export const AlertsScreen: React.FC = () => {
  const { nowcastData, hasJump, setHasJump } = useNowcastStore();
  const [timeseries, setTimeseries] = useState<FlashTimeSeriesPoint[]>([]);
  const [copied, setCopied] = useState(false);
  const [showJson, setShowJson] = useState(false);
  const [districtSummary, setDistrictSummary] = useState<DistrictSummaryResponse | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  useEffect(() => {
    fetchLightningJumpTimeseries(hasJump).then((res) => {
      setTimeseries(res.timeseries);
    });
  }, [hasJump]);

  useEffect(() => {
    setLoadingSummary(true);
    fetchDistrictsSummary(12).then((res) => {
      if (res) setDistrictSummary(res);
      setLoadingSummary(false);
    });
  }, []);

  if (!nowcastData) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3 text-slate-400 font-mono text-xs">
        <RefreshCw className="w-7 h-7 text-cyan-400 animate-spin" />
        <span>Loading Lightning Jump & Warning Telemetry…</span>
      </div>
    );
  }

  const jump = nowcastData.lightning_jump;
  const cap = nowcastData.cap_bulletin;

  const handleCopyCap = () => {
    navigator.clipboard.writeText(JSON.stringify(cap, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadCap = () => {
    const blob = new Blob([JSON.stringify(cap, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `CAP_Alert_${cap.identifier}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full max-w-7xl mx-auto px-3 py-3 lg:px-6 lg:py-4 space-y-4 pb-24 lg:pb-12 animate-in fade-in duration-300">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base lg:text-lg font-semibold text-[var(--color-ink)] flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-400" />
            Lightning Jump Precursor Radar
          </h2>
          <p className="text-xs text-[var(--color-ink-muted)]">
            Schultz / Gatlin & Goodman 2σ Convective Surge Early Warning System
          </p>
        </div>

        {/* Demo Jump Toggle */}
        <button
          onClick={() => setHasJump(!hasJump)}
          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
            hasJump
              ? 'bg-red-500/20 border-red-500/40 text-red-300 shadow-sm shadow-red-950'
              : 'bg-[var(--color-surface-raised)] border-[var(--color-line)] text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]'
          }`}
        >
          {hasJump ? '🚨 Convective Surge Active' : '🟢 Normal State'}
        </button>
      </div>

      {/* Main Responsive Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Status Hero Card, Time-Series Chart, Physics Principle */}
        <div className="lg:col-span-7 space-y-4">
          {/* Main Status Hero Card */}
          <div
            className={`p-4 rounded-[10px] border ${
              jump.jump_detected
                ? 'bg-gradient-to-br from-red-500/20 via-orange-500/15 to-transparent border-red-500/40'
                : 'bg-gradient-to-br from-emerald-500/20 to-transparent border-emerald-500/30'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <span
                  className={`text-[11px] font-semibold tracking-wider uppercase px-2.5 py-0.5 rounded-md ${
                    jump.jump_detected
                      ? 'bg-red-500 text-white'
                      : 'bg-emerald-500 text-[#06080b]'
                  }`}
                >
                  {jump.threat_level}
                </span>
                <h3 className="text-sm lg:text-base font-semibold text-[var(--color-ink)] mt-2">
                  {jump.status}
                </h3>
              </div>

              <div className="text-right shrink-0 bg-black/40 px-3 py-1.5 rounded-[10px] border border-[var(--color-line)]">
                <div className="text-[11px] text-[var(--color-ink-muted)] uppercase font-bold">
                  Precursor Lead-Time
                </div>
                <div className="text-xl font-semibold text-amber-400 font-mono">
                  ~{jump.estimated_lead_time_min} MINS
                </div>
              </div>
            </div>

            {/* 4 Telemetry Metrics */}
            <div className="grid grid-cols-4 gap-2 mt-4 pt-3 border-t border-[var(--color-line)] text-center">
              <div className="bg-black/30 rounded-lg p-2">
                <div className="text-[11px] text-[var(--color-ink-muted)]">Sigma Metric</div>
                <div
                  className={`text-sm font-semibold mt-0.5 ${
                    jump.sigma_metric >= 2.0 ? 'text-red-400' : 'text-emerald-400'
                  }`}
                >
                  {jump.sigma_metric} σ
                </div>
              </div>

              <div className="bg-black/30 rounded-lg p-2">
                <div className="text-[11px] text-[var(--color-ink-muted)]">Flash Rate</div>
                <div className="text-sm font-semibold text-amber-400 mt-0.5">
                  {jump.current_rate_fpm} fpm
                </div>
              </div>

              <div className="bg-black/30 rounded-lg p-2">
                <div className="text-[11px] text-[var(--color-ink-muted)]">Rate Surge ΔFR</div>
                <div className="text-sm font-semibold text-orange-400 mt-0.5">
                  +{jump.dfr_dt}
                </div>
              </div>

              <div className="bg-black/30 rounded-lg p-2">
                <div className="text-[11px] text-[var(--color-ink-muted)]">Warning Window</div>
                <div className="text-sm font-semibold text-[var(--color-accent)] mt-0.5">
                  15–45 min
                </div>
              </div>
            </div>
          </div>

          {/* Lightning Flash Rate Time-Series Chart */}
          <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-4 space-y-3 shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
              <div className="text-xs lg:text-sm font-bold text-[var(--color-ink)]">
                High-Cadence Flash Rate History (flashes/min)
              </div>
              <div className="flex items-center gap-3 text-[11px] font-medium">
                <span className="flex items-center gap-1 text-yellow-400">
                  <span className="w-2 h-2 rounded-full bg-yellow-400" /> Total
                </span>
                <span className="flex items-center gap-1 text-[var(--color-accent)]">
                  <span className="w-2 h-2 rounded-full bg-sky-400" /> IC (82%)
                </span>
                <span className="flex items-center gap-1 text-red-400">
                  <span className="w-2 h-2 rounded-full bg-red-400" /> CG (18%)
                </span>
              </div>
            </div>

            <div className="h-56 lg:h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeseries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                  <XAxis
                    dataKey="minutes_ago"
                    stroke="#94a3b8"
                    fontSize={11}
                    tickFormatter={(val) => `${val}m`}
                  />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0d1117',
                      borderColor: 'rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                      fontSize: '11px',
                    }}
                  />
                  {jump.jump_detected && (
                    <ReferenceLine
                      x={0}
                      stroke="#ef4444"
                      strokeDasharray="4 4"
                      label={{
                        value: `2σ JUMP (${jump.sigma_metric}σ)`,
                        fill: '#ef4444',
                        fontSize: 10,
                        position: 'insideTopLeft',
                      }}
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey="total_flash_rate"
                    stroke="#facc15"
                    strokeWidth={3}
                    dot={{ r: 3 }}
                    name="Total Flashes"
                  />
                  <Line
                    type="monotone"
                    dataKey="ic_flash_rate"
                    stroke="#38bdf8"
                    strokeWidth={2}
                    strokeDasharray="3 3"
                    dot={false}
                    name="Intra-Cloud"
                  />
                  <Line
                    type="monotone"
                    dataKey="cg_flash_rate"
                    stroke="#f87171"
                    strokeWidth={2}
                    dot={false}
                    name="Cloud-to-Ground"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Physics Principle Card */}
          <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-3.5 space-y-2 text-xs text-[var(--color-ink)]">
            <div className="flex items-center gap-2 font-bold text-amber-300 text-xs">
              <Info className="w-4 h-4 text-amber-400" />
              <span>Meteorological Principle of Lightning Jump</span>
            </div>
            <p className="text-[11px] lg:text-xs text-[var(--color-ink-muted)] leading-relaxed">
              Intense updrafts elevate supercooled liquid water into the mixed-phase charging zone (-10°C to -25°C). Violent collisions between graupel and ice crystals trigger rapid electrical charging, producing a non-linear surge in intra-cloud (IC) flashes ~15 to 45 minutes before heavy hail cores collapse and cloud-to-ground (CG) strikes hit the surface.
            </p>
          </div>
        </div>

        {/* Right Column: CAP v1.2 Official Alert Bulletin Card & Inspector */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-4 space-y-3 shadow-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                <h3 className="font-bold text-xs lg:text-sm text-[var(--color-ink)]">
                  CAP v1.2 Disaster Bulletin
                </h3>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={handleCopyCap}
                  className="p-1.5 rounded-lg bg-[var(--color-surface-raised)] hover:bg-[var(--color-surface-overlay)] text-[var(--color-ink)] text-xs flex items-center gap-1.5 px-2.5 transition-colors"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
                <button
                  onClick={handleDownloadCap}
                  className="p-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-white text-xs flex items-center gap-1.5 px-2.5 font-bold shadow transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download JSON</span>
                </button>
              </div>
            </div>

            <div className="bg-black/40 border border-[var(--color-line-faint)] rounded-[10px] p-3.5 text-xs space-y-2 text-[var(--color-ink)] font-sans">
              <div className="font-bold text-amber-300 text-xs lg:text-sm">
                {cap.info.headline}
              </div>
              <div className="text-[11px] text-[var(--color-ink-muted)] font-mono">
                Identifier: {cap.identifier} • Sent: {cap.sent}
              </div>
              <div className="text-[var(--color-ink)] text-xs leading-relaxed">
                {cap.info.description}
              </div>
              <div className="mt-2 p-2.5 bg-red-500/10 border border-red-500/20 rounded-lg text-red-300 text-[11px] whitespace-pre-line font-medium leading-normal">
                {cap.info.instruction}
              </div>
            </div>

            <div className="space-y-1.5 pt-1">
              <button
                onClick={() => setShowJson(!showJson)}
                className="text-xs text-[var(--color-accent)] hover:text-[var(--color-accent)] underline font-medium"
              >
                {showJson ? '▲ Hide raw OASIS CAP JSON' : '▼ Inspect raw OASIS CAP v1.2 JSON'}
              </button>

              {showJson && (
                <pre className="p-3 bg-black/70 border border-[var(--color-line)] rounded-[10px] text-[11px] font-mono text-[var(--color-ink)] overflow-x-auto max-h-72 scrollbar-thin">
                  {JSON.stringify(cap, null, 2)}
                </pre>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* National District Convective Watch Grid */}
      <div className="bg-[var(--color-surface-base)] border border-[var(--color-line)] rounded-[10px] p-4 space-y-3 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[var(--color-line)] pb-3">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-rose-400 animate-pulse" />
            <div>
              <h3 className="font-bold text-xs lg:text-sm text-[var(--color-ink)] flex items-center gap-2">
                National District Convective Hazard Watch
                <span className="text-[10px] font-normal px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/30">
                  {districtSummary
                    ? `${(districtSummary.warning_summary.extreme_warnings || 0) + (districtSummary.warning_summary.severe_warnings || 0)} Active Warnings`
                    : 'Scanning 734 Districts...'}
                </span>
              </h3>
              <p className="text-[11px] text-[var(--color-ink-muted)]">
                AI nowcasting model sweep across all 734 Indian districts via IMD Doppler Radar & INSAT-3D
              </p>
            </div>
          </div>
          <div className="text-[11px] text-[var(--color-ink-muted)] font-mono flex items-center gap-2">
            <span>{districtSummary?.total_districts_indexed ?? 734} Districts Monitored</span>
          </div>
        </div>

        {loadingSummary && (
          <div className="py-8 text-center text-xs text-[var(--color-ink-muted)] animate-pulse">
            Querying deep learning extrapolation across national district grid...
          </div>
        )}

        {districtSummary && districtSummary.districts && districtSummary.districts.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
            {districtSummary.districts.map((d: any) => (
              <div
                key={d.id}
                className="bg-black/30 border border-[var(--color-line-faint)] hover:border-amber-500/40 rounded-lg p-3 space-y-2 transition-all"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-bold text-xs text-[var(--color-ink)] flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                      <span>{d.name}</span>
                    </div>
                    <div className="text-[10px] text-[var(--color-ink-muted)] pl-5">{d.state}</div>
                  </div>
                  <span
                    className={`text-[9px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${
                      d.threat_level === 'EXTREME'
                        ? 'bg-red-500/20 text-red-300 border-red-500/40'
                        : d.threat_level === 'SEVERE'
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                        : 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30'
                    }`}
                  >
                    {d.threat_level}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-1.5 pt-1 text-[10px] font-mono">
                  <div className="bg-black/40 p-1.5 rounded border border-white/5">
                    <div className="text-[9px] text-[var(--color-ink-muted)] uppercase">Peak Reflectivity</div>
                    <div className="font-bold text-amber-300">{d.max_reflectivity_dbz} dBZ</div>
                  </div>
                  <div className="bg-black/40 p-1.5 rounded border border-white/5">
                    <div className="text-[9px] text-[var(--color-ink-muted)] uppercase">CAPE Sounding</div>
                    <div className="font-bold text-cyan-300">{Math.round(d.cape_j_kg)} J/kg</div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-[var(--color-ink-muted)] pt-1 border-t border-white/5 font-mono">
                  <span>Lat: {Number(d.lat).toFixed(2)}°, Lon: {Number(d.lon).toFixed(2)}°</span>
                  <span className="text-amber-400 font-medium">Auto-Nowcast</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
