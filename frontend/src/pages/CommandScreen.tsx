import React, { useEffect, useState } from 'react';
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
  Radio,
  Activity,
  Layers,
  Globe2,
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
    setActiveTab,
  } = useNowcastStore();

  // Responsive sub-tab view for tablet/mobile in Pro Mode
  const [mobileProView, setMobileProView] = useState<'globe' | 'soundings' | 'nowcast'>('globe');

  useEffect(() => startPolling(), [startPolling]);

  // Evaluate plain-English threat
  const maxDbz = nowcastData?.observation?.max_dbz || 0;
  const activeCells = nowcastData?.observation?.storm_cells || [];
  const strikeCount30m = summary?.strike_count_30min || 0;

  const threat = assessThunderstormThreat(
    hasJump,
    activeCells.length,
    maxDbz,
    strikeCount30m
  );

  const currentCity =
    MAJOR_INDIAN_CITIES.find((c) => c.id === selectedCity) || MAJOR_INDIAN_CITIES[0];

  return (
    <div className="flex flex-col gap-3 p-3 xl:h-[calc(100dvh-3.5rem)] min-h-0">
      {/* Mobile/Tablet Sub-Tab Navigation Bar for Pro Mode (Hidden on Desktop >= xl) */}
      {uiMode === 'pro' && (
        <div className="flex xl:hidden items-center justify-between bg-slate-900/90 border border-slate-700/80 rounded-xl p-1 text-xs shrink-0">
          <button
            onClick={() => setMobileProView('soundings')}
            className={`flex-1 py-1.5 px-2 rounded-lg font-medium flex items-center justify-center gap-1.5 transition-all ${
              mobileProView === 'soundings'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Soundings</span>
          </button>
          <button
            onClick={() => setMobileProView('globe')}
            className={`flex-1 py-1.5 px-2 rounded-lg font-medium flex items-center justify-center gap-1.5 transition-all ${
              mobileProView === 'globe'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Globe2 className="w-3.5 h-3.5" />
            <span>3D Earth</span>
          </button>
          <button
            onClick={() => setMobileProView('nowcast')}
            className={`flex-1 py-1.5 px-2 rounded-lg font-medium flex items-center justify-center gap-1.5 transition-all ${
              mobileProView === 'nowcast'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Nowcast</span>
          </button>
        </div>
      )}

      {/* Main Multi-Column Viewport */}
      <div className="flex flex-col xl:flex-row gap-3 flex-1 min-h-0">
        {/* ========================================================================
            LEFT COLUMN (PRO MODE ONLY): OBSERVATION & SOUNDINGS CONSOLE
            ======================================================================== */}
        {uiMode === 'pro' && (
          <aside
            className={`w-full xl:w-80 2xl:w-[350px] shrink-0 flex flex-col gap-3 min-h-0 overflow-y-auto pr-0.5 ${
              mobileProView === 'soundings' ? 'flex' : 'hidden xl:flex'
            }`}
          >
            <div className="flex items-center justify-between px-1 text-[11px] font-bold uppercase tracking-wider text-cyan-400">
              <span className="flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5" />
                Live Ingest & Soundings
              </span>
              <span className="text-[10px] font-mono text-slate-400">LEFT RAIL</span>
            </div>
            <LiveDomainPanel />
            <NodeDetailPanel />
            <NetworkStatusPanel />
          </aside>
        )}

        {/* ========================================================================
            CENTER COLUMN: 3D EARTH GEOSPATIAL CANVAS & HUD
            ======================================================================== */}
        <div
          className={`relative flex-1 min-w-0 rounded-[12px] border border-[var(--color-line)] overflow-hidden h-[58vh] xl:h-auto bg-[var(--color-surface-void)] shadow-inner ${
            uiMode === 'pro' && mobileProView !== 'globe' ? 'hidden xl:block' : 'block'
          }`}
        >
          <LightningGlobe className="absolute inset-0" />

          {/* Clean Glassmorphic Top-Left Strike Counter HUD (Non-colliding) */}
          {summary && (
            <div className="absolute top-4 left-4 z-20 panel p-3 bg-slate-950/85 backdrop-blur-md border border-cyan-500/35 rounded-xl shadow-2xl pointer-events-none min-w-[185px]">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
                  <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                    30m Strikes
                  </span>
                </div>
                {lightning && <ProvenanceBadge provenance={lightning.status} />}
              </div>

              <div className="flex items-baseline gap-1.5 mt-1.5">
                <div className="font-mono text-2xl font-bold leading-none text-cyan-400 tabular">
                  {summary.strike_count_30min.toLocaleString()}
                </div>
                <span className="text-[10px] text-slate-400 font-mono">flashes</span>
              </div>

              <div className="mt-1.5 flex items-center justify-between text-[10px] font-mono text-slate-400 border-t border-slate-800/80 pt-1">
                <span>Rate: {summary.flash_rate_per_min}/min</span>
                <span>CAPE: {summary.max_cape_j_kg.toFixed(0)}</span>
              </div>
            </div>
          )}

          {/* Collapsible Map Legend */}
          <GlobeLegend uiMode={uiMode} />
        </div>

        {/* ========================================================================
            RIGHT COLUMN: CITIZEN GUIDE OR PRO AI NOWCASTING & STORM KINEMATICS
            ======================================================================== */}
        <aside
          className={`w-full xl:w-[380px] 2xl:w-[420px] shrink-0 flex flex-col gap-3 min-h-0 pb-20 xl:pb-0 overflow-y-auto ${
            uiMode === 'pro' && mobileProView !== 'nowcast' ? 'hidden xl:flex' : 'flex'
          }`}
        >
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
               PRO / FORECASTER MODE RAIL: AI NOWCAST & STORM KINEMATICS
               ================================================================ */
            <>
              <div className="flex items-center justify-between px-1 text-[11px] font-bold uppercase tracking-wider text-amber-400">
                <span className="flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5" />
                  AI Nowcast & Prediction
                </span>
                <span className="text-[10px] font-mono text-slate-400">RIGHT RAIL</span>
              </div>

              {/* Precursor Surge Alert */}
              <LightningJumpBanner />

              {/* Neural Model Verification on Demand */}
              <ModelReportPanel />

              {/* SCIT Storm Cell Kinematics Summary Card */}
              <div className="rounded-[10px] border border-[var(--color-line)] bg-[var(--color-surface-base)] p-3.5 space-y-2.5 shadow">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-200 uppercase tracking-wide">
                    <Activity className="w-4 h-4 text-orange-400" />
                    SCIT Storm Cells ({activeCells.length} Active)
                  </div>
                  <button
                    onClick={() => setActiveTab('storms')}
                    className="text-[11px] text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1 transition-colors"
                  >
                    <span>Full Kinematics</span>
                    <span>→</span>
                  </button>
                </div>

                {activeCells.length === 0 ? (
                  <p className="text-xs text-slate-500 italic py-2">
                    No active convective cells meeting ≥ 40 dBZ / 24 km² tracking threshold.
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {activeCells.slice(0, 3).map((cell) => (
                      <div
                        key={cell.cell_id}
                        className="bg-white/5 hover:bg-white/10 border border-white/5 rounded-lg p-2 flex items-center justify-between text-xs transition-colors"
                      >
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ backgroundColor: cell.color }}
                            />
                            <span className="font-bold text-slate-200">{cell.cell_id}</span>
                            <span className="text-[10px] text-slate-400 font-mono">{cell.area_km2} km²</span>
                          </div>
                          <div className="text-[10px] text-slate-400 mt-0.5">{cell.severity}</div>
                        </div>

                        <div className="text-right">
                          <div className="font-bold text-orange-400 font-mono">{cell.max_dbz} dBZ</div>
                          <div className="text-[10px] text-red-400 font-semibold">Hail Risk {cell.hail_risk_pct}%</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
};

const GlobeLegend: React.FC<{ uiMode: 'citizen' | 'pro' }> = ({ uiMode }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div
      className="absolute bottom-4 left-4 z-20 pointer-events-auto backdrop-blur-md rounded-xl transition-all shadow-xl hidden sm:block overflow-hidden"
      style={{
        background: 'rgba(11, 15, 20, 0.94)',
        border: '1px solid rgba(56, 189, 248, 0.3)',
      }}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between gap-3 px-3 py-1.5 w-full text-left hover:bg-white/5 transition-colors cursor-pointer"
        title="Toggle map legend display"
      >
        <div className="flex items-center gap-1.5 text-[10px] font-bold text-cyan-400 uppercase tracking-wide">
          <Layers className="w-3 h-3" />
          <span>Map Legend</span>
        </div>
        <span className="text-[10px] font-mono text-slate-400">
          {isOpen ? '▾ Hide' : '▸ Show'}
        </span>
      </button>

      {isOpen && (
        <div className="p-3 pt-2 space-y-2 border-t border-slate-800/80">
          {uiMode === 'citizen' ? (
            <>
              <div className="space-y-1.5 text-[10px] text-slate-300">
                <span className="flex items-center gap-1.5">
                  <span className="relative flex items-center justify-center w-3">
                    <span className="absolute w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
                    <span className="relative w-2 h-2 rounded-full bg-cyan-400" />
                  </span>
                  City Beacon — tap to dive in
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="flex rounded-full overflow-hidden h-2 w-10">
                    {SEVERITY_LEVELS.map((level) => (
                      <span
                        key={level}
                        className="flex-1"
                        style={{ background: SEVERITY_COLOR[level] }}
                      />
                    ))}
                  </span>
                  Storm energy — calm to severe
                </span>
                <span className="flex items-center gap-3">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: FLASH.cg }} />
                    Ground strike
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: FLASH.ic }} />
                    In-cloud
                  </span>
                </span>
              </div>
              <p className="text-[10px] text-slate-400 max-w-[15rem] leading-snug">
                Drag to rotate. Scroll to zoom directly into Indian states & radar sites.
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
                <div className="eyebrow mb-1">Lightning Geolocation</div>
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
      )}
    </div>
  );
};
