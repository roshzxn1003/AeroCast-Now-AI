import React, { useState } from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { CloudLightning, Radio, ChevronDown, RefreshCw, AlertCircle } from 'lucide-react';
import { StormScenario } from '../types/nowcast';

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
  } = useNowcastStore();

  const [showStationModal, setShowStationModal] = useState(false);
  const [showScenarioModal, setShowScenarioModal] = useState(false);

  const scenarios: StormScenario[] = [
    'Severe Squall Line',
    'Supercell Thunderstorm',
    'Multi-Cell Cluster',
  ];

  return (
    <>
      <header className="sticky top-0 z-40 bg-[#0d1117]/90 backdrop-blur-md border-b border-white/10 px-3 py-2.5">
        <div className="flex items-center justify-between gap-2 max-w-lg mx-auto">
          {/* Logo & Status */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500/20 via-orange-500/20 to-sky-500/20 border border-white/10 flex items-center justify-center text-red-400">
              <CloudLightning className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-sm tracking-tight gradient-text">
                  AeroCast-Now AI
                </span>
                <span className="sim-badge text-[9px] px-1.5 py-0.5">SIMULATED</span>
              </div>
              <div className="flex items-center gap-1 text-[11px] text-slate-400">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                <span>ConvLSTM 2.0</span>
                <span className="text-slate-600">•</span>
                <span>{nowcastData?.inference_time_ms ? `${nowcastData.inference_time_ms}ms` : 'Ready'}</span>
              </div>
            </div>
          </div>

          {/* Controls: Station & Scenario Quick Buttons */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setShowStationModal(true)}
              className="flex items-center gap-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-200 transition-colors"
            >
              <Radio className="w-3.5 h-3.5 text-sky-400" />
              <span className="max-w-[85px] truncate font-medium">
                {selectedStation.split(' ')[0]}
              </span>
              <ChevronDown className="w-3 h-3 text-slate-400" />
            </button>

            <button
              onClick={() => loadNowcast()}
              disabled={isLoading}
              className={`p-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-slate-300 transition-colors ${
                isLoading ? 'animate-spin text-sky-400' : ''
              }`}
              title="Refresh Nowcast"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Secondary Sub-Bar: Storm Scenario Selector */}
        <div className="flex items-center justify-between gap-2 max-w-lg mx-auto mt-2 pt-2 border-t border-white/5 text-[11px]">
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

      {/* Station Selection Modal */}
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

      {/* Storm Scenario Modal */}
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
