import React, { useState } from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import {
  CloudLightning,
  Radio,
  ChevronDown,
  RefreshCw,
  Radar,
  AlertTriangle,
  Activity,
  ShieldAlert,
  Menu,
} from 'lucide-react';
import { StormScenario, ActiveTab } from '../types/nowcast';

export const Header: React.FC = () => {
  const {
    selectedStation,
    setSelectedStation,
    stations,
    stormScenario,
    setStormScenario,
    isLoading,
    loadNowcast,
    nowcastData,
    activeTab,
    setActiveTab,
  } = useNowcastStore();

  const [showStationModal, setShowStationModal] = useState(false);
  const [showScenarioModal, setShowScenarioModal] = useState(false);

  const scenarios: StormScenario[] = [
    'Severe Squall Line',
    'Supercell Thunderstorm',
    'Multi-Cell Cluster',
  ];

  const hasJump = nowcastData?.lightning_jump?.jump_detected;
  const activeCellsCount = nowcastData?.observation?.storm_cells?.length || 0;

  const navTabs: { id: ActiveTab; label: string; icon: React.ComponentType<{ className?: string }>; badge?: string | number; badgeColor?: string }[] = [
    { id: 'nowcast', label: 'Nowcast', icon: Radar },
    { id: 'alerts', label: 'Alerts', icon: AlertTriangle, badge: hasJump ? 'JUMP' : undefined, badgeColor: 'bg-red-500 text-white animate-pulse' },
    { id: 'storms', label: 'Storm Cells', icon: Activity, badge: activeCellsCount > 0 ? activeCellsCount : undefined, badgeColor: 'bg-amber-500 text-slate-900' },
    { id: 'risk', label: 'Sector Risk', icon: ShieldAlert },
    { id: 'more', label: 'Diagnostics & Model', icon: Menu },
  ];

  return (
    <>
      <header className="sticky top-0 z-40 bg-[#0d1117]/95 backdrop-blur-md border-b border-white/10 px-3 py-2.5 lg:px-6">
        <div className="w-full max-w-7xl mx-auto flex items-center justify-between gap-3">
          {/* Brand Logo & Telemetry Status */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 lg:w-9 lg:h-9 rounded-xl bg-gradient-to-br from-red-500/20 via-orange-500/20 to-sky-500/20 border border-white/10 flex items-center justify-center text-red-400 shrink-0">
              <CloudLightning className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-sm lg:text-base tracking-tight gradient-text">
                  AeroCast-Now AI
                </span>
                <span className="sim-badge text-[9px] px-1.5 py-0.5">SIMULATED</span>
              </div>
              <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                <span className="font-mono">ConvLSTM 2.0</span>
                <span className="text-slate-600">•</span>
                <span className="hidden sm:inline text-slate-400">Inference:</span>
                <span className="font-mono text-sky-400 font-semibold">
                  {nowcastData?.inference_time_ms ? `${nowcastData.inference_time_ms}ms` : 'Ready'}
                </span>
              </div>
            </div>
          </div>

          {/* Desktop Navigation Links (Visible on lg screens >= 1024px) */}
          <nav className="hidden lg:flex items-center gap-1 bg-[#161b22] p-1 rounded-xl border border-white/10">
            {navTabs.map((tab) => {
              const isActive = activeTab === tab.id;
              const Icon = tab.icon;

              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all relative ${
                    isActive
                      ? 'bg-sky-500 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                  {tab.badge && (
                    <span
                      className={`text-[9px] font-black px-1.5 py-0.2 rounded-full ml-0.5 ${tab.badgeColor}`}
                    >
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Controls: Station & Scenario Selectors */}
          <div className="flex items-center gap-2">
            {/* Desktop Station Select Dropdown */}
            <div className="relative hidden md:block">
              <select
                value={selectedStation}
                onChange={(e) => setSelectedStation(e.target.value)}
                className="bg-[#161b22] hover:bg-[#1c222c] border border-white/15 text-slate-200 text-xs font-semibold rounded-lg px-2.5 py-1.5 appearance-none pr-8 cursor-pointer transition-colors max-w-[210px] truncate"
              >
                {stations.map((st) => (
                  <option key={st.name} value={st.name} className="bg-[#161b22] text-slate-200">
                    {st.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>

            {/* Mobile Station Button (Triggers Modal) */}
            <button
              onClick={() => setShowStationModal(true)}
              className="md:hidden flex items-center gap-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-200 transition-colors"
            >
              <Radio className="w-3.5 h-3.5 text-sky-400" />
              <span className="max-w-[90px] truncate font-medium">
                {selectedStation.split(' ')[0]}
              </span>
              <ChevronDown className="w-3 h-3 text-slate-400" />
            </button>

            {/* Desktop Scenario Dropdown */}
            <div className="relative hidden md:block">
              <select
                value={stormScenario}
                onChange={(e) => setStormScenario(e.target.value as StormScenario)}
                className="bg-[#161b22] hover:bg-[#1c222c] border border-amber-500/30 text-amber-300 text-xs font-bold rounded-lg px-2.5 py-1.5 appearance-none pr-8 cursor-pointer transition-colors max-w-[190px] truncate"
              >
                {scenarios.map((sc) => (
                  <option key={sc} value={sc} className="bg-[#161b22] text-amber-300">
                    {sc}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-amber-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>

            {/* Refresh Button */}
            <button
              onClick={() => loadNowcast()}
              disabled={isLoading}
              className={`p-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-slate-300 transition-colors ${
                isLoading ? 'animate-spin text-sky-400' : ''
              }`}
              title="Refresh Nowcast & Radar Sweep"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Mobile Secondary Sub-Bar: Storm Scenario Selector (hidden on desktop) */}
        <div className="flex md:hidden items-center justify-between gap-2 max-w-lg mx-auto mt-2 pt-2 border-t border-white/5 text-[11px]">
          <div className="flex items-center gap-1 text-slate-400 truncate">
            <span className="text-slate-500">Mode:</span>
            <button
              onClick={() => setShowScenarioModal(true)}
              className="text-amber-400 font-semibold underline underline-offset-2 hover:text-amber-300 flex items-center gap-0.5 truncate"
            >
              {stormScenario}
              <ChevronDown className="w-2.5 h-2.5" />
            </button>
          </div>
          <div className="text-[10px] text-slate-500 font-mono">
            Grid: 32×32 (128km)
          </div>
        </div>
      </header>

      {/* Station Selection Modal (Mobile) */}
      {showStationModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-[#161b22] border border-white/10 rounded-t-2xl sm:rounded-2xl w-full max-w-md max-h-[80vh] flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-6">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-sky-400" />
                <h3 className="font-bold text-sm text-slate-200">
                  Select Doppler Radar Station
                </h3>
              </div>
              <button
                onClick={() => setShowStationModal(false)}
                className="text-slate-400 hover:text-white text-xs px-2 py-1"
              >
                Close
              </button>
            </div>
            <div className="p-2 overflow-y-auto space-y-1">
              {stations.map((st) => {
                const isSelected = st.name === selectedStation;
                return (
                  <button
                    key={st.name}
                    onClick={() => {
                      setSelectedStation(st.name);
                      setShowStationModal(false);
                    }}
                    className={`w-full text-left p-3 rounded-xl transition-colors flex items-center justify-between ${
                      isSelected
                        ? 'bg-sky-500/20 border border-sky-500/40 text-sky-300'
                        : 'bg-white/5 hover:bg-white/10 border border-transparent text-slate-300'
                    }`}
                  >
                    <div>
                      <div className="font-semibold text-xs text-slate-100">
                        {st.name}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {st.state} • {st.radar_type} ({st.freq_ghz} GHz)
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                        {st.lat.toFixed(4)}°N, {st.lon.toFixed(4)}°E • Radius 250km
                      </div>
                    </div>
                    {isSelected && (
                      <span className="w-2 h-2 rounded-full bg-sky-400 shadow-sm shadow-sky-400" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Storm Scenario Modal (Mobile) */}
      {showScenarioModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
          <div className="bg-[#161b22] border border-white/10 rounded-t-2xl sm:rounded-2xl w-full max-w-md p-4 space-y-3 animate-in fade-in slide-in-from-bottom-6">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-200">
                Select Convective Storm Morphology
              </h3>
              <button
                onClick={() => setShowScenarioModal(false)}
                className="text-slate-400 hover:text-white text-xs"
              >
                Close
              </button>
            </div>
            <p className="text-[11px] text-slate-400">
              Selects the simulated meteorological atmospheric dynamics model to evaluate:
            </p>
            <div className="space-y-2">
              {scenarios.map((sc) => {
                const isSelected = sc === stormScenario;
                return (
                  <button
                    key={sc}
                    onClick={() => {
                      setStormScenario(sc);
                      setShowScenarioModal(false);
                    }}
                    className={`w-full text-left p-3 rounded-xl transition-colors ${
                      isSelected
                        ? 'bg-amber-500/20 border border-amber-500/40 text-amber-300'
                        : 'bg-white/5 hover:bg-white/10 border border-transparent text-slate-300'
                    }`}
                  >
                    <div className="font-bold text-xs">{sc}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {sc === 'Severe Squall Line' && 'Linear convective front with intense multi-cell cores along gust front'}
                      {sc === 'Supercell Thunderstorm' && 'Isolated rotating convective cell with hook echo and severe hail core'}
                      {sc === 'Multi-Cell Cluster' && 'Scattered clusters with varying maturation and pulse microburst risk'}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
