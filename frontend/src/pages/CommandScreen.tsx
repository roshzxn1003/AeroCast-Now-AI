import React, { useEffect } from 'react';
import { LightningGlobe } from '../components/LightningGlobe';
import { ModelReportPanel } from '../components/ModelReportPanel';
import { LightningJumpBanner } from '../components/LightningJumpBanner';
import {
  LiveDomainPanel,
  NetworkStatusPanel,
  NodeDetailPanel,
} from '../components/LiveDomainPanel';
import { useLiveStore } from '../store/liveStore';
import { useNowcastStore } from '../store/nowcastStore';
import { FLASH, SEVERITY_COLOR, SEVERITY_LEVELS } from '../design/tokens';
import { ProvenanceBadge } from '../components/ui';
import {
  assessThunderstormThreat,
  MAJOR_INDIAN_CITIES,
} from '../utils/weatherInterpreter';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Zap,
  MapPin,
  Clock,
  Info,
  CheckCircle2,
} from 'lucide-react';

export const CommandScreen: React.FC = () => {
  const startPolling = useLiveStore((s) => s.startPolling);
  const lightning = useLiveStore((s) => s.lightning);
  const summary = useLiveStore((s) => s.summary);

  const {
    uiMode,
    nowcastData,
    hasJump,
    selectedCity,
    setSelectedCity,
    setSelectedStation,
  } = useNowcastStore();

  useEffect(() => startPolling(), [startPolling]);

  // Evaluate plain-English threat
  const maxDbz = nowcastData?.observation?.max_dbz || 0;
  const activeCellsCount = nowcastData?.observation?.storm_cells?.length || 0;
  const strikeCount30m = summary?.strike_count_30min || 0;

  const threat = assessThunderstormThreat(
    hasJump,
    activeCellsCount,
    maxDbz,
    strikeCount30m
  );

  const currentCity =
    MAJOR_INDIAN_CITIES.find((c) => c.id === selectedCity) || MAJOR_INDIAN_CITIES[0];

  return (
    <div className="flex flex-col lg:flex-row gap-3 p-3 lg:h-[calc(100dvh-3.5rem)] min-h-0">
      {/* 3D Globe Viewport */}
      <div className="relative flex-1 min-w-0 rounded-[10px] border border-[var(--color-line)] overflow-hidden h-[56vh] lg:h-auto bg-[var(--color-surface-void)] shadow-inner">
        <LightningGlobe className="absolute inset-0" />

        {/* Headline flash counter */}
        {summary && (
          <div className="absolute top-4 left-4 text-left pointer-events-none z-10">
            <div
              className="font-mono tabular font-bold leading-none drop-shadow-md text-cyan-400"
              style={{ fontSize: 'var(--text-display)' }}
            >
              {summary.strike_count_30min.toLocaleString()}
            </div>
            <div className="text-[11px] font-semibold text-slate-300 tracking-wider uppercase mt-1">
              ⚡ Strikes (Last 30 Min)
            </div>
            {lightning && (
              <div className="mt-1 flex justify-start">
                <ProvenanceBadge provenance={lightning.status} />
              </div>
            )}
          </div>
        )}

        <GlobeLegend uiMode={uiMode} />
      </div>

      {/* Right Rail: Citizen Mode vs Pro Forecaster Mode */}
      <aside className="w-full lg:w-[400px] xl:w-[440px] shrink-0 flex flex-col gap-3 min-h-0 pb-20 lg:pb-0 lg:overflow-y-auto">
        {uiMode === 'citizen' ? (
          /* ================================================================
             PUBLIC / CITIZEN MODE RAIL
             ================================================================ */
          <div className="space-y-3">
            {/* 1. Big Friendly Threat Alert Hero */}
            <div
              className="p-4 rounded-xl border shadow-lg transition-all"
              style={{
                backgroundColor: threat.bgRgba,
                borderColor: threat.colorHex,
              }}
            >
              <div className="flex items-center justify-between">
                <span
                  className="text-xs font-bold px-2.5 py-0.5 rounded-full text-white shadow-sm"
                  style={{ backgroundColor: threat.colorHex }}
                >
                  {threat.badgeText}
                </span>
                <span className="text-xs text-slate-300 font-mono flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-cyan-400" />
                  Live 0–2h AI Nowcast
                </span>
              </div>

              <h3 className="text-base sm:text-lg font-bold text-white mt-2.5 leading-snug">
                {threat.headline}
              </h3>
              <p className="text-xs text-slate-200 mt-1 leading-relaxed">
                {threat.subhead}
              </p>
            </div>

            {/* 2. City Weather & Radar Quick-Lookup */}
            <div className="p-3.5 rounded-xl border border-slate-700/70 bg-slate-900/90 shadow-md">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-bold text-cyan-400 uppercase tracking-wider">
                  <MapPin className="w-3.5 h-3.5" />
                  Local City Radar
                </div>
                <select
                  value={selectedCity}
                  onChange={(e) => {
                    const id = e.target.value;
                    setSelectedCity(id);
                    const c = MAJOR_INDIAN_CITIES.find((item) => item.id === id);
                    if (c) setSelectedStation(c.stationName);
                  }}
                  className="bg-slate-800 text-cyan-300 text-xs rounded-lg px-2 py-1 border border-slate-600 focus:outline-none cursor-pointer"
                >
                  {MAJOR_INDIAN_CITIES.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-3 flex items-center justify-between">
                <div>
                  <div className="text-lg font-bold text-white">{currentCity.name}</div>
                  <div className="text-xs text-slate-400">{currentCity.state}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-semibold text-emerald-400 flex items-center gap-1 justify-end">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Radar Online
                  </div>
                  <div className="text-[11px] font-mono text-slate-400">
                    Range: 250 km
                  </div>
                </div>
              </div>

              <div className="mt-3 pt-2.5 border-t border-slate-800 grid grid-cols-2 gap-2 text-center text-xs">
                <div className="p-2 rounded-lg bg-slate-800/60">
                  <div className="text-slate-400 text-[10px] uppercase">Rain Intensity</div>
                  <div className="font-bold text-white mt-0.5">
                    {maxDbz >= 40 ? '🌧️ Heavy Downpour' : maxDbz >= 25 ? '🌦️ Moderate Rain' : '⛅ Passing Showers'}
                  </div>
                </div>
                <div className="p-2 rounded-lg bg-slate-800/60">
                  <div className="text-slate-400 text-[10px] uppercase">Lightning Danger</div>
                  <div className="font-bold text-amber-400 mt-0.5">
                    {hasJump ? '⚡ High Alert' : '🟢 Moderate / Normal'}
                  </div>
                </div>
              </div>
            </div>

            {/* 3. Actionable Safety Checklist for Citizens */}
            <div className="p-3.5 rounded-xl border border-slate-700/70 bg-slate-900/90 shadow-md">
              <div className="flex items-center gap-2 text-xs font-bold text-amber-400 uppercase tracking-wider mb-2.5">
                <ShieldAlert className="w-4 h-4" />
                What Should You Do Now?
              </div>
              <ul className="space-y-2">
                {threat.safetyActions.map((action, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-xs text-slate-300 leading-relaxed"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 shrink-0" />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* 4. Plain English Explainer Box */}
            <div className="p-3 rounded-xl border border-cyan-500/20 bg-cyan-950/20 text-xs text-slate-300 leading-relaxed">
              <div className="flex items-center gap-1.5 font-bold text-cyan-300 mb-1">
                <Info className="w-3.5 h-3.5" />
                How AeroCast AI Works
              </div>
              AeroCast fuses 11 IMD Doppler radars, ISRO INSAT-3D satellites, and ground lightning sensors. The deep learning model predicts thunderstorm movement 15 to 120 minutes in advance.
            </div>
          </div>
        ) : (
          /* ================================================================
             PRO / FORECASTER MODE RAIL (Original Scientific Dashboard)
             ================================================================ */
          <>
            <LiveDomainPanel />
            <LightningJumpBanner />
            <ModelReportPanel />
            <NodeDetailPanel />
            <NetworkStatusPanel />
          </>
        )}
      </aside>
    </div>
  );
};

const GlobeLegend: React.FC<{ uiMode: 'citizen' | 'pro' }> = ({ uiMode }) => (
  <div
    className="absolute bottom-4 left-4 panel px-3 py-2.5 space-y-2 pointer-events-none z-10 backdrop-blur-md hidden sm:block"
    style={{ background: 'rgba(11, 15, 20, 0.9)', border: '1px solid rgba(56, 189, 248, 0.25)' }}
  >
    {uiMode === 'citizen' ? (
      <>
        <div className="text-[11px] font-bold text-cyan-400 uppercase tracking-wide">
          Map Legend
        </div>
        <div className="flex items-center gap-3 text-[10px] text-slate-300">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
            <span className="w-2 h-2 rounded-full bg-cyan-400" />
            Active Strikes
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            Storm Energy Column
          </span>
        </div>
        <p className="text-[10px] text-slate-400 max-w-[15rem] leading-snug">
          Drag to rotate. Scroll to zoom directly into Indian states & cities.
        </p>
      </>
    ) : (
      <>
        <div>
          <div className="eyebrow mb-1">Convective Instability</div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-full overflow-hidden h-1.5 w-24">
              {SEVERITY_LEVELS.map((level) => (
                <span
                  key={level}
                  className="flex-1"
                  style={{ background: SEVERITY_COLOR[level] }}
                  title={level}
                />
              ))}
            </div>
            <span className="text-[10px] font-mono text-slate-400">Stable → Extreme</span>
          </div>
        </div>

        <div>
          <div className="eyebrow mb-1">Lightning Types</div>
          <div className="flex items-center gap-3 text-[10px] font-mono text-slate-300">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: FLASH.cg }} />
              CG (Ground)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: FLASH.ic }} />
              IC (Cloud)
            </span>
          </div>
        </div>
      </>
    )}
  </div>
);
