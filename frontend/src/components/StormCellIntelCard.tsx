import React, { useMemo } from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { gridPixelToGeo } from '../utils/geoProjection';
import {
  X,
  Crosshair,
  Navigation,
  Zap,
  Activity,
  AlertTriangle,
  LocateFixed,
  ShieldAlert,
} from 'lucide-react';

interface StormCellIntelCardProps {
  onFocusCell?: (lat: number, lon: number) => void;
  className?: string;
}

export const StormCellIntelCard: React.FC<StormCellIntelCardProps> = ({
  onFocusCell,
  className = '',
}) => {
  const { selectedStormCell, setSelectedStormCell, nowcastData, stations, selectedStation } =
    useNowcastStore();

  const station = useMemo(() => {
    if (nowcastData?.location) {
      return {
        lat: nowcastData.location.lat,
        lon: nowcastData.location.lon,
        range_km: 256,
      };
    }
    const found = stations.find((s) => s.name === selectedStation);
    return {
      lat: found?.lat ?? 13.0827,
      lon: found?.lon ?? 80.2707,
      range_km: found?.range_km ?? 256,
    };
  }, [nowcastData, stations, selectedStation]);

  const cell = selectedStormCell;

  const currentGeo = useMemo(() => {
    if (!cell) return null;
    return gridPixelToGeo(
      cell.centroid_pixel[0],
      cell.centroid_pixel[1],
      station.lat,
      station.lon,
      station.range_km,
      32
    );
  }, [cell, station]);

  const proj15Geo = useMemo(() => {
    if (!cell?.projected_15min) return null;
    return gridPixelToGeo(
      cell.projected_15min[0],
      cell.projected_15min[1],
      station.lat,
      station.lon,
      station.range_km,
      32
    );
  }, [cell, station]);

  const proj30Geo = useMemo(() => {
    if (!cell?.projected_30min) return null;
    return gridPixelToGeo(
      cell.projected_30min[0],
      cell.projected_30min[1],
      station.lat,
      station.lon,
      station.range_km,
      32
    );
  }, [cell, station]);

  const proj60Geo = useMemo(() => {
    if (!cell?.projected_60min) return null;
    return gridPixelToGeo(
      cell.projected_60min[0],
      cell.projected_60min[1],
      station.lat,
      station.lon,
      station.range_km,
      32
    );
  }, [cell, station]);

  if (!cell || !currentGeo) return null;

  const severityBadgeClass =
    cell.severity === 'Severe' || cell.severity === 'Catastrophic'
      ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
      : cell.severity === 'Strong'
      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
      : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';

  const hailRiskClass =
    cell.hail_risk_pct > 60
      ? 'text-rose-400 font-bold'
      : cell.hail_risk_pct > 30
      ? 'text-amber-400 font-semibold'
      : 'text-slate-300';

  return (
    <div
      className={`absolute bottom-20 left-4 z-30 w-84 max-w-[calc(100vw-2rem)] rounded-2xl bg-slate-900/95 border border-cyan-500/40 shadow-2xl backdrop-blur-xl p-4 text-slate-100 transition-all duration-300 animate-in fade-in slide-in-from-left-4 ${className}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-white/10 pb-2.5">
        <div className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full shrink-0 shadow-sm animate-pulse"
            style={{ backgroundColor: cell.color || '#ef4444' }}
          />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold tracking-wider text-white">
                {cell.cell_id}
              </span>
              <span
                className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${severityBadgeClass}`}
              >
                {cell.severity}
              </span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">
              SCIT Centroid: {currentGeo.lat.toFixed(3)}°N, {currentGeo.lon.toFixed(3)}°E
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => onFocusCell?.(currentGeo.lat, currentGeo.lon)}
            title="Fly Camera to Storm Cell Centroid"
            className="p-1 rounded-lg text-cyan-400 hover:text-white hover:bg-cyan-900/40 transition-colors"
          >
            <Crosshair className="w-4 h-4" />
          </button>
          <button
            onClick={() => setSelectedStormCell(null)}
            title="Close Cell Intel"
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Core Telemetry Grid */}
      <div className="grid grid-cols-2 gap-2 my-2.5 text-xs">
        {/* Max Reflectivity */}
        <div className="p-2 rounded-xl bg-slate-800/60 border border-white/5 flex flex-col">
          <span className="text-[10px] uppercase font-mono text-slate-400 flex items-center gap-1">
            <Activity className="w-3 h-3 text-cyan-400" /> Max Reflectivity
          </span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="font-mono text-base font-bold text-amber-300">
              {cell.max_dbz.toFixed(1)}
            </span>
            <span className="text-[10px] font-mono text-slate-400">dBZ</span>
          </div>
          <span className="text-[9px] text-slate-500 font-mono">
            Mean: {cell.mean_dbz.toFixed(1)} dBZ
          </span>
        </div>

        {/* VIL */}
        <div className="p-2 rounded-xl bg-slate-800/60 border border-white/5 flex flex-col">
          <span className="text-[10px] uppercase font-mono text-slate-400 flex items-center gap-1">
            <LocateFixed className="w-3 h-3 text-emerald-400" /> VIL Core
          </span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="font-mono text-base font-bold text-emerald-300">
              {cell.max_vil_kg_m2.toFixed(1)}
            </span>
            <span className="text-[10px] font-mono text-slate-400">kg/m²</span>
          </div>
          <span className="text-[9px] text-slate-500 font-mono">
            Area: {cell.area_km2.toFixed(0)} km²
          </span>
        </div>

        {/* Kinematics */}
        <div className="p-2 rounded-xl bg-slate-800/60 border border-white/5 flex flex-col">
          <span className="text-[10px] uppercase font-mono text-slate-400 flex items-center gap-1">
            <Navigation className="w-3 h-3 text-indigo-400" /> Kinematics
          </span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="font-mono text-base font-bold text-indigo-200">
              {cell.speed_kmh.toFixed(0)}
            </span>
            <span className="text-[10px] font-mono text-slate-400">km/h</span>
          </div>
          <span className="text-[9px] text-slate-400 font-mono">
            Heading: {cell.heading_deg.toFixed(0)}°
          </span>
        </div>

        {/* Hail Risk */}
        <div className="p-2 rounded-xl bg-slate-800/60 border border-white/5 flex flex-col">
          <span className="text-[10px] uppercase font-mono text-slate-400 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3 text-amber-400" /> Hail Probability
          </span>
          <div className="flex items-baseline gap-1 mt-1">
            <span className={`font-mono text-base ${hailRiskClass}`}>
              {cell.hail_risk_pct.toFixed(0)}%
            </span>
          </div>
          <span className="text-[9px] text-slate-500 font-mono">
            {cell.hail_risk_pct > 50 ? 'Significant risk' : 'Low risk'}
          </span>
        </div>
      </div>

      {/* Projected Trajectory Path */}
      <div className="border-t border-white/10 pt-2 text-[10px] font-mono text-slate-400">
        <div className="flex items-center justify-between mb-1 text-slate-300 font-semibold">
          <span>AI Projected Trajectory</span>
          <span className="text-cyan-400 text-[9px]">SCIT Motion Model</span>
        </div>
        <div className="space-y-1 bg-slate-950/50 p-2 rounded-lg border border-white/5">
          {proj15Geo && (
            <div className="flex justify-between items-center">
              <span className="text-cyan-300">+15 min:</span>
              <span className="text-slate-200">
                {proj15Geo.lat.toFixed(3)}°N, {proj15Geo.lon.toFixed(3)}°E
              </span>
            </div>
          )}
          {proj30Geo && (
            <div className="flex justify-between items-center">
              <span className="text-indigo-300">+30 min:</span>
              <span className="text-slate-200">
                {proj30Geo.lat.toFixed(3)}°N, {proj30Geo.lon.toFixed(3)}°E
              </span>
            </div>
          )}
          {proj60Geo && (
            <div className="flex justify-between items-center">
              <span className="text-purple-300">+60 min:</span>
              <span className="text-slate-200">
                {proj60Geo.lat.toFixed(3)}°N, {proj60Geo.lon.toFixed(3)}°E
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Lightning Jump / Threat Status */}
      {nowcastData?.lightning_jump && (
        <div className="mt-2.5 pt-2 border-t border-white/10 flex items-center justify-between text-[11px]">
          <span className="text-slate-400 flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            Jump Status:
          </span>
          <span
            className={`font-mono font-bold px-2 py-0.5 rounded text-[10px] ${
              nowcastData.lightning_jump.jump_detected
                ? 'text-rose-400 bg-rose-950/60 border border-rose-500/30'
                : 'text-slate-300 bg-slate-800'
            }`}
          >
            {nowcastData.lightning_jump.jump_detected ? 'JUMP DETECTED' : 'NORMAL'}
          </span>
        </div>
      )}
    </div>
  );
};
