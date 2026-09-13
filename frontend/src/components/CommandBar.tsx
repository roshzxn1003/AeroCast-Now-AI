import React from 'react';
import { Activity, AlertTriangle, RefreshCw, Zap, User, Gauge, MapPin } from 'lucide-react';
import { useLiveStore } from '../store/liveStore';
import { useNowcastStore } from '../store/nowcastStore';
import { Badge, Button, ProvenanceBadge } from './ui';
import { ActiveTab } from '../types/nowcast';
import { severityColor } from '../design/tokens';
import { MAJOR_INDIAN_CITIES } from '../utils/weatherInterpreter';

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
  } = useNowcastStore();

  const summary = useLiveStore((s) => s.summary);
  const isLoading = useLiveStore((s) => s.isLoading);
  const refreshAll = useLiveStore((s) => s.refreshAll);

  const tabs = uiMode === 'citizen' ? CITIZEN_TABS : PRO_TABS;

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
        <div className="flex items-center rounded-lg p-0.5 bg-slate-900 border border-slate-700/80 text-xs">
          <button
            onClick={() => setUiMode('citizen')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium transition-all ${
              uiMode === 'citizen'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Switch to Public / Citizen Mode with simple language & safety tips"
          >
            <User className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Public Mode</span>
          </button>
          <button
            onClick={() => setUiMode('pro')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium transition-all ${
              uiMode === 'pro'
                ? 'bg-cyan-500 text-slate-950 font-bold shadow'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Switch to Pro Forecaster Mode with raw radar dBZ & sounding telemetry"
          >
            <Gauge className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Pro Mode</span>
          </button>
        </div>

        {/* Citizen Quick City Selector */}
        {uiMode === 'citizen' ? (
          <div className="hidden md:flex items-center gap-2 pl-3 border-l border-[var(--color-line)]">
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
              className="bg-slate-900/90 border border-cyan-500/40 text-cyan-300 text-xs rounded-lg px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-cyan-400 cursor-pointer font-medium"
            >
              {MAJOR_INDIAN_CITIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.state})
                </option>
              ))}
            </select>
          </div>
        ) : (
          /* Pro Live Telemetry Strip */
          summary && (
            <div className="hidden xl:flex items-center gap-5 pl-4 border-l border-[var(--color-line)]">
              <Reading
                icon={<Zap className="w-3.5 h-3.5" />}
                label="Flash rate"
                value={`${summary.flash_rate_per_min}/min`}
                provenance={summary.lightning_status}
              />
              <Reading
                icon={<AlertTriangle className="w-3.5 h-3.5" />}
                label="Active storms"
                value={`${summary.active_thunderstorms} of ${summary.nodes_monitored}`}
                provenance={summary.convective_status}
              />
              {summary.most_unstable && (
                <Reading
                  icon={<Activity className="w-3.5 h-3.5" />}
                  label="Most unstable"
                  value={summary.most_unstable.name}
                  badge={
                    <Badge color={severityColor(summary.most_unstable.instability)}>
                      {summary.most_unstable.instability}
                    </Badge>
                  }
                />
              )}
            </div>
          )
        )}

        <div className="flex-1" />

        {/* Navigation Tabs */}
        <nav className="hidden lg:flex items-center gap-0.5" aria-label="Primary">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              aria-current={activeTab === tab.id ? 'page' : undefined}
              className={`px-3 py-1.5 rounded-[6px] text-[12px] font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-[var(--color-ink)] bg-[var(--color-surface-overlay)] font-semibold'
                  : 'text-[var(--color-ink-faint)] hover:text-[var(--color-ink-muted)]'
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

const Reading: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string;
  provenance?: string;
  badge?: React.ReactNode;
}> = ({ icon, label, value, provenance, badge }) => (
  <div className="flex items-center gap-2">
    <span className="text-[var(--color-ink-faint)]">{icon}</span>
    <div className="leading-tight">
      <div className="eyebrow">{label}</div>
      <div className="flex items-center gap-1.5 mt-0.5">
        <span className="text-[12px] font-mono tabular text-[var(--color-ink)]">{value}</span>
        {provenance && <ProvenanceBadge provenance={provenance} />}
        {badge}
      </div>
    </div>
  </div>
);
