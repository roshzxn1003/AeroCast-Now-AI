import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Wind,
  Plane,
  Zap,
  Building2,
  Wheat,
  Waves,
  FileText,
  Printer,
  Copy,
  Check,
  Download,
  Search,
  Crosshair,
  RefreshCw,
  X,
  Radio,
  Clock,
  Compass,
} from 'lucide-react';
import { StateConvectiveReport, StateDistrictEntry } from '../types/nowcast';
import { fetchStateConvectiveReport } from '../services/api';
import { useNowcastStore } from '../store/nowcastStore';
import { OutputDataSourceSwitcher } from './OutputDataSourceSwitcher';

interface TamilNaduReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  stateSlug?: string;
  onFlyToDistrict?: (district: StateDistrictEntry) => void;
}

export const TamilNaduReportModal: React.FC<TamilNaduReportModalProps> = ({
  isOpen,
  onClose,
  stateSlug = 'tamil-nadu',
  onFlyToDistrict,
}) => {
  const [data, setData] = useState<StateConvectiveReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters & State
  const outputDataSource = useNowcastStore((s) => s.outputDataSource);
  const setOutputDataSource = useNowcastStore((s) => s.setOutputDataSource);
  const [selectedLang, setSelectedLang] = useState<'en' | 'ta' | 'hi'>('en');
  const [searchQuery, setSearchQuery] = useState('');
  const [threatFilter, setThreatFilter] = useState<'ALL' | 'EXTREME' | 'SEVERE' | 'MODERATE' | 'STABLE'>('ALL');
  const [copied, setCopied] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchStateConvectiveReport(stateSlug);
      if (!res) throw new Error('Failed to retrieve state convective intelligence data');
      setData(res);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.message || 'Error loading report');
    } finally {
      setLoading(false);
    }
  }, [stateSlug]);

  useEffect(() => {
    if (isOpen) {
      loadReport();
    }
  }, [isOpen, loadReport]);

  // Keyboard navigation (ESC to close)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Filtered districts
  const filteredDistricts = useMemo(() => {
    if (!data?.districts) return [];
    return data.districts.filter((d) => {
      const matchesSearch =
        d.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        d.id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesThreat =
        threatFilter === 'ALL'
          ? true
          : threatFilter === 'STABLE'
            ? d.threat_level === 'STABLE' || d.threat_level === 'LOW'
            : d.threat_level === threatFilter;
      return matchesSearch && matchesThreat;
    });
  }, [data, searchQuery, threatFilter]);

  // Copy bulletin text to clipboard
  const handleCopyBulletin = useCallback(() => {
    if (!data) return;
    const advisoryText = data.advisory[selectedLang] || data.advisory.en;
    const text = `================================================================================
AEROCAST-NOW AI PRO: STATE CONVECTIVE INTELLIGENCE REPORT
STATE: ${data.state.toUpperCase()} (38 DISTRICTS)
TIMESTAMP: ${new Date(data.timestamp).toUTCString()}
THREAT LEVEL: ${data.summary.highest_threat} | PEAK REFLECTIVITY: ${data.summary.peak_reflectivity_dbz} dBZ
MAX SOUNDING CAPE: ${data.summary.max_cape_j_kg} J/kg | 30M LIGHTNING: ${data.summary.active_lightning_strikes}
================================================================================

OFFICIAL ADVISORY [${selectedLang.toUpperCase()}]:
${advisoryText}

CRITICAL SECTOR IMPACTS:
- Power Grid: ${data.sector_impacts.power_grid.authority} -> ${data.sector_impacts.power_grid.risk_level} (${data.sector_impacts.power_grid.trip_probability_pct}% trip risk)
- Agriculture: ${data.sector_impacts.agriculture.zone} -> ${data.sector_impacts.agriculture.risk_level}
- Marine & Ports: ${data.sector_impacts.marine_and_ports.risk_level} (${data.sector_impacts.marine_and_ports.description})

CAP BULLETIN IDENTIFIER: ${data.cap_bulletin.identifier}
ISSUED BY: ${data.cap_bulletin.sender}
================================================================================`;

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  }, [data, selectedLang]);

  // Export JSON payload
  const handleDownloadJSON = useCallback(() => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aerocast-${stateSlug}-report-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [data, stateSlug]);

  // Print report
  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 md:p-6 bg-black/80 backdrop-blur-md animate-fadeIn">
      {/* Global Print Styling */}
      <style>{`
        @media print {
          body * {
            visibility: hidden !important;
          }
          #tn-printable-hub, #tn-printable-hub * {
            visibility: visible !important;
          }
          #tn-printable-hub {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            background: #ffffff !important;
            color: #000000 !important;
            box-shadow: none !important;
            border: none !important;
            overflow: visible !important;
          }
          .no-print {
            display: none !important;
          }
          .print-dark-text {
            color: #111827 !important;
          }
          .print-border {
            border-color: #cbd5e1 !important;
          }
        }
      `}</style>

      {/* Main Container */}
      <div
        id="tn-printable-hub"
        className="relative w-full max-w-6xl max-h-[94vh] flex flex-col rounded-2xl bg-[#0b0f14]/95 border border-cyan-500/35 shadow-[0_0_60px_rgba(6,182,212,0.18)] overflow-hidden text-slate-100"
      >
        {/* Header Bar */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-cyan-950/80 bg-gradient-to-r from-slate-900 via-slate-900/90 to-cyan-950/40 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-950/80 border border-cyan-500/50 flex items-center justify-center text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.3)]">
              <Radio className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono font-bold tracking-widest text-cyan-400 uppercase bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30">
                  AEROCAST-NOW AI PRO · METEOROLOGICAL INTELLIGENCE
                </span>
                {data && (
                  <span
                    className="px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase border"
                    style={{
                      background: `${data.summary.highest_threat_color}22`,
                      color: data.summary.highest_threat_color,
                      borderColor: `${data.summary.highest_threat_color}66`,
                    }}
                  >
                    ● STATE STATUS: {data.summary.highest_threat}
                  </span>
                )}
              </div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2 mt-0.5">
                <span>Tamil Nadu Convective Intelligence Hub</span>
                <span className="text-xs font-mono font-normal text-slate-400">
                  (38 Districts Grid)
                </span>
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 no-print">
            <button
              onClick={loadReport}
              disabled={loading}
              title="Refresh live telemetry"
              className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 text-slate-300 hover:text-cyan-400 hover:border-cyan-500/40 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
            </button>
            <button
              onClick={handlePrint}
              title="Print official report / Export to PDF"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/90 border border-slate-700 text-slate-200 hover:text-white hover:border-slate-500 transition-colors text-xs font-medium"
            >
              <Printer className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden sm:inline">Print / PDF</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
              title="Close report (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Scrollable Content Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 scrollbar-thin scrollbar-thumb-slate-700">
          {loading && !data && (
            <div className="py-24 flex flex-col items-center justify-center space-y-3">
              <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin" />
              <div className="text-sm font-mono text-cyan-300">
                Aggregating Doppler Radar, CAPE Soundings & 38 Tamil Nadu District Footprints…
              </div>
            </div>
          )}

          {error && !data && (
            <div className="p-6 rounded-xl bg-red-950/40 border border-red-500/50 text-red-200 flex items-center justify-between">
              <div>
                <div className="font-bold flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  Telemetry Acquisition Failed
                </div>
                <div className="text-xs mt-1 text-red-300">{error}</div>
              </div>
              <button
                onClick={loadReport}
                className="px-4 py-1.5 rounded-lg bg-red-900/60 border border-red-400/50 text-white text-xs font-semibold hover:bg-red-800"
              >
                Retry
              </button>
            </div>
          )}

          {data && (
            <>
              {/* Telemetry KPI Strip */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md">
                  <div className="flex items-center justify-between text-slate-400 text-[11px] font-mono">
                    <span>COVERAGE</span>
                    <Compass className="w-3.5 h-3.5 text-cyan-400" />
                  </div>
                  <div className="mt-1 text-2xl font-bold font-mono text-white">
                    {data.summary.districts_monitored}{' '}
                    <span className="text-xs font-normal text-slate-400">/ 38</span>
                  </div>
                  <div className="text-[10px] text-emerald-400 font-mono mt-0.5">
                    ● 100% Districts Synced
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md">
                  <div className="flex items-center justify-between text-slate-400 text-[11px] font-mono">
                    <span>ACTIVE WARNINGS</span>
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                  </div>
                  <div className="mt-1 text-2xl font-bold font-mono text-amber-400">
                    {data.summary.extreme_count + data.summary.severe_count + data.summary.moderate_count}
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    {data.summary.extreme_count} Ext · {data.summary.severe_count} Sev · {data.summary.moderate_count} Mod
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md">
                  <div className="flex items-center justify-between text-slate-400 text-[11px] font-mono">
                    <span>PEAK REFLECTIVITY</span>
                    <Radio className="w-3.5 h-3.5 text-red-400" />
                  </div>
                  <div className="mt-1 text-2xl font-bold font-mono text-cyan-300">
                    {data.summary.peak_reflectivity_dbz}{' '}
                    <span className="text-xs font-normal text-slate-400">dBZ</span>
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    DWR Doppler S-Band
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md">
                  <div className="flex items-center justify-between text-slate-400 text-[11px] font-mono">
                    <span>MAX SOUNDING CAPE</span>
                    <Zap className="w-3.5 h-3.5 text-amber-400" />
                  </div>
                  <div className="mt-1 text-2xl font-bold font-mono text-amber-300">
                    {Math.round(data.summary.max_cape_j_kg)}{' '}
                    <span className="text-xs font-normal text-slate-400">J/kg</span>
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    Atmospheric Instability
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md">
                  <div className="flex items-center justify-between text-slate-400 text-[11px] font-mono">
                    <span>LIGHTNING STRIKES</span>
                    <Zap className="w-3.5 h-3.5 text-cyan-400" />
                  </div>
                  <div className="mt-1 text-2xl font-bold font-mono text-cyan-400">
                    {data.summary.active_lightning_strikes}
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    TN Bounding Box (30m)
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md">
                  <div className="flex items-center justify-between text-slate-400 text-[11px] font-mono">
                    <span>RADAR STATION</span>
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                  </div>
                  <div className="mt-1 text-sm font-bold text-white truncate" title={data.summary.nearest_radar_station}>
                    {data.summary.nearest_radar_station.split(' ')[0]} DWR
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                    Refreshed {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>

              {/* Official Disaster Advisory & Bulletin */}
              <div className="p-5 rounded-xl bg-slate-900/90 border border-cyan-500/30 shadow-xl space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-cyan-400 ring-2 ring-cyan-400/30" />
                    <h3 className="font-bold text-base text-white flex items-center gap-2 font-mono">
                      <span>OFFICIAL DISASTER MANAGEMENT ADVISORY</span>
                      <span className="text-[10px] font-normal text-slate-400 px-2 py-0.5 rounded bg-slate-800 border border-slate-700">
                        IMD / NDMA CAP v1.2
                      </span>
                    </h3>
                  </div>

                  {/* Language Selector & Actions */}
                  <div className="flex items-center gap-2">
                    <div className="flex rounded-lg bg-slate-800 p-0.5 border border-slate-700/80 text-xs font-mono">
                      <button
                        onClick={() => setSelectedLang('en')}
                        className={`px-3 py-1 rounded-md transition-colors ${
                          selectedLang === 'en'
                            ? 'bg-cyan-500 text-slate-950 font-bold'
                            : 'text-slate-300 hover:text-white'
                        }`}
                      >
                        English
                      </button>
                      <button
                        onClick={() => setSelectedLang('ta')}
                        className={`px-3 py-1 rounded-md transition-colors ${
                          selectedLang === 'ta'
                            ? 'bg-cyan-500 text-slate-950 font-bold'
                            : 'text-slate-300 hover:text-white'
                        }`}
                      >
                        தமிழ் (Tamil)
                      </button>
                      <button
                        onClick={() => setSelectedLang('hi')}
                        className={`px-3 py-1 rounded-md transition-colors ${
                          selectedLang === 'hi'
                            ? 'bg-cyan-500 text-slate-950 font-bold'
                            : 'text-slate-300 hover:text-white'
                        }`}
                      >
                        हिंदी (Hindi)
                      </button>
                    </div>

                    <button
                      onClick={handleCopyBulletin}
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors"
                      title="Copy formatted bulletin text"
                    >
                      {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Localized Text */}
                <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/80 leading-relaxed text-sm text-slate-200">
                  {data.advisory[selectedLang] || data.advisory.en}
                </div>

                {/* CAP Bulletin Footnote */}
                <div className="flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 pt-1">
                  <span>CAP ID: {data.cap_bulletin.identifier}</span>
                  <span>DISPATCH: {data.cap_bulletin.sender}</span>
                  <span>CATEGORY: {data.cap_bulletin.category} · {data.cap_bulletin.urgency}</span>
                </div>
              </div>

              {/* Sector Critical Impact Grid */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-sm tracking-wider uppercase font-mono text-cyan-400 flex items-center gap-2">
                    <Building2 className="w-4 h-4" />
                    <span>State Strategic Sector Vulnerability Matrix</span>
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">
                    Real-time cross-industry risk projection
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                  {/* Aviation Hubs */}
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/40 transition-colors flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-mono font-bold text-cyan-400 flex items-center gap-1.5">
                          <Plane className="w-3.5 h-3.5" />
                          <span>AVIATION SECTOR</span>
                        </div>
                        <span className="text-[10px] font-mono text-slate-400">4 INTL HUBS</span>
                      </div>
                      <div className="mt-2.5 space-y-2">
                        {data.sector_impacts.aviation.map((hub) => (
                          <div key={hub.iata} className="flex items-center justify-between text-xs pb-1 border-b border-slate-800/60 last:border-0">
                            <div>
                              <span className="font-mono font-bold text-white mr-1.5">{hub.iata}</span>
                              <span className="text-slate-400 text-[11px]">{hub.airport.split(' ')[0]}</span>
                            </div>
                            <span
                              className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold"
                              style={{ color: hub.color, background: `${hub.color}18` }}
                            >
                              {hub.status.replace('_', ' ')}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="mt-3 text-[10px] text-slate-400 leading-tight">
                      Low-level wind shear and microburst monitoring active on MAA, CJB, IXM, TRZ approaches.
                    </div>
                  </div>

                  {/* Power Grid */}
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/40 transition-colors flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-mono font-bold text-amber-400 flex items-center gap-1.5">
                          <Zap className="w-3.5 h-3.5" />
                          <span>TANGEDCO POWER GRID</span>
                        </div>
                        <span
                          className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold"
                          style={{
                            color: data.sector_impacts.power_grid.risk_color,
                            background: `${data.sector_impacts.power_grid.risk_color}18`,
                          }}
                        >
                          {data.sector_impacts.power_grid.risk_level}
                        </span>
                      </div>
                      <div className="mt-2 text-2xl font-bold font-mono text-white">
                        {data.sector_impacts.power_grid.trip_probability_pct}%{' '}
                        <span className="text-xs font-normal text-slate-400">Trip Probability</span>
                      </div>
                      <p className="mt-2 text-xs text-slate-300 leading-relaxed">
                        {data.sector_impacts.power_grid.description}
                      </p>
                    </div>
                    <div className="mt-3 text-[10px] text-slate-400 font-mono">
                      Substation lightning surge arrestor duty: Elevated
                    </div>
                  </div>

                  {/* Cauvery Delta Agriculture */}
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/40 transition-colors flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-mono font-bold text-emerald-400 flex items-center gap-1.5">
                          <Wheat className="w-3.5 h-3.5" />
                          <span>CAUVERY DELTA AGRI</span>
                        </div>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-500/30">
                          {data.sector_impacts.agriculture.risk_level}
                        </span>
                      </div>
                      <div className="mt-1 text-xs font-semibold text-slate-200">
                        {data.sector_impacts.agriculture.zone}
                      </div>
                      <p className="mt-2 text-xs text-slate-300 leading-relaxed">
                        {data.sector_impacts.agriculture.description}
                      </p>
                    </div>
                    <div className="mt-3 text-[10px] text-slate-400 font-mono">
                      Paddy lodging & squall gust alert
                    </div>
                  </div>

                  {/* Marine & Coastal Ports */}
                  <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/40 transition-colors flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between">
                        <div className="text-xs font-mono font-bold text-sky-400 flex items-center gap-1.5">
                          <Waves className="w-3.5 h-3.5" />
                          <span>COASTAL & MARITIME</span>
                        </div>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-sky-950/60 text-sky-300 border border-sky-500/30">
                          {data.sector_impacts.marine_and_ports.risk_level}
                        </span>
                      </div>
                      <div className="mt-1 text-xs font-semibold text-slate-200">
                        {data.sector_impacts.marine_and_ports.coastal_stretch}
                      </div>
                      <p className="mt-2 text-xs text-slate-300 leading-relaxed">
                        {data.sector_impacts.marine_and_ports.description}
                      </p>
                    </div>
                    <div className="mt-3 text-[10px] text-slate-400 font-mono">
                      Chennai, Ennore & Tuticorin Port Operations
                    </div>
                  </div>
                </div>
              </div>

              {/* 38-District Convective Hazard Table */}
              <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className="font-bold text-base text-white font-mono flex items-center gap-2">
                      <span>TAMIL NADU 38-DISTRICT CONVECTIVE TELEMETRY GRID</span>
                      <span className="text-xs font-normal text-cyan-400 px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/30">
                        {filteredDistricts.length} Listed
                      </span>
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Real-time Doppler radar reflectivity, thermodynamic CAPE sounding, and storm ETA per administrative district.
                    </p>
                  </div>

                  {/* Search and Filters */}
                  <div className="flex flex-wrap items-center gap-2 no-print">
                    <OutputDataSourceSwitcher
                      value={outputDataSource}
                      onChange={setOutputDataSource}
                      size="xs"
                      compact={true}
                    />

                    <div className="relative">
                      <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                      <input
                        type="text"
                        placeholder="Search district..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-8 pr-3 py-1.5 text-xs rounded-lg bg-slate-950 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors w-36 sm:w-44"
                      />
                    </div>

                    <div className="flex rounded-lg bg-slate-950 p-0.5 border border-slate-700 text-[11px] font-mono">
                      {(['ALL', 'EXTREME', 'SEVERE', 'MODERATE', 'STABLE'] as const).map((filter) => (
                        <button
                          key={filter}
                          onClick={() => setThreatFilter(filter)}
                          className={`px-2 py-1 rounded transition-colors ${
                            threatFilter === filter
                              ? 'bg-cyan-500 text-slate-950 font-bold'
                              : 'text-slate-400 hover:text-white'
                          }`}
                        >
                          {filter}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Table */}
                <div className="overflow-x-auto rounded-xl border border-slate-800">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider text-[10px] border-b border-slate-800">
                      <tr>
                        <th className="py-2.5 px-3">District</th>
                        <th className={`py-2.5 px-3 transition-colors ${outputDataSource === 'model' ? 'text-purple-300 font-bold bg-purple-950/30' : ''}`}>
                          <div className="flex items-center gap-1">
                            <span>Status</span>
                            {outputDataSource === 'model' && <span className="text-[9px] px-1 rounded bg-purple-500/30 text-purple-200">MODEL</span>}
                          </div>
                        </th>
                        <th className={`py-2.5 px-3 transition-colors ${outputDataSource === 'live' ? 'text-emerald-300 font-bold bg-emerald-950/30' : ''}`}>
                          <div className="flex items-center gap-1">
                            <span>Peak dBZ</span>
                            {outputDataSource === 'live' && <span className="text-[9px] px-1 rounded bg-emerald-500/30 text-emerald-200">LIVE</span>}
                          </div>
                        </th>
                        <th className={`py-2.5 px-3 transition-colors ${outputDataSource === 'live' ? 'text-emerald-300 font-bold bg-emerald-950/30' : ''}`}>
                          <div className="flex items-center gap-1">
                            <span>CAPE (J/kg)</span>
                            {outputDataSource === 'live' && <span className="text-[9px] px-1 rounded bg-emerald-500/30 text-emerald-200">LIVE</span>}
                          </div>
                        </th>
                        <th className={`py-2.5 px-3 transition-colors ${outputDataSource === 'live' ? 'text-emerald-300 font-bold bg-emerald-950/30' : ''}`}>
                          <div className="flex items-center gap-1">
                            <span>Wind Gust</span>
                            {outputDataSource === 'live' && <span className="text-[9px] px-1 rounded bg-emerald-500/30 text-emerald-200">LIVE</span>}
                          </div>
                        </th>
                        <th className={`py-2.5 px-3 transition-colors ${outputDataSource === 'model' ? 'text-purple-300 font-bold bg-purple-950/30' : ''}`}>
                          <div className="flex items-center gap-1">
                            <span>Storm Proximity</span>
                            {outputDataSource === 'model' && <span className="text-[9px] px-1 rounded bg-purple-500/30 text-purple-200">MODEL</span>}
                          </div>
                        </th>
                        <th className="py-2.5 px-3 text-right no-print">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {filteredDistricts.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="py-8 text-center text-slate-500">
                            No districts matched filter criteria "{searchQuery}"
                          </td>
                        </tr>
                      ) : (
                        filteredDistricts.map((d) => (
                          <tr
                            key={d.id}
                            className="hover:bg-cyan-950/20 transition-colors group"
                          >
                            <td className="py-2.5 px-3 font-semibold text-white">
                              <div className="flex items-center gap-1.5">
                                <span>{d.name}</span>
                                <span className="text-[10px] text-slate-500 font-normal">
                                  [{d.lat.toFixed(2)}, {d.lon.toFixed(2)}]
                                </span>
                              </div>
                            </td>
                            <td className={`py-2.5 px-3 ${outputDataSource === 'model' ? 'bg-purple-950/15' : ''}`}>
                              <span
                                className="px-2 py-0.5 rounded text-[10px] font-bold border"
                                style={{
                                  color: d.threat_color,
                                  background: `${d.threat_color}18`,
                                  borderColor: `${d.threat_color}44`,
                                }}
                              >
                                {d.threat_level}
                              </span>
                            </td>
                            <td className={`py-2.5 px-3 ${outputDataSource === 'live' ? 'bg-emerald-950/15' : ''}`}>
                              <div className="flex items-center gap-2">
                                <span className={`font-bold ${outputDataSource === 'live' ? 'text-emerald-300' : 'text-slate-100'}`}>{d.max_reflectivity_dbz}</span>
                                <div className="w-12 h-1.5 rounded-full bg-slate-800 overflow-hidden hidden sm:block">
                                  <div
                                    className="h-full rounded-full"
                                    style={{
                                      width: `${Math.min(100, (d.max_reflectivity_dbz / 65) * 100)}%`,
                                      backgroundColor: d.threat_color,
                                    }}
                                  />
                                </div>
                              </div>
                            </td>
                            <td className={`py-2.5 px-3 text-slate-300 ${outputDataSource === 'live' ? 'bg-emerald-950/15 text-emerald-200 font-semibold' : ''}`}>
                              {Math.round(d.cape_j_kg)}
                            </td>
                            <td className={`py-2.5 px-3 text-slate-300 ${outputDataSource === 'live' ? 'bg-emerald-950/15 text-emerald-200 font-semibold' : ''}`}>
                              {d.wind_gust_kmh} km/h
                            </td>
                            <td className={`py-2.5 px-3 ${outputDataSource === 'model' ? 'bg-purple-950/15 text-purple-200 font-semibold' : ''}`}>
                              {d.distance_to_core_km != null ? (
                                <span className={outputDataSource === 'model' ? 'text-purple-200' : 'text-slate-300'}>
                                  {d.distance_to_core_km} km{' '}
                                  <span className={outputDataSource === 'model' ? 'text-purple-400 font-bold' : 'text-slate-500'}>
                                    {d.eta_minutes ? `(~${d.eta_minutes}m)` : ''}
                                  </span>
                                </span>
                              ) : (
                                <span className="text-slate-500">None nearby</span>
                              )}
                            </td>
                            <td className="py-2.5 px-3 text-right no-print">
                              <button
                                onClick={() => {
                                  onFlyToDistrict?.(d);
                                  onClose();
                                }}
                                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-cyan-600 hover:text-slate-950 text-cyan-400 text-[11px] font-semibold transition-colors flex items-center gap-1 ml-auto"
                                title={`Fly globe directly to ${d.name}`}
                              >
                                <Crosshair className="w-3 h-3" />
                                <span>Fly To</span>
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-800/80 bg-slate-950/90 text-xs font-mono text-slate-400 shrink-0">
          <div className="flex items-center gap-2">
            <span>AEROCAST RADAR ENGINE V2.0</span>
            <span>·</span>
            <span>TAMIL NADU 38-DISTRICT TELEMETRY</span>
          </div>

          <div className="flex items-center gap-2 no-print">
            <button
              onClick={handleDownloadJSON}
              disabled={!data}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5 text-cyan-400" />
              <span>Download JSON Payload</span>
            </button>
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold transition-colors"
            >
              Close Hub
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
