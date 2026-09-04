import React, { useState, useRef, useEffect } from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { ChannelMode, StormCell } from '../types/nowcast';
import {
  Compass,
  Crosshair,
  Zap,
  Activity,
  Layers,
  Eye,
  EyeOff,
  Navigation,
  X,
  Radio,
} from 'lucide-react';

export const RadarViewport: React.FC = () => {
  const { nowcastData, channelMode, setChannelMode, timeIndex } = useNowcastStore();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [selectedCell, setSelectedCell] = useState<StormCell | null>(null);
  const [enableSweep, setEnableSweep] = useState(true);
  const [sweepAngle, setSweepAngle] = useState(0);

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

  // Radar sweep rotation animation loop
  useEffect(() => {
    if (!enableSweep) return;
    let animId: number;
    const animate = () => {
      setSweepAngle((prev) => (prev + 0.025) % (Math.PI * 2));
      animId = requestAnimationFrame(animate);
    };
    animId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animId);
  }, [enableSweep]);

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
    ctx.fillStyle = '#080c12';
    ctx.fillRect(0, 0, width, height);

    // Subtle background concentric radial gradient
    const radialGrad = ctx.createRadialGradient(center, center, 10, center, center, center * 0.95);
    radialGrad.addColorStop(0, '#0c121c');
    radialGrad.addColorStop(1, '#06090e');
    ctx.fillStyle = radialGrad;
    ctx.fillRect(0, 0, width, height);

    // Draw Range Rings (50 km, 100 km, 150 km, 200 km, 250 km)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    const maxRadius = center * 0.90;
    const rings = [0.25, 0.5, 0.75, 1.0];
    rings.forEach((r) => {
      ctx.beginPath();
      ctx.arc(center, center, maxRadius * r, 0, Math.PI * 2);
      ctx.stroke();
    });

    // Draw Crosshairs & Cardinal Spoke Lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
    ctx.beginPath();
    ctx.moveTo(center, center - maxRadius);
    ctx.lineTo(center, center + maxRadius);
    ctx.moveTo(center - maxRadius, center);
    ctx.lineTo(center + maxRadius, center);
    ctx.stroke();

    // 45-degree diagonal guideline spokes
    ctx.beginPath();
    const d45 = maxRadius * 0.7071;
    ctx.moveTo(center - d45, center - d45);
    ctx.lineTo(center + d45, center + d45);
    ctx.moveTo(center - d45, center + d45);
    ctx.lineTo(center + d45, center - d45);
    ctx.stroke();

    // Render Convective Storm Grid (32x32 heatmap simulation)
    const shiftX = (timeIndex - 3) * 8;
    const shiftY = -(timeIndex - 3) * 5;

    const grid = nowcastData.observation.dbz_grid || [];
    grid.forEach((pt) => {
      const px = (pt.x / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftX;
      const py = (pt.y / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftY;

      let color = 'rgba(56, 189, 248, 0.35)';
      const val = pt.v;

      if (channelMode === 'dbz') {
        if (val >= 60) color = 'rgba(217, 70, 239, 0.9)'; // Magenta
        else if (val >= 50) color = 'rgba(239, 68, 68, 0.85)'; // Red
        else if (val >= 40) color = 'rgba(249, 115, 22, 0.8)'; // Orange
        else if (val >= 30) color = 'rgba(251, 191, 36, 0.75)'; // Yellow
        else if (val >= 20) color = 'rgba(74, 222, 128, 0.65)'; // Green
        else color = 'rgba(56, 189, 248, 0.4)'; // Cyan
      } else if (channelMode === 'vil') {
        if (val >= 35) color = 'rgba(239, 68, 68, 0.85)';
        else if (val >= 20) color = 'rgba(56, 189, 248, 0.8)';
        else color = 'rgba(74, 222, 128, 0.55)';
      } else if (channelMode === 'tir') {
        if (val >= 45) color = 'rgba(168, 85, 247, 0.9)';
        else if (val >= 30) color = 'rgba(239, 68, 68, 0.8)';
        else color = 'rgba(56, 189, 248, 0.55)';
      } else {
        // Flash density
        if (val >= 15) color = 'rgba(255, 255, 255, 0.95)';
        else if (val >= 8) color = 'rgba(250, 204, 21, 0.9)';
        else color = 'rgba(249, 115, 22, 0.65)';
      }

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(px, py, 22, 0, Math.PI * 2);
      ctx.fill();
    });

    // Draw Radar Sweep Beam if enabled
    if (enableSweep) {
      ctx.save();
      const sweepGrad = ctx.createRadialGradient(center, center, 0, center, center, maxRadius);
      sweepGrad.addColorStop(0, 'rgba(56, 189, 248, 0.3)');
      sweepGrad.addColorStop(1, 'rgba(56, 189, 248, 0.0)');

      ctx.beginPath();
      ctx.moveTo(center, center);
      ctx.arc(center, center, maxRadius, sweepAngle - 0.25, sweepAngle);
      ctx.closePath();
      ctx.fillStyle = 'rgba(56, 189, 248, 0.08)';
      ctx.fill();

      // Leading beam line
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(center, center);
      ctx.lineTo(center + Math.cos(sweepAngle) * maxRadius, center + Math.sin(sweepAngle) * maxRadius);
      ctx.stroke();
      ctx.restore();
    }

    // Draw Storm Cells & Kinematic Trajectory Cones
    currentCells.forEach((cell) => {
      const isSelected = selectedCell?.cell_id === cell.cell_id;
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
      ctx.strokeStyle = isSelected ? '#fbbf24' : '#f43f5e';
      ctx.lineWidth = isSelected ? 2.5 : 1.8;
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
        ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
        ctx.font = '10px monospace';
        ctx.fillText(p.label, p.x + 5, p.y - 4);
      });

      // Cell Core Marker
      ctx.strokeStyle = isSelected ? '#fbbf24' : cell.color || '#ef4444';
      ctx.lineWidth = isSelected ? 3.5 : 2.5;
      ctx.fillStyle = isSelected ? 'rgba(251, 191, 36, 0.25)' : 'rgba(0, 0, 0, 0.75)';
      ctx.beginPath();
      ctx.arc(cx, cy, isSelected ? 14 : 11, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Cross inside marker
      ctx.beginPath();
      ctx.moveTo(cx - 6, cy);
      ctx.lineTo(cx + 6, cy);
      ctx.moveTo(cx, cy - 6);
      ctx.lineTo(cx, cy + 6);
      ctx.stroke();

      // Label with shadow
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 11px sans-serif';
      ctx.fillText(`${cell.cell_id} (${cell.max_dbz} dBZ)`, cx + 14, cy + 4);
    });

    // Radar Center Station Cross
    ctx.fillStyle = '#38bdf8';
    ctx.strokeStyle = '#0284c7';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(center, center, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Range Ring Labels (km)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.font = '9px monospace';
    ctx.fillText('62 km', center + maxRadius * 0.25 + 3, center - 5);
    ctx.fillText('125 km', center + maxRadius * 0.5 + 3, center - 5);
    ctx.fillText('188 km', center + maxRadius * 0.75 + 3, center - 5);
    ctx.fillText('250 km', center + maxRadius * 1.0 - 36, center - 5);
  }, [nowcastData, channelMode, timeIndex, currentCells, enableSweep, sweepAngle, selectedCell]);

  // Handle Canvas Click to Select Storm Cell
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !nowcastData) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = ((e.clientX - rect.left) / rect.width) * canvas.width;
    const clickY = ((e.clientY - rect.top) / rect.height) * canvas.height;

    const center = canvas.width / 2;
    const maxRadius = center * 0.90;
    const shiftX = (timeIndex - 3) * 8;
    const shiftY = -(timeIndex - 3) * 5;

    // Check if clicked near any storm cell
    for (const cell of currentCells) {
      const cx = (cell.centroid_pixel[1] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftX;
      const cy = (cell.centroid_pixel[0] / 32) * (maxRadius * 1.6) + (center - maxRadius * 0.8) + shiftY;
      const dist = Math.hypot(clickX - cx, clickY - cy);
      if (dist <= 22) {
        setSelectedCell(cell);
        return;
      }
    }
    setSelectedCell(null);
  };

  const channelOptions: { id: ChannelMode; label: string; unit: string }[] = [
    { id: 'dbz', label: 'Reflectivity', unit: 'dBZ' },
    { id: 'vil', label: 'VIL Liquid', unit: 'kg/m²' },
    { id: 'tir', label: 'INSAT-3D TIR', unit: '°C' },
    { id: 'flash', label: 'Lightning', unit: 'f/km²' },
  ];

  return (
    <div className="space-y-2.5">
      {/* Channel Switcher with High-Tech Pill Tabs */}
      <div className="flex items-center justify-between gap-2">
        <div className="grid grid-cols-4 gap-1 p-1 bg-[#161b22] rounded-xl border border-white/10 text-xs flex-1">
          {channelOptions.map((opt) => (
            <button
              key={opt.id}
              onClick={() => setChannelMode(opt.id)}
              className={`py-1.5 px-2 rounded-lg font-bold text-center transition-all ${
                channelMode === opt.id
                  ? 'bg-sky-500 text-white shadow-md shadow-sky-950'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              <div className="leading-tight truncate text-xs">{opt.label}</div>
              <div className="text-[9px] opacity-70 font-mono font-normal">
                {opt.unit}
              </div>
            </button>
          ))}
        </div>

        {/* Radar Sweep Animation Toggle */}
        <button
          onClick={() => setEnableSweep(!enableSweep)}
          className={`p-2 rounded-xl border transition-all text-xs font-semibold flex items-center gap-1.5 shrink-0 ${
            enableSweep
              ? 'bg-sky-500/20 border-sky-500/40 text-sky-300'
              : 'bg-[#161b22] border-white/10 text-slate-400 hover:text-slate-200'
          }`}
          title={enableSweep ? 'Disable Beam Sweep' : 'Enable Beam Sweep'}
        >
          <Radio className={`w-3.5 h-3.5 ${enableSweep ? 'animate-pulse text-sky-400' : ''}`} />
          <span className="hidden sm:inline font-mono text-[11px]">
            {enableSweep ? 'SWEEP ON' : 'SWEEP OFF'}
          </span>
        </button>
      </div>

      {/* Radar Viewport Canvas Container */}
      <div className="relative aspect-square w-full max-h-[580px] rounded-2xl overflow-hidden border border-white/15 shadow-2xl bg-[#080c12]">
        <canvas
          ref={canvasRef}
          width={540}
          height={540}
          onClick={handleCanvasClick}
          className="w-full h-full object-cover cursor-crosshair"
        />

        {/* Compass Cardinal Badge */}
        <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-black/70 backdrop-blur-md px-2.5 py-1 rounded-lg border border-white/10 text-[11px] text-slate-300 font-mono shadow">
          <Compass className="w-3.5 h-3.5 text-sky-400" />
          <span>N 000° • 250km RADIAL</span>
        </div>

        {/* Convective Motion Vector Heading Badge */}
        <div className="absolute top-3 right-3 bg-black/70 backdrop-blur-md px-2.5 py-1 rounded-lg border border-white/10 text-[11px] text-amber-300 font-mono shadow flex items-center gap-1.5">
          <Navigation className="w-3 h-3 text-amber-400" />
          <span>ENE 65° @ 42km/h</span>
        </div>

        {/* Selected Cell Floating HUD Inspector Popover */}
        {selectedCell && (
          <div className="absolute top-12 left-3 right-3 sm:right-auto sm:w-72 bg-[#161b22]/95 backdrop-blur-md border border-amber-500/40 rounded-xl p-3 shadow-2xl animate-in fade-in slide-in-from-top-2 text-xs space-y-2 z-10">
            <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                <span className="font-extrabold text-white text-sm">
                  {selectedCell.cell_id}
                </span>
                <span className="text-[9px] font-bold text-amber-300 bg-amber-500/20 px-1.5 py-0.5 rounded">
                  {selectedCell.severity}
                </span>
              </div>
              <button
                onClick={() => setSelectedCell(null)}
                className="text-slate-400 hover:text-white p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-1.5 text-center text-[10px]">
              <div className="bg-black/40 p-1.5 rounded">
                <div className="text-slate-400">Max dBZ</div>
                <div className="font-bold text-orange-400 mt-0.5">
                  {selectedCell.max_dbz}
                </div>
              </div>
              <div className="bg-black/40 p-1.5 rounded">
                <div className="text-slate-400">VIL Core</div>
                <div className="font-bold text-sky-400 mt-0.5">
                  {selectedCell.max_vil_kg_m2} kg/m²
                </div>
              </div>
              <div className="bg-black/40 p-1.5 rounded">
                <div className="text-slate-400">Hail Risk</div>
                <div className="font-bold text-red-400 mt-0.5">
                  {selectedCell.hail_risk_pct}%
                </div>
              </div>
            </div>

            <div className="text-[10px] text-slate-400 font-mono pt-1 border-t border-white/5 flex justify-between">
              <span>Velocity: {selectedCell.speed_kmh} km/h</span>
              <span>Heading: {selectedCell.heading_deg}° ENE</span>
            </div>
          </div>
        )}

        {/* Clean Meteorological Intensity Legend Bar */}
        <div className="absolute bottom-3 left-3 right-3 bg-black/80 backdrop-blur-md px-3 py-2 rounded-xl border border-white/10 flex flex-col gap-1.5 shadow-xl">
          <div className="flex justify-between text-[10px] font-bold text-slate-300">
            <span className="font-mono">{channelMode.toUpperCase()} METEOROLOGICAL INTENSITY SCALE</span>
            <span className="font-mono text-sky-400">
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
            <div className="space-y-1">
              <div className="h-2.5 rounded-full overflow-hidden flex shadow-inner">
                <span className="flex-1 bg-[#38bdf8]" title="Light (< 25 dBZ)" />
                <span className="flex-1 bg-[#4ade80]" title="Moderate (25-35 dBZ)" />
                <span className="flex-1 bg-[#facc15]" title="Heavy (35-45 dBZ)" />
                <span className="flex-1 bg-[#f97316]" title="Intense (45-55 dBZ)" />
                <span className="flex-1 bg-[#ef4444]" title="Severe Hail (55-65 dBZ)" />
                <span className="flex-1 bg-[#d946ef]" title="Violent/Tornadic (> 65 dBZ)" />
              </div>
              <div className="flex justify-between text-[8px] font-mono text-slate-400 px-0.5">
                <span>15 dBZ (Rain)</span>
                <span>35 dBZ (Convective)</span>
                <span>50 dBZ (Severe)</span>
                <span>65+ dBZ (Hail/Tornado)</span>
              </div>
            </div>
          )}

          {channelMode === 'vil' && (
            <div className="h-2.5 rounded-full overflow-hidden flex bg-gradient-to-r from-emerald-500 via-sky-400 to-red-500" />
          )}

          {channelMode === 'tir' && (
            <div className="h-2.5 rounded-full overflow-hidden flex bg-gradient-to-r from-slate-200 via-sky-400 via-red-500 to-purple-600" />
          )}

          {channelMode === 'flash' && (
            <div className="h-2.5 rounded-full overflow-hidden flex bg-gradient-to-r from-transparent via-amber-400 via-orange-500 to-white" />
          )}
        </div>
      </div>
    </div>
  );
};
