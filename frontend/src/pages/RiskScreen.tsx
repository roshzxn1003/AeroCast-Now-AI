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
    <div className="w-full max-w-7xl mx-auto px-3 py-3 lg:px-6 lg:py-4 space-y-4 pb-24 lg:pb-12 animate-in fade-in duration-300">
      {/* Header */}
      <div>
        <h2 className="text-base lg:text-lg font-extrabold text-slate-100 flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-red-400" />
          Multi-Sector Impact & Disaster Advisories
        </h2>
        <p className="text-xs text-slate-400">
          Tailored Convective Vulnerability Assessments for Critical Infrastructure & Public Safety
        </p>
      </div>

      {/* 4 Sector Cards (2x2 grid on desktop) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sectors.map((sec) => {
          const Icon = sec.icon;
          const isExpanded = expandedSector === sec.id;

          return (
            <div
              key={sec.id}
              className="bg-[#161b22] border border-white/10 rounded-xl overflow-hidden transition-all shadow-lg flex flex-col justify-between"
            >
              <button
                onClick={() => setExpandedSector(isExpanded ? null : sec.id)}
                className="w-full p-3.5 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-white/5 text-slate-200 shrink-0">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="font-extrabold text-xs lg:text-sm text-slate-100">
                      {sec.title}
                    </div>
                    <span
                      className={`text-[9px] font-black uppercase px-2 py-0.5 rounded border mt-1 inline-block ${sec.statusColor}`}
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

              {/* Collapsible / Expanded details */}
              {isExpanded && (
                <div className="px-3.5 pb-3.5 pt-1 border-t border-white/5 space-y-3 animate-in fade-in duration-200">
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    {sec.metrics.map((m, i) => (
                      <div key={i} className="bg-black/30 p-2 rounded-lg border border-white/5">
                        <div className="text-[10px] text-slate-400 leading-tight">{m.label}</div>
                        <div className="font-extrabold text-slate-200 mt-1">
                          {m.val}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="bg-white/5 p-2.5 rounded-lg border border-white/5 text-xs text-slate-300">
                    <div className="font-bold text-amber-300 text-[10px] uppercase mb-0.5">
                      Operational Protocol
                    </div>
                    <p className="leading-relaxed text-slate-300 text-[11px] lg:text-xs">
                      {sec.action}
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* CAP Export & Sharing */}
      <div className="bg-[#161b22] border border-white/10 rounded-xl p-4 space-y-3 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertOctagon className="w-5 h-5 text-red-400" />
            <div>
              <h3 className="font-bold text-xs lg:text-sm text-slate-200">
                NDMA / IMD CAP v1.2 Standard Alert Payload
              </h3>
              <p className="text-[11px] text-slate-400">
                Conforming to OASIS Common Alerting Protocol v1.2 standards
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyCap}
              className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs flex items-center gap-1.5 px-3 font-medium transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
            <button
              onClick={handleDownloadCap}
              className="p-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-white text-xs flex items-center gap-1.5 px-3 font-bold shadow transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download JSON</span>
            </button>
          </div>
        </div>

        <div className="bg-black/40 rounded-xl p-3 font-mono text-xs text-slate-300 space-y-1.5 border border-white/5">
          <div><span className="text-slate-500">ID:</span> {cap.identifier}</div>
          <div><span className="text-slate-500">Sender:</span> {cap.sender}</div>
          <div><span className="text-slate-500">Event:</span> {cap.info.event}</div>
          <div>
            <span className="text-slate-500">Severity:</span> {cap.info.severity} •{' '}
            <span className="text-slate-500">Urgency:</span> {cap.info.urgency} •{' '}
            <span className="text-slate-500">Certainty:</span> {cap.info.certainty}
          </div>
          <div><span className="text-slate-500">Area:</span> {cap.info.area.areaDesc}</div>
        </div>
      </div>
    </div>
  );
};
