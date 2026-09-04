import React, { useState } from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import {
  ShieldAlert,
  Plane,
  Zap,
  Wheat,
  Building2,
  AlertOctagon,
  Download,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export const RiskScreen: React.FC = () => {
  const { nowcastData } = useNowcastStore();
  const [copied, setCopied] = useState(false);
  const [expandedSector, setExpandedSector] = useState<string | null>('aviation');

  if (!nowcastData) return null;

  const maxDbz = nowcastData.observation.max_dbz;
  const maxVil = nowcastData.observation.max_vil;
  const jump = nowcastData.lightning_jump;
  const cap = nowcastData.cap_bulletin;

  const rainRateMmHr = Math.round(maxDbz * 1.2 * 10) / 10;
  const microburstProb = maxDbz >= 50 ? 85 : maxDbz >= 40 ? 45 : 15;
  const gridStrikeProb = jump.jump_detected ? 88 : 35;
  const cropHailDamage = maxVil >= 30 ? 75 : 20;

  const sectors = [
    {
      id: 'aviation',
      title: 'Aviation & Aerodrome Operations',
      icon: Plane,
      status: maxDbz >= 50 ? 'CRITICAL - DELAY DEPARTURES' : 'MODERATE CAUTION',
      statusColor: maxDbz >= 50 ? 'bg-red-500/20 text-red-300 border-red-500/30' : 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      metrics: [
        { label: 'Low-Level Wind Shear (LLWS)', val: maxDbz >= 50 ? 'HIGH SEVERITY' : 'MODERATE' },
        { label: 'Microburst Probability', val: `${microburstProb}%` },
        { label: 'Runway Convective Incursion', val: '~18 min' },
      ],
      action: 'Advise Air Traffic Control (ATC) to hold departures within radial 50km cone. Re-route arrival vectors away from ENE azimuth.',
    },
    {
      id: 'power',
      title: 'Power Grid & 400kV Substations',
      icon: Zap,
      status: jump.jump_detected ? 'HIGH SURGE RISK' : 'NORMAL MONITORING',
      statusColor: jump.jump_detected ? 'bg-red-500/20 text-red-300 border-red-500/30' : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
      metrics: [
        { label: 'Grid Strike Probability', val: `${gridStrikeProb}%` },
        { label: 'Surge Arrester Stress', val: jump.jump_detected ? 'CRITICAL' : 'NOMINAL' },
        { label: 'Lightning Flash Density', val: `${nowcastData.observation.flash_rate_fpm} fpm` },
      ],
      action: 'Enable automated rapid auto-reclosers on high-voltage transmission lines. Isolate vulnerable rural feeder transformers in the storm path.',
    },
    {
      id: 'agri',
      title: 'Agriculture & Rural Safety',
      icon: Wheat,
      status: 'EXTREME CG STRIKE HAZARD',
      statusColor: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
      metrics: [
        { label: 'Open-Field Lightning Hazard', val: 'FATAL RISK' },
        { label: 'Hail Crop Destruction', val: `${cropHailDamage}%` },
        { label: 'Precursor Lead Time', val: `~${jump.estimated_lead_time_min} mins` },
      ],
      action: 'Broadcast immediate Damini / IMD SMS sirens to agricultural workers and rural field laborers to evacuate open paddies and avoid tall trees.',
    },
    {
      id: 'urban',
      title: 'Urban Drainage & Flood Response',
      icon: Building2,
      status: rainRateMmHr >= 60 ? 'RAPID FLOODING RISK' : 'HEAVY RUNOFF',
      statusColor: rainRateMmHr >= 60 ? 'bg-red-500/20 text-red-300 border-red-500/30' : 'bg-sky-500/20 text-sky-300 border-sky-500/30',
      metrics: [
        { label: 'Instantaneous Rain Rate', val: `${rainRateMmHr} mm/hr` },
        { label: 'Storm Water Sump Saturation', val: 'RAPID ACCUMULATION' },
        { label: 'Underpass Inundation Risk', val: 'HIGH' },
      ],
      action: 'Pre-position emergency high-capacity mobile de-watering diesel pumps at known arterial low-lying highway underpasses and metro station sumps.',
    },
  ];

  const handleCopyCap = () => {
    navigator.clipboard.writeText(JSON.stringify(cap, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadCap = () => {
    const blob = new Blob([JSON.stringify(cap, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `CAP_Alert_${cap.identifier}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-3 p-3 max-w-lg mx-auto pb-24 animate-in fade-in duration-300">
      {/* Header */}
      <div>
        <h2 className="text-base font-extrabold text-slate-100 flex items-center gap-1.5">
          <ShieldAlert className="w-5 h-5 text-red-400" />
          Multi-Sector Impact & Disaster Advisories
        </h2>
        <p className="text-[11px] text-slate-400">
          Tailored Vulnerability Assessments for Critical Infrastructure & Public Safety
        </p>
      </div>

      {/* 4 Sector Cards */}
      <div className="space-y-2.5">
        {sectors.map((sec) => {
          const Icon = sec.icon;
          const isExpanded = expandedSector === sec.id;

          return (
            <div
              key={sec.id}
              className="bg-[#161b22] border border-white/10 rounded-xl overflow-hidden transition-all"
            >
              <button
                onClick={() => setExpandedSector(isExpanded ? null : sec.id)}
                className="w-full p-3 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-white/5 text-slate-200">
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-extrabold text-xs text-slate-100">
                      {sec.title}
                    </div>
                    <span
                      className={`text-[9px] font-black uppercase px-1.5 py-0.5 rounded border mt-0.5 inline-block ${sec.statusColor}`}
                    >
                      {sec.status}
                    </span>
                  </div>
                </div>

                {isExpanded ? (
                  <ChevronUp className="w-4 h-4 text-slate-400" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                )}
              </button>

              {isExpanded && (
                <div className="px-3 pb-3 pt-1 border-t border-white/5 space-y-2.5 animate-in fade-in duration-200">
                  <div className="grid grid-cols-3 gap-1.5 text-center text-[10px]">
                    {sec.metrics.map((m, i) => (
                      <div key={i} className="bg-black/30 p-1.5 rounded-lg border border-white/5">
                        <div className="text-slate-400 leading-tight">{m.label}</div>
                        <div className="font-extrabold text-slate-200 mt-0.5">
                          {m.val}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="bg-white/5 p-2 rounded-lg border border-white/5 text-[11px] text-slate-300">
                    <div className="font-bold text-amber-300 text-[10px] uppercase mb-0.5">
                      Operational Protocol
                    </div>
                    <p className="leading-snug text-slate-300">{sec.action}</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* CAP Export & Sharing */}
      <div className="bg-[#161b22] border border-white/10 rounded-xl p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <AlertOctagon className="w-4 h-4 text-red-400" />
            <h3 className="font-bold text-xs text-slate-200">
              NDMA / IMD CAP v1.2 Standard Alert Payload
            </h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleCopyCap}
              className="p-1 rounded bg-white/5 hover:bg-white/10 text-slate-300 text-[10px] flex items-center gap-1 px-2 font-medium"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            <button
              onClick={handleDownloadCap}
              className="p-1 rounded bg-sky-500 hover:bg-sky-400 text-white text-[10px] flex items-center gap-1 px-2 font-bold"
            >
              <Download className="w-3 h-3" />
              Download JSON
            </button>
          </div>
        </div>

        <p className="text-[11px] text-slate-400">
          This payload conforms to OASIS Common Alerting Protocol v1.2 standards for integration with national emergency broadcast systems.
        </p>

        <div className="bg-black/40 rounded-lg p-2 font-mono text-[10px] text-slate-300 space-y-1">
          <div><span className="text-slate-500">ID:</span> {cap.identifier}</div>
          <div><span className="text-slate-500">Sender:</span> {cap.sender}</div>
          <div><span className="text-slate-500">Event:</span> {cap.info.event}</div>
          <div><span className="text-slate-500">Severity:</span> {cap.info.severity} • <span className="text-slate-500">Urgency:</span> {cap.info.urgency}</div>
          <div><span className="text-slate-500">Area:</span> {cap.info.area.areaDesc}</div>
        </div>
      </div>
    </div>
  );
};
