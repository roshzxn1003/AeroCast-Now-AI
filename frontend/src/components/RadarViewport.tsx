import React, { useState, useRef, useEffect } from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { ChannelMode, StormCell } from '../types/nowcast';
import { Layers, Compass, Crosshair, ZoomIn, ZoomOut, AlertCircle } from 'lucide-react';

export const RadarViewport: React.FC = () => {
  const { nowcastData, channelMode, setChannelMode, timeIndex } = useNowcastStore();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [selectedCell, setSelectedCell] = useState<StormCell | null>(null);

  // Active cells for current timeIndex
  let currentCells: StormCell[] = [];
  if (nowcastData) {
    if (timeIndex <= 3) {
      currentCells = nowcastData.observation.storm_cells;
    } else {
      const fc = nowcastData.forecast[timeIndex - 4];
      currentCells = fc?.cells || [];
    }
  }

  // Draw radar sweeps, range rings, and convective storm field on Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !nowcastData) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const center = width / 2;

    // Clear background
    ctx.fillStyle = '#0a0e14';
    ctx.fillRect(0, 0, width, height);

    // Draw Range Rings (50 km, 100 km, 150 km, 200 km)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    const maxRadius = center * 0.92;
    const rings = [0.25, 0.5, 0.75, 1.0];
    rings.forEach((r) => {
      ctx.beginPath();
      ctx.arc(center, center, maxRadius * r, 0, Math.PI * 2);
      ctx.stroke();
    });

    // Draw Crosshairs
    ctx.beginPath();
    ctx.moveTo(center, center - maxRadius);
    ctx.lineTo(center, center + maxRadius);
    ctx.moveTo(center - maxRadius, center);
    ctx.lineTo(center + maxRadius, center);
    ctx.stroke();

    // Render Convective Storm Grid (32x32 heatmap simulation)
    // Motion shift based on timeIndex
    const shiftX = (timeIndex - 3) * 6;
    const shiftY = -(timeIndex - 3) * 4;

    const grid = nowcastData.observation.dbz_grid || [];
    grid.forEach((pt) => {
      // Map 32x32 grid to canvas pixel space
      const px = (pt.x / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftX;
      const py = (pt.y / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftY;

      // Color mapping based on channelMode and value
      let color = 'rgba(56, 189, 248, 0.4)';
      const val = pt.v;

      if (channelMode === 'dbz') {
        if (val >= 60) color = 'rgba(217, 70, 239, 0.85)'; // Violent Magenta
        else if (val >= 50) color = 'rgba(239, 68, 68, 0.8)'; // Red
        else if (val >= 40) color = 'rgba(249, 115, 22, 0.75)'; // Orange
        else if (val >= 30) color = 'rgba(251, 191, 36, 0.7)'; // Yellow
        else if (val >= 20) color = 'rgba(74, 222, 128, 0.6)'; // Green
        else color = 'rgba(56, 189, 248, 0.4)'; // Cyan
      } else if (channelMode === 'vil') {
        if (val >= 35) color = 'rgba(239, 68, 68, 0.8)';
        else if (val >= 20) color = 'rgba(56, 189, 248, 0.75)';
        else color = 'rgba(74, 222, 128, 0.5)';
      } else if (channelMode === 'tir') {
        if (val >= 45) color = 'rgba(168, 85, 247, 0.85)';
        else if (val >= 30) color = 'rgba(239, 68, 68, 0.75)';
        else color = 'rgba(56, 189, 248, 0.5)';
      } else {
        // Flash density
        if (val >= 15) color = 'rgba(255, 255, 255, 0.95)';
        else if (val >= 8) color = 'rgba(250, 204, 21, 0.85)';
        else color = 'rgba(249, 115, 22, 0.6)';
      }

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(px, py, 18, 0, Math.PI * 2);
      ctx.fill();
    });

    // Draw Storm Cells & Kinematic Trajectory Cones
    currentCells.forEach((cell) => {
      const cx = (cell.centroid_pixel[1] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftX;
      const cy = (cell.centroid_pixel[0] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftY;

      // Trajectory projected points
      const p15x = (cell.projected_15min[1] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftX;
      const p15y = (cell.projected_15min[0] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftY;

      const p30x = (cell.projected_30min[1] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftX;
      const p30y = (cell.projected_30min[0] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftY;

      const p60x = (cell.projected_60min[1] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftX;
      const p60y = (cell.projected_60min[0] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftY;

      // Trajectory vector line (dotted)
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#f43f5e';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(p15x, p15y);
      ctx.lineTo(p30x, p30y);
      ctx.lineTo(p60x, p60y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Trajectory milestone dots
      [
        { x: p15x, y: p15y, label: '+15m' },
        { x: p30x, y: p30y, label: '+30m' },
        { x: p60x, y: p60y, label: '+60m' },
      ].forEach((p) => {
        ctx.fillStyle = '#fb7185';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#fda4af';
        ctx.font = '9px monospace';
        ctx.fillText(p.label, p.x + 4, p.y - 4);
      });

      // Cell Core Marker
      ctx.strokeStyle = cell.color || '#ef4444';
      ctx.lineWidth = 2.5;
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.beginPath();
      ctx.arc(cx, cy, 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Cross inside marker
      ctx.beginPath();
      ctx.moveTo(cx - 5, cy);
      ctx.lineTo(cx + 5, cy);
      ctx.moveTo(cx, cy - 5);
      ctx.lineTo(cx, cy + 5);
      ctx.stroke();

      // Label
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 10px sans-serif';
      ctx.fillText(`${cell.cell_id} (${cell.max_dbz} dBZ)`, cx + 12, cy + 3);
    });

    // Radar Center Station Cross
    ctx.fillStyle = '#38bdf8';
    ctx.strokeStyle = '#0284c7';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(center, center, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Range Ring Labels (km)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.font = '8px monospace';
    ctx.fillText('62km', center + maxRadius * 0.25 + 2, center - 4);
    ctx.fillText('125km', center + maxRadius * 0.5 + 2, center - 4);
    ctx.fillText('188km', center + maxRadius * 0.75 + 2, center - 4);
    ctx.fillText('250km', center + maxRadius * 1.0 - 28, center - 4);
  }, [nowcastData, channelMode, timeIndex, currentCells]);

  const channelOptions: { id: ChannelMode; label: string; unit: string }[] = [
    { id: 'dbz', label: 'Reflectivity', unit: 'dBZ' },
    { id: 'vil', label: 'VIL Liquid', unit: 'kg/m²' },
    { id: 'tir', label: 'INSAT-3D TIR', unit: '°C' },
    { id: 'flash', label: 'Lightning', unit: 'f/km²' },
  ];

  return (
    <div className="space-y-2">
      {/* Channel Switcher */}
      <div className="grid grid-cols-4 gap-1 p-1 bg-[#161b22] rounded-xl border border-white/10 text-xs">
        {channelOptions.map((opt) => (
          <button
            key={opt.id}
            onClick={() => setChannelMode(opt.id)}
            className={`py-1.5 px-2 rounded-lg font-bold text-center transition-all ${
              channelMode === opt.id
                ? 'bg-sky-500 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            <div className="leading-tight truncate">{opt.label}</div>
            <div className="text-[9px] opacity-70 font-mono font-normal">
              {opt.unit}
            </div>
          </button>
        ))}
      </div>

      {/* Radar Viewport Canvas Container */}
      <div className="relative aspect-square w-full rounded-2xl overflow-hidden border border-white/15 shadow-2xl bg-[#0a0e14]">
        <canvas
          ref={canvasRef}
          width={540}
          height={540}
          className="w-full h-full object-cover"
        />

        {/* Compass Cardinal Badge */}
        <div className="absolute top-2 left-2 flex items-center gap-1 bg-black/60 backdrop-blur-md px-2 py-0.5 rounded-md border border-white/10 text-[10px] text-slate-300 font-mono">
          <Compass className="w-3 h-3 text-sky-400" />
          <span>N 000° • 250km RADIAL</span>
        </div>

        {/* Motion Vector Heading Badge */}
        <div className="absolute top-2 right-2 bg-black/60 backdrop-blur-md px-2 py-0.5 rounded-md border border-white/10 text-[10px] text-amber-300 font-mono">
          <span>ENE 65° @ 42km/h</span>
        </div>

        {/* Legend Scale Bar */}
        <div className="absolute bottom-2 left-2 right-2 bg-black/75 backdrop-blur-md px-2.5 py-1.5 rounded-xl border border-white/10 flex flex-col gap-1">
          <div className="flex justify-between text-[9px] font-bold text-slate-300">
            <span>{channelMode.toUpperCase()} INTENSITY</span>
            <span>
              {channelMode === 'dbz'
                ? '0 — 75 dBZ'
                : channelMode === 'vil'
                ? '0 — 65 kg/m²'
                : channelMode === 'tir'
                ? '-85 — +35 °C'
                : '0 — 25 f/km²'}
            </span>
          </div>
          {channelMode === 'dbz' && (
            <div className="h-2 rounded-full overflow-hidden flex">
              <span className="flex-1 bg-[#38bdf8]" title="Light Rain (< 25)" />
              <span className="flex-1 bg-[#4ade80]" title="Moderate (25-35)" />
              <span className="flex-1 bg-[#facc15]" title="Heavy (35-45)" />
              <span className="flex-1 bg-[#f97316]" title="Intense (45-55)" />
              <span className="flex-1 bg-[#ef4444]" title="Severe Hail (55-65)" />
              <span className="flex-1 bg-[#d946ef]" title="Violent/Tornadic (> 65)" />
            </div>
          )}
          {channelMode === 'vil' && (
            <div className="h-2 rounded-full overflow-hidden flex bg-gradient-to-r from-emerald-500 via-sky-400 to-red-500" />
          )}
          {channelMode === 'tir' && (
            <div className="h-2 rounded-full overflow-hidden flex bg-gradient-to-r from-slate-200 via-sky-400 via-red-500 to-purple-600" />
          )}
          {channelMode === 'flash' && (
            <div className="h-2 rounded-full overflow-hidden flex bg-gradient-to-r from-transparent via-amber-400 via-orange-500 to-white" />
          )}
        </div>
      </div>
    </div>
  );
};
