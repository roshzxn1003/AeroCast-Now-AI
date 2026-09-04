import React, { useState, useEffect } from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { fetchLightningJumpTimeseries } from '../services/api';
import { FlashTimeSeriesPoint } from '../types/nowcast';
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

  useEffect(() => {
    fetchLightningJumpTimeseries(hasJump).then((res) => {
      setTimeseries(res.timeseries);
    });
  }, [hasJump]);

  if (!nowcastData) return null;

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
    <div className="space-y-3 p-3 max-w-lg mx-auto pb-24 animate-in fade-in duration-300">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-extrabold text-slate-100 flex items-center gap-1.5">
            <Zap className="w-5 h-5 text-amber-400" />
            Lightning Jump Precursor Radar
          </h2>
          <p className="text-[11px] text-slate-400">
            Schultz / Gatlin & Goodman 2σ Convective Surge Detection
          </p>
        </div>

        {/* Demo Jump Toggle */}
        <button
          onClick={() => setHasJump(!hasJump)}
          className={`px-2 py-1 rounded-lg text-xs font-bold transition-all border ${
            hasJump
              ? 'bg-red-500/20 border-red-500/40 text-red-300'
              : 'bg-white/5 border-white/10 text-slate-400'
          }`}
        >
          {hasJump ? '🚨 Surge Active' : '🟢 Normal'}
        </button>
      </div>

      {/* Main Status Hero Card */}
      <div
        className={`p-3.5 rounded-2xl border ${
          jump.jump_detected
            ? 'bg-gradient-to-br from-red-500/20 via-orange-500/15 to-transparent border-red-500/40 alert-pulse'
            : 'bg-gradient-to-br from-emerald-500/20 to-transparent border-emerald-500/30'
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <span
              className={`text-[10px] font-black tracking-wider uppercase px-2 py-0.5 rounded-md ${
                jump.jump_detected
                  ? 'bg-red-500 text-white'
                  : 'bg-emerald-500 text-slate-900'
              }`}
            >
              {jump.threat_level}
            </span>
            <h3 className="text-sm font-black text-slate-100 mt-1.5">
              {jump.status}
            </h3>
          </div>

          <div className="text-right shrink-0">
            <div className="text-[10px] text-slate-400 uppercase font-bold">
              Precursor Lead-Time
            </div>
            <div className="text-lg font-black text-amber-400 font-mono">
              ~{jump.estimated_lead_time_min} MINS
            </div>
          </div>
        </div>

        {/* 4 Telemetry Metrics */}
        <div className="grid grid-cols-4 gap-1.5 mt-3 pt-3 border-t border-white/10 text-center">
          <div className="bg-black/30 rounded-lg p-1.5">
            <div className="text-[9px] text-slate-400">Sigma Metric</div>
            <div
              className={`text-xs font-extrabold ${
                jump.sigma_metric >= 2.0 ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              {jump.sigma_metric} σ
            </div>
          </div>

          <div className="bg-black/30 rounded-lg p-1.5">
            <div className="text-[9px] text-slate-400">Flash Rate</div>
            <div className="text-xs font-extrabold text-amber-400">
              {jump.current_rate_fpm} fpm
            </div>
          </div>

          <div className="bg-black/30 rounded-lg p-1.5">
            <div className="text-[9px] text-slate-400">Rate Surge ΔFR</div>
            <div className="text-xs font-extrabold text-orange-400">
              +{jump.dfr_dt}
            </div>
          </div>

          <div className="bg-black/30 rounded-lg p-1.5">
            <div className="text-[9px] text-slate-400">Warning Window</div>
            <div className="text-xs font-extrabold text-sky-400">
              15–45 min
            </div>
          </div>
        </div>
      </div>

      {/* Lightning Flash Rate Time-Series Chart */}
      <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-slate-200">
            High-Cadence Flash Rate History (flashes/min)
          </div>
          <div className="flex items-center gap-2 text-[10px] font-medium">
            <span className="flex items-center gap-1 text-yellow-400">
              <span className="w-2 h-2 rounded-full bg-yellow-400" /> Total
            </span>
            <span className="flex items-center gap-1 text-sky-400">
              <span className="w-2 h-2 rounded-full bg-sky-400" /> IC (82%)
            </span>
            <span className="flex items-center gap-1 text-red-400">
              <span className="w-2 h-2 rounded-full bg-red-400" /> CG (18%)
            </span>
          </div>
        </div>

        <div className="h-44 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeseries} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
              <XAxis
                dataKey="minutes_ago"
                stroke="#94a3b8"
                fontSize={10}
                tickFormatter={(val) => `${val}m`}
              />
              <YAxis stroke="#94a3b8" fontSize={10} />
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
                    fontSize: 9,
                    position: 'insideTopLeft',
                  }}
                />
              )}
              <Line
                type="monotone"
                dataKey="total_flash_rate"
                stroke="#facc15"
                strokeWidth={2.5}
                dot={{ r: 2 }}
                name="Total Flashes"
              />
              <Line
                type="monotone"
                dataKey="ic_flash_rate"
                stroke="#38bdf8"
                strokeWidth={1.5}
                strokeDasharray="3 3"
                dot={false}
                name="Intra-Cloud"
              />
              <Line
                type="monotone"
                dataKey="cg_flash_rate"
                stroke="#f87171"
                strokeWidth={1.5}
                dot={false}
                name="Cloud-to-Ground"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Physics Principle Card */}
      <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 space-y-1.5 text-xs text-slate-300">
        <div className="flex items-center gap-1.5 font-bold text-amber-300 text-xs">
          <Info className="w-4 h-4" />
          <span>Meteorological Principle of Lightning Jump</span>
        </div>
        <p className="text-[11px] text-slate-400 leading-relaxed">
          Intense updrafts elevate supercooled liquid water into the mixed-phase charging zone (-10°C to -25°C). Violent collisions between graupel and ice crystals trigger rapid electrical charging, producing a non-linear surge in intra-cloud (IC) flashes ~15 to 45 minutes before heavy hail cores collapse and cloud-to-ground (CG) strikes hit the surface.
        </p>
      </div>

      {/* CAP v1.2 Official Alert Bulletin Card */}
      <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <h3 className="font-bold text-xs text-slate-200">
              CAP v1.2 Disaster Bulletin
            </h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleCopyCap}
              className="p-1 rounded bg-white/5 hover:bg-white/10 text-slate-300 text-[10px] flex items-center gap-1 px-1.5"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            <button
              onClick={handleDownloadCap}
              className="p-1 rounded bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 text-[10px] flex items-center gap-1 px-1.5 font-bold"
            >
              <Download className="w-3 h-3" />
              JSON
            </button>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 rounded-lg p-2.5 text-[11px] space-y-1 text-slate-300 font-sans">
          <div className="font-bold text-amber-300">{cap.info.headline}</div>
          <div className="text-[10px] text-slate-400 font-mono">
            Identifier: {cap.identifier} • Sent: {cap.sent}
          </div>
          <div className="text-slate-300 mt-1">{cap.info.description}</div>
          <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded text-red-300 text-[10px] whitespace-pre-line font-medium">
            {cap.info.instruction}
          </div>
        </div>

        <button
          onClick={() => setShowJson(!showJson)}
          className="text-[11px] text-slate-400 hover:text-slate-200 underline"
        >
          {showJson ? 'Hide raw CAP JSON' : 'Inspect raw CAP v1.2 JSON'}
        </button>

        {showJson && (
          <pre className="p-2 bg-black/60 rounded-lg text-[10px] font-mono text-slate-300 overflow-x-auto max-h-48 scrollbar-thin">
            {JSON.stringify(cap, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
};
