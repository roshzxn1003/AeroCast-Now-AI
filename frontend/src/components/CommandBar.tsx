import React from 'react';
import { RefreshCw, Zap, User, Gauge, MapPin } from 'lucide-react';
import { useLiveStore } from '../store/liveStore';
import { useNowcastStore } from '../store/nowcastStore';
import { Button, ProvenanceBadge } from './ui';
import { ActiveTab } from '../types/nowcast';
import { MAJOR_INDIAN_CITIES } from '../utils/weatherInterpreter';
import { OutputDataSourceSwitcher } from './OutputDataSourceSwitcher';

const PRO_TABS: { id: ActiveTab; label: string }[] = [
  { id: 'nowcast', label: 'Command' },
  { id: 'alerts', label: 'Alerts' },
  { id: 'storms', label: 'Cells' },
  { id: 'risk', label: 'Sectors' },
  { id: 'more', label: 'Diagnostics' },
];

const CITIZEN_TABS: { id: ActiveTab; label: string }[] = [
  { id: 'nowcast', label: 'Live Earth' },
  { id: 'alerts', label: 'Warnings' },
  { id: 'storms', label: 'Radar & Rain' },
  { id: 'risk', label: 'Safety Tips' },
  { id: 'more', label: 'About AI' },
];

export const CommandBar: React.FC = () => {
  const {
    activeTab,
    setActiveTab,
    uiMode,
    setUiMode,
    selectedCity,
    setSelectedCity,
    setSelectedStation,
    dataPipelineStatus,
    loadDataPipelineStatus,
  } = useNowcastStore();

  React.useEffect(() => {
    void loadDataPipelineStatus();
    const timer = setInterval(() => {
      void loadDataPipelineStatus();
    }, 30000);
    return () => clearInterval(timer);
  }, [loadDataPipelineStatus]);

  const summary = useLiveStore((s) => s.summary);
  const isLoading = useLiveStore((s) => s.isLoading);
  const refreshAll = useLiveStore((s) => s.refreshAll);

  const tabs = uiMode === 'citizen' ? CITIZEN_TABS : PRO_TABS;

  const mode = dataPipelineStatus?.mode ?? 'hybrid';
  let badgeColor = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';
  let dotColor = 'bg-cyan-400';
  let modeLabel = 'HYBRID FEED';

  if (mode === 'real') {
    badgeColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    dotColor = 'bg-emerald-400';
    modeLabel = 'LIVE DATA';
  } else if (mode === 'simulation') {
    badgeColor = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    dotColor = 'bg-amber-400';
    modeLabel = 'SIMULATION';
  }

  const tooltipText = dataPipelineStatus
    ? `Data Pipeline: ${dataPipelineStatus.mode.toUpperCase()} (Quality: ${Math.round(dataPipelineStatus.quality_score * 100)}%)\n` +
      `• Weather: ${dataPipelineStatus.sources.weather.status} (${dataPipelineStatus.sources.weather.provider})\n` +
      `• Radar: ${dataPipelineStatus.sources.radar.status} (${dataPipelineStatus.sources.radar.provider})\n` +
      `• Satellite: ${dataPipelineStatus.sources.satellite.status} (${dataPipelineStatus.sources.satellite.provider})\n` +
      `• Lightning: ${dataPipelineStatus.sources.lightning.status} (${dataPipelineStatus.sources.lightning.provider})`
    : 'Data Pipeline: Connecting...';

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-line)] bg-[rgba(6,8,11,0.92)] backdrop-blur-md">
      <div className="flex items-center gap-3 px-3 sm:px-4 h-14">
        {/* Identity */}
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="w-7 h-7 rounded-[6px] border border-[var(--color-accent-line)] bg-[var(--color-accent-dim)] grid place-items-center">
            <Zap className="w-4 h-4 text-[var(--color-accent)]" />
          </div>
          <div className="leading-tight">
            <div className="text-[14px] font-semibold tracking-tight text-white">AeroCast-Now</div>
            <div className="text-[10px] text-cyan-400 font-mono tracking-wide">
              {uiMode === 'citizen' ? 'INDIA WEATHER & LIGHTNING' : 'INDIAN CONVECTIVE DOMAIN'}
            </div>
          </div>
        </div>

        {/* Dual Mode Switcher: Citizen (Friendly) vs Pro (Meteorologist) */}
        <div className="flex items-center rounded-lg p-0.5 bg-slate-900 border border-slate-700/80 text-xs shrink-0">
          <button
            onClick={() => setUiMode('citizen')}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-md font-medium transition-all ${
              uiMode === 'citizen'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Switch to Public / Citizen Mode with simple language & safety tips"
          >
            <User className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Citizen</span>
          </button>
          <button
            onClick={() => setUiMode('pro')}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-md font-medium transition-all ${
              uiMode === 'pro'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Switch to Pro Forecaster Mode with raw radar dBZ & sounding telemetry"
          >
            <Gauge className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Pro</span>
          </button>
        </div>

        {/* Global Output Data Source Switcher (All vs Live vs Model) */}
        <div className="hidden sm:flex items-center pl-2 border-l border-[var(--color-line)] shrink-0">
          <OutputDataSourceSwitcher size="xs" compact={true} />
        </div>

        {/* Citizen Quick City Selector */}
        {uiMode === 'citizen' ? (
          <div className="hidden md:flex items-center gap-1.5 pl-3 border-l border-[var(--color-line)] shrink-0">
            <MapPin className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <span className="text-xs text-slate-400 font-medium shrink-0">City:</span>
            <select
              value={selectedCity}
              onChange={(e) => {
                const cityId = e.target.value;
                setSelectedCity(cityId);
                const city = MAJOR_INDIAN_CITIES.find((c) => c.id === cityId);
                if (city) setSelectedStation(city.stationName);
              }}
              className="bg-slate-900/90 border border-cyan-500/40 text-cyan-300 text-xs rounded-lg px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-cyan-400 cursor-pointer font-medium"
            >
              {MAJOR_INDIAN_CITIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.state})
                </option>
              ))}
            </select>
          </div>
        ) : (
          summary && (
            <div className="hidden xl:flex items-center gap-2 pl-3 border-l border-[var(--color-line)] shrink-0">
              <ProvenanceBadge provenance={summary.lightning_status} />
              <span className="text-[11px] font-mono text-[var(--color-ink-faint)]">
                {new Date(summary.retrieved_at).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          )
        )}

        {/* Data Pipeline Mode & Provider Quality Badge */}
        <div
          className={`hidden 2xl:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold border cursor-help transition-colors shrink-0 ${badgeColor}`}
          title={tooltipText}
        >
          <span className={`w-2 h-2 rounded-full ${mode === 'simulation' ? 'bg-amber-400' : 'animate-pulse ' + dotColor}`} />
          <span>{modeLabel}</span>
        </div>

        <div className="flex-1 min-w-[0.5rem]" />

        {/* Navigation Tabs */}
        <nav className="hidden lg:flex items-center gap-1 shrink-0" aria-label="Primary">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              aria-current={activeTab === tab.id ? 'page' : undefined}
              className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-all ${
                activeTab === tab.id
                  ? 'text-cyan-300 bg-cyan-950/50 border border-cyan-500/40 font-bold shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60 border border-transparent'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <Button
          icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />}
          onClick={() => void refreshAll()}
          disabled={isLoading}
          aria-label="Refresh live telemetry"
        >
          <span className="hidden sm:inline">Refresh</span>
        </Button>
      </div>
    </header>
  );
};

