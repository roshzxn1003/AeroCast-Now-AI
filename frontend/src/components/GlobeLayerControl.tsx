import React, { useState } from 'react';
import { useNowcastStore, GlobeLayers } from '../store/nowcastStore';
import {
  Layers,
  Eye,
  EyeOff,
  Zap,
  Radio,
  Compass,
  CloudRain,
  Activity,
  Sliders,
  ChevronDown,
  ChevronUp,
  MapPin,
  Sparkles,
} from 'lucide-react';

interface GlobeLayerControlProps {
  hasRadarData: boolean;
  hasLightningData: boolean;
  hasStormCells: boolean;
  hasPrediction: boolean;
  hasSoundings: boolean;
}

export const GlobeLayerControl: React.FC<GlobeLayerControlProps> = ({
  hasRadarData,
  hasLightningData,
  hasStormCells,
  hasPrediction,
  hasSoundings,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const { layers, setLayers, radarOpacity, setRadarOpacity } = useNowcastStore();

  const toggleLayer = (key: keyof GlobeLayers) => {
    if (typeof layers[key] === 'boolean') {
      setLayers({ [key]: !layers[key] });
    }
  };

  const activeCount = [
    layers.earth,
    layers.radar && hasRadarData,
    layers.lightning && hasLightningData,
    layers.stormCells && hasStormCells,
    layers.aiPrediction && hasPrediction,
    layers.stormTracks && hasStormCells,
    layers.soundingNodes && hasSoundings,
    layers.districts,
  ].filter(Boolean).length;

  return (
    <div className="absolute top-16 right-3 z-30 pointer-events-auto">
      {/* Floating Collapsible Trigger */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-white/10 shadow-xl backdrop-blur-md text-xs font-semibold text-slate-200 hover:text-white hover:border-cyan-500/40 transition-all group"
        title="Toggle Globe Layer Manager"
      >
        <Layers className="w-3.5 h-3.5 text-cyan-400 group-hover:rotate-12 transition-transform" />
        <span className="font-mono tracking-tight">LAYERS</span>
        <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
          {activeCount}/8
        </span>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5 ml-0.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 ml-0.5 text-slate-400" />}
      </button>

      {/* Expanded Glassmorphic Drawer */}
      {isOpen && (
        <div className="mt-2 w-72 rounded-2xl bg-slate-900/95 border border-cyan-500/30 shadow-2xl backdrop-blur-md p-3.5 space-y-3.5 enter">
          <div className="flex items-center justify-between pb-2 border-b border-white/10">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-100 uppercase tracking-wider font-mono">
              <Sliders className="w-3.5 h-3.5 text-cyan-400" />
              <span>Meteorological Layers</span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">Phase 6 GIS</span>
          </div>

          {/* Layer List */}
          <div className="space-y-1.5 text-xs">
            {/* 1. Radar Layer & Opacity */}
            <div className={`p-2 rounded-xl border transition-all ${
              layers.radar && hasRadarData
                ? 'bg-slate-800/60 border-cyan-500/40'
                : 'bg-slate-900/40 border-transparent opacity-60'
            }`}>
              <div className="flex items-center justify-between">
                <button
                  disabled={!hasRadarData}
                  onClick={() => toggleLayer('radar')}
                  className="flex items-center gap-2 text-left disabled:cursor-not-allowed"
                >
                  <CloudRain className={`w-3.5 h-3.5 ${layers.radar ? 'text-sky-400' : 'text-slate-500'}`} />
                  <div>
                    <div className="font-bold text-slate-200 flex items-center gap-1.5">
                      Doppler Radar (dBZ)
                      {!hasRadarData && <span className="text-[9px] text-rose-400 font-normal">Offline</span>}
                    </div>
                    <div className="text-[10px] text-slate-400">Reflectivity & VIL Grids</div>
                  </div>
                </button>
                <button
                  disabled={!hasRadarData}
                  onClick={() => toggleLayer('radar')}
                  className="p-1 text-slate-400 hover:text-white"
                >
                  {layers.radar && hasRadarData ? <Eye className="w-3.5 h-3.5 text-cyan-400" /> : <EyeOff className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Opacity Slider */}
              {layers.radar && hasRadarData && (
                <div className="mt-2 pt-2 border-t border-white/5 space-y-1">
                  <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                    <span>Radar Opacity:</span>
                    <span className="text-cyan-300 font-bold">{Math.round(radarOpacity * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min={0.1}
                    max={1.0}
                    step={0.05}
                    value={radarOpacity}
                    onChange={(e) => setRadarOpacity(parseFloat(e.target.value))}
                    className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                  />
                </div>
              )}
            </div>

            {/* 2. Lightning Layer with Flashes / Density Switch */}
            <div className={`p-2 rounded-xl border transition-all ${
              layers.lightning && hasLightningData
                ? 'bg-slate-800/60 border-amber-500/40'
                : 'bg-slate-900/40 border-transparent opacity-60'
            }`}>
              <div className="flex items-center justify-between">
                <button
                  disabled={!hasLightningData}
                  onClick={() => toggleLayer('lightning')}
                  className="flex items-center gap-2 text-left disabled:cursor-not-allowed"
                >
                  <Zap className={`w-3.5 h-3.5 ${layers.lightning ? 'text-amber-400' : 'text-slate-500'}`} />
                  <div>
                    <div className="font-bold text-slate-200">Lightning Detection</div>
                    <div className="text-[10px] text-slate-400">Real-time CG & IC telemetry</div>
                  </div>
                </button>
                <button
                  disabled={!hasLightningData}
                  onClick={() => toggleLayer('lightning')}
                  className="p-1 text-slate-400 hover:text-white"
                >
                  {layers.lightning && hasLightningData ? <Eye className="w-3.5 h-3.5 text-amber-400" /> : <EyeOff className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Flashes vs Density Mode Toggle */}
              {layers.lightning && hasLightningData && (
                <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between">
                  <span className="text-[10px] text-slate-400 font-mono">Display Mode:</span>
                  <div className="inline-flex rounded-lg bg-black/40 p-0.5 border border-white/10 text-[10px] font-mono">
                    <button
                      onClick={() => setLayers({ lightningMode: 'flashes' })}
                      className={`px-2 py-0.5 rounded-md transition-all ${
                        layers.lightningMode === 'flashes'
                          ? 'bg-amber-500/30 text-amber-300 font-bold'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      FLASHES
                    </button>
                    <button
                      onClick={() => setLayers({ lightningMode: 'density' })}
                      className={`px-2 py-0.5 rounded-md transition-all ${
                        layers.lightningMode === 'density'
                          ? 'bg-cyan-500/30 text-cyan-300 font-bold'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      DENSITY
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* 3. AI Prediction Layer */}
            <div className={`p-2 rounded-xl border transition-all ${
              layers.aiPrediction && hasPrediction
                ? 'bg-slate-800/60 border-purple-500/40'
                : 'bg-slate-900/40 border-transparent opacity-60'
            }`}>
              <div className="flex items-center justify-between">
                <button
                  disabled={!hasPrediction}
                  onClick={() => toggleLayer('aiPrediction')}
                  className="flex items-center gap-2 text-left disabled:cursor-not-allowed"
                >
                  <Sparkles className={`w-3.5 h-3.5 ${layers.aiPrediction ? 'text-purple-400' : 'text-slate-500'}`} />
                  <div>
                    <div className="font-bold text-slate-200">AI ConvLSTM Forecast</div>
                    <div className="text-[10px] text-slate-400">+15 to +60m Rollout Grid</div>
                  </div>
                </button>
                <button
                  disabled={!hasPrediction}
                  onClick={() => toggleLayer('aiPrediction')}
                  className="p-1 text-slate-400 hover:text-white"
                >
                  {layers.aiPrediction && hasPrediction ? <Eye className="w-3.5 h-3.5 text-purple-400" /> : <EyeOff className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* 4. Active Storm Cells (SCIT) */}
            <div className={`p-2 rounded-xl border transition-all ${
              layers.stormCells && hasStormCells
                ? 'bg-slate-800/60 border-red-500/40'
                : 'bg-slate-900/40 border-transparent opacity-60'
            }`}>
              <div className="flex items-center justify-between">
                <button
                  disabled={!hasStormCells}
                  onClick={() => toggleLayer('stormCells')}
                  className="flex items-center gap-2 text-left disabled:cursor-not-allowed"
                >
                  <Activity className={`w-3.5 h-3.5 ${layers.stormCells ? 'text-red-400' : 'text-slate-500'}`} />
                  <div>
                    <div className="font-bold text-slate-200">Storm Cells (SCIT)</div>
                    <div className="text-[10px] text-slate-400">Centroids, Severity, Hail Risk</div>
                  </div>
                </button>
                <button
                  disabled={!hasStormCells}
                  onClick={() => toggleLayer('stormCells')}
                  className="p-1 text-slate-400 hover:text-white"
                >
                  {layers.stormCells && hasStormCells ? <Eye className="w-3.5 h-3.5 text-red-400" /> : <EyeOff className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* 5. Storm Motion Vectors & Tracks */}
            <div className={`p-2 rounded-xl border transition-all ${
              layers.stormTracks && hasStormCells
                ? 'bg-slate-800/60 border-indigo-500/40'
                : 'bg-slate-900/40 border-transparent opacity-60'
            }`}>
              <div className="flex items-center justify-between">
                <button
                  disabled={!hasStormCells}
                  onClick={() => toggleLayer('stormTracks')}
                  className="flex items-center gap-2 text-left disabled:cursor-not-allowed"
                >
                  <Compass className={`w-3.5 h-3.5 ${layers.stormTracks ? 'text-indigo-400' : 'text-slate-500'}`} />
                  <div>
                    <div className="font-bold text-slate-200">Storm Tracks & Motion</div>
                    <div className="text-[10px] text-slate-400">Kinematics & Uncertainty Cones</div>
                  </div>
                </button>
                <button
                  disabled={!hasStormCells}
                  onClick={() => toggleLayer('stormTracks')}
                  className="p-1 text-slate-400 hover:text-white"
                >
                  {layers.stormTracks && hasStormCells ? <Eye className="w-3.5 h-3.5 text-indigo-400" /> : <EyeOff className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* 6. Convective Sounding Nodes */}
            <div className={`p-2 rounded-xl border transition-all ${
              layers.soundingNodes && hasSoundings
                ? 'bg-slate-800/60 border-emerald-500/40'
                : 'bg-slate-900/40 border-transparent opacity-60'
            }`}>
              <div className="flex items-center justify-between">
                <button
                  disabled={!hasSoundings}
                  onClick={() => toggleLayer('soundingNodes')}
                  className="flex items-center gap-2 text-left disabled:cursor-not-allowed"
                >
                  <Radio className={`w-3.5 h-3.5 ${layers.soundingNodes ? 'text-emerald-400' : 'text-slate-500'}`} />
                  <div>
                    <div className="font-bold text-slate-200">Sounding Beacons</div>
                    <div className="text-[10px] text-slate-400">CAPE & Instability Columns</div>
                  </div>
                </button>
                <button
                  disabled={!hasSoundings}
                  onClick={() => toggleLayer('soundingNodes')}
                  className="p-1 text-slate-400 hover:text-white"
                >
                  {layers.soundingNodes && hasSoundings ? <Eye className="w-3.5 h-3.5 text-emerald-400" /> : <EyeOff className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* 7. Districts Layer */}
            <div className={`p-2 rounded-xl border transition-all ${
              layers.districts
                ? 'bg-slate-800/60 border-cyan-500/40'
                : 'bg-slate-900/40 border-transparent opacity-60'
            }`}>
              <div className="flex items-center justify-between">
                <button
                  onClick={() => toggleLayer('districts')}
                  className="flex items-center gap-2 text-left"
                >
                  <MapPin className={`w-3.5 h-3.5 ${layers.districts ? 'text-cyan-400' : 'text-slate-500'}`} />
                  <div>
                    <div className="font-bold text-slate-200">District Boundaries</div>
                    <div className="text-[10px] text-slate-400">734 India / 38 TN Districts</div>
                  </div>
                </button>
                <button
                  onClick={() => toggleLayer('districts')}
                  className="p-1 text-slate-400 hover:text-white"
                >
                  {layers.districts ? <Eye className="w-3.5 h-3.5 text-cyan-400" /> : <EyeOff className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
