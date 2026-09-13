import React, { useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  ChevronDown,
  Clock,
  Info,
  MapPin,
  ShieldAlert,
  Zap,
} from 'lucide-react';
import { LightningGlobe } from '../components/LightningGlobe';
import { ModelReportPanel } from '../components/ModelReportPanel';
import { LightningJumpBanner } from '../components/LightningJumpBanner';
import {
  LiveDomainPanel,
  NetworkStatusPanel,
  NodeDetailPanel,
} from '../components/LiveDomainPanel';
import { useLiveStore } from '../store/liveStore';
import { useNowcastStore } from '../store/nowcastStore';
import { FLASH, SEVERITY_COLOR, SEVERITY_LEVELS } from '../design/tokens';
import { ProvenanceBadge } from '../components/ui';
import {
  assessThunderstormThreat,
  MAJOR_INDIAN_CITIES,
} from '../utils/weatherInterpreter';

/**
 * The command screen.
 *
 * One skeleton serves both audiences: a dominant globe, and a single rail
 * beside it. Public and Pro differ only in what the rail contains — never in
 * the layout itself. The previous build ran a second rail on the left in Pro
 * mode, which squeezed the globe, clipped its own panels, and printed every
 * headline figure two or three times in different places.
 *
 * The rule the layout now follows: one fact, one home.
 *   - the globe shows the single hero number (flashes) and nothing else
 *   - the rail holds every other reading, grouped under quiet dividers
 *   - the header carries identity, mode, navigation and one freshness stamp
 */
export const CommandScreen: React.FC = () => {
  const startPolling = useLiveStore((s) => s.startPolling);
  const lightning = useLiveStore((s) => s.lightning);
  const summary = useLiveStore((s) => s.summary);

  const {
    uiMode,
    nowcastData,
    hasJump,
    selectedCity,
    setSelectedCity,
    setSelectedStation,
    setActiveTab,
  } = useNowcastStore();

  useEffect(() => startPolling(), [startPolling]);

  const maxDbz = nowcastData?.observation?.max_dbz || 0;
  const activeCells = nowcastData?.observation?.storm_cells || [];
  const strikeCount30m = summary?.strike_count_30min || 0;

  const threat = assessThunderstormThreat(
    hasJump,
    activeCells.length,
    maxDbz,
    strikeCount30m,
  );

  const currentCity =
    MAJOR_INDIAN_CITIES.find((c) => c.id === selectedCity) || MAJOR_INDIAN_CITIES[0];

  return (
    <div className="flex flex-col xl:flex-row gap-3 p-3 xl:h-[calc(100dvh-3.5rem)] min-h-0">
      {/* ---------------------------------------------------------------- Stage */}
      <section className="relative w-full shrink-0 xl:flex-1 min-w-0 h-[52vh] xl:h-auto rounded-[12px] border border-[var(--color-line)] overflow-hidden bg-[var(--color-surface-void)]">
        <LightningGlobe className="absolute inset-0" />
        {summary && <HeroCount count={summary.strike_count_30min} status={lightning?.status} />}
        <GlobeLegend />
      </section>

      {/* ----------------------------------------------------------------- Rail */}
      <aside className="w-full xl:w-[400px] 2xl:w-[440px] shrink-0 flex flex-col gap-3 min-h-0 pb-20 xl:pb-0 xl:overflow-y-auto [&>*]:shrink-0">
        {uiMode === 'citizen' ? (
          <>
            <ThreatHero threat={threat} />
            <CityRadarCard
              currentCity={currentCity}
              selectedCity={selectedCity}
              onSelectCity={(id) => {
                setSelectedCity(id);
                const c = MAJOR_INDIAN_CITIES.find((item) => item.id === id);
                if (c) setSelectedStation(c.stationName);
              }}
              maxDbz={maxDbz}
              hasJump={hasJump}
            />
            <SafetyCard actions={threat.safetyActions} />
            <ExplainerCard />
          </>
        ) : (
          <>
            <RailSection label="Nowcast" />
            <LightningJumpBanner />
            <StormCellsCard cells={activeCells} onOpenTracker={() => setActiveTab('storms')} />
            <ModelReportPanel />

            <RailSection label="Observations" />
            <LiveDomainPanel />
            <NodeDetailPanel />
            <NetworkStatusPanel />
          </>
        )}
      </aside>
    </div>
  );
};

// -----------------------------------------------------------------------------
// Stage furniture
// -----------------------------------------------------------------------------

/**
 * The one figure that should be readable across a room. Deliberately carries no
 * secondary readings: rate and CAPE live in the rail, and repeating them here is
 * what made the old header, HUD and rail disagree at a glance.
 */
const HeroCount: React.FC<{ count: number; status?: string }> = ({ count, status }) => (
  <div className="absolute top-4 left-4 z-20 pointer-events-none">
    <div className="flex items-center gap-2">
      <Zap className="w-3.5 h-3.5 text-[var(--color-ink-faint)]" />
      <span className="eyebrow">Flashes · last 30 min</span>
    </div>
    <div className="flex items-baseline gap-2 mt-1">
      <span
        className="font-mono tabular font-medium leading-none"
        style={{ fontSize: 'var(--text-display)', color: FLASH.cg }}
      >
        {count.toLocaleString()}
      </span>
      {status && <ProvenanceBadge provenance={status} />}
    </div>
  </div>
);

/** Collapsed by default: a legend is reference material, not a permanent panel. */
const GlobeLegend: React.FC = () => {
  const [open, setOpen] = useState(false);

  return (
    <div className="absolute bottom-3 left-3 z-20 hidden sm:block">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-[6px] border border-[var(--color-line)] bg-[rgba(11,15,20,0.92)] text-[11px] font-mono text-[var(--color-ink-muted)] hover:text-[var(--color-ink)] transition-colors"
      >
        Legend
        <ChevronDown
          className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div
          className="mt-1.5 panel px-3 py-2.5 space-y-2 enter"
          style={{ background: 'rgba(11,15,20,0.94)' }}
        >
          <LegendRow label="Storm energy">
            <span className="flex rounded-full overflow-hidden h-2 w-16">
              {SEVERITY_LEVELS.map((level) => (
                <span key={level} className="flex-1" style={{ background: SEVERITY_COLOR[level] }} />
              ))}
            </span>
          </LegendRow>
          <LegendRow label="Ground strike">
            <span className="w-2 h-2 rounded-full" style={{ background: FLASH.cg }} />
          </LegendRow>
          <LegendRow label="In-cloud">
            <span className="w-2 h-2 rounded-full" style={{ background: FLASH.ic }} />
          </LegendRow>
          <LegendRow label="City">
            <span className="w-2 h-2 rounded-full bg-cyan-400" />
          </LegendRow>
          <p className="text-[10px] text-[var(--color-ink-faint)] pt-1 max-w-[15rem] leading-snug border-t border-[var(--color-line-faint)]">
            Column height encodes convective vigour. Drag to rotate, scroll to
            zoom, click a marker to inspect.
          </p>
        </div>
      )}
    </div>
  );
};

const LegendRow: React.FC<{ label: string; children: React.ReactNode }> = ({
  label,
  children,
}) => (
  <div className="flex items-center gap-2 text-[11px] text-[var(--color-ink-muted)]">
    <span className="w-16 shrink-0 flex items-center">{children}</span>
    <span>{label}</span>
  </div>
);

// -----------------------------------------------------------------------------
// Rail furniture
// -----------------------------------------------------------------------------

/**
 * A quiet grouping divider. The old build used saturated, icon-laden headers
 * plus literal "LEFT RAIL" / "RIGHT RAIL" captions, which competed with the
 * data for attention and leaked internal layout vocabulary to the user.
 */
const RailSection: React.FC<{ label: string }> = ({ label }) => (
  <div className="flex items-center gap-2.5 pt-1 first:pt-0">
    <span className="eyebrow whitespace-nowrap">{label}</span>
    <span className="h-px flex-1 bg-[var(--color-line)]" />
  </div>
);

// -----------------------------------------------------------------------------
// Public-mode cards
// -----------------------------------------------------------------------------

type Threat = ReturnType<typeof assessThunderstormThreat>;

const ThreatHero: React.FC<{ threat: Threat }> = ({ threat }) => (
  <section
    className="rounded-[10px] border p-4"
    style={{ backgroundColor: threat.bgRgba, borderColor: threat.colorHex }}
  >
    <div className="flex items-center justify-between gap-2">
      <span
        className="text-[11px] font-semibold px-2 py-0.5 rounded-full text-white"
        style={{ backgroundColor: threat.colorHex }}
      >
        {threat.badgeText}
      </span>
      <span className="text-[11px] text-[var(--color-ink-muted)] font-mono flex items-center gap-1">
        <Clock className="w-3 h-3" />
        Live 0–2 h nowcast
      </span>
    </div>
    <h2 className="text-[17px] font-semibold text-white mt-2.5 leading-snug">
      {threat.headline}
    </h2>
    <p className="text-[13px] text-[var(--color-ink)] mt-1 leading-relaxed opacity-90">
      {threat.subhead}
    </p>
  </section>
);

const CityRadarCard: React.FC<{
  currentCity: (typeof MAJOR_INDIAN_CITIES)[number];
  selectedCity: string;
  onSelectCity: (id: string) => void;
  maxDbz: number;
  hasJump: boolean;
}> = ({ currentCity, selectedCity, onSelectCity, maxDbz, hasJump }) => (
  <section className="panel">
    <header className="panel-header">
      <h2 className="panel-title flex items-center gap-1.5">
        <MapPin className="w-3.5 h-3.5" />
        Local radar
      </h2>
      <select
        value={selectedCity}
        onChange={(e) => onSelectCity(e.target.value)}
        aria-label="Select city"
        className="bg-[var(--color-surface-raised)] text-[var(--color-ink)] text-[12px] rounded-[6px] px-2 py-1 border border-[var(--color-line)] cursor-pointer"
      >
        {MAJOR_INDIAN_CITIES.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </header>

    <div className="p-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[17px] font-semibold truncate">{currentCity.name}</div>
          <div className="text-[12px] text-[var(--color-ink-faint)]">{currentCity.state}</div>
        </div>
        <div className="text-right shrink-0">
          <div
            className="text-[12px] font-medium flex items-center gap-1 justify-end"
            style={{ color: SEVERITY_COLOR.MARGINAL }}
          >
            <CheckCircle2 className="w-3.5 h-3.5" /> Radar online
          </div>
          <div className="text-[11px] font-mono text-[var(--color-ink-faint)]">250 km range</div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-[var(--color-line-faint)] grid grid-cols-2 gap-2.5">
        <Readout
          label="Rain intensity"
          value={maxDbz >= 40 ? 'Heavy' : maxDbz >= 25 ? 'Moderate' : 'Light'}
        />
        <Readout
          label="Lightning danger"
          value={hasJump ? 'High alert' : 'Normal'}
          tone={hasJump ? SEVERITY_COLOR.SEVERE : undefined}
        />
      </div>
    </div>
  </section>
);

const Readout: React.FC<{ label: string; value: string; tone?: string }> = ({
  label,
  value,
  tone,
}) => (
  <div className="rounded-[6px] bg-[var(--color-surface-raised)] border border-[var(--color-line-faint)] p-2.5">
    <div className="eyebrow">{label}</div>
    <div
      className="text-[14px] font-medium mt-1"
      style={{ color: tone ?? 'var(--color-ink)' }}
    >
      {value}
    </div>
  </div>
);

const SafetyCard: React.FC<{ actions: string[] }> = ({ actions }) => (
  <section className="panel">
    <header className="panel-header">
      <h2 className="panel-title flex items-center gap-1.5">
        <ShieldAlert className="w-3.5 h-3.5" />
        What to do now
      </h2>
    </header>
    <ul className="p-3.5 space-y-2">
      {actions.map((action, i) => (
        <li
          key={i}
          className="flex items-start gap-2 text-[13px] text-[var(--color-ink-muted)] leading-relaxed"
        >
          <span
            className="w-1 h-1 rounded-full mt-2 shrink-0"
            style={{ background: 'var(--color-accent)' }}
          />
          <span>{action}</span>
        </li>
      ))}
    </ul>
  </section>
);

const ExplainerCard: React.FC = () => (
  <section className="panel">
    <div className="p-3.5">
      <h2 className="text-[13px] font-medium flex items-center gap-1.5 mb-1.5">
        <Info className="w-3.5 h-3.5 text-[var(--color-ink-faint)]" />
        How AeroCast works
      </h2>
      <p className="text-[12px] text-[var(--color-ink-muted)] leading-relaxed">
        AeroCast fuses IMD Doppler radar, ISRO INSAT-3D satellite imagery and
        ground lightning sensors. A ResAtt-ConvLSTM2D network predicts
        thunderstorm movement 15 to 120 minutes ahead.
      </p>
    </div>
  </section>
);

// -----------------------------------------------------------------------------
// Pro-mode cards
// -----------------------------------------------------------------------------

const StormCellsCard: React.FC<{
  cells: NonNullable<ReturnType<typeof useNowcastStore.getState>['nowcastData']>['observation']['storm_cells'];
  onOpenTracker: () => void;
}> = ({ cells, onOpenTracker }) => (
  <section className="panel">
    <header className="panel-header">
      <h2 className="panel-title flex items-center gap-1.5">
        <Activity className="w-3.5 h-3.5" />
        Storm cells · {cells.length} active
      </h2>
      <button
        onClick={onOpenTracker}
        className="text-[12px] text-[var(--color-accent)] hover:underline"
      >
        Tracker →
      </button>
    </header>

    <div className="p-3.5">
      {cells.length === 0 ? (
        <p className="text-[12px] text-[var(--color-ink-faint)]">
          No cells meet the 40 dBZ / 24 km² tracking threshold.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {cells.slice(0, 3).map((cell) => (
            <li
              key={cell.cell_id}
              className="rounded-[6px] border border-[var(--color-line-faint)] bg-[var(--color-surface-raised)] p-2.5 flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: cell.color }}
                  />
                  <span className="text-[13px] font-medium">{cell.cell_id}</span>
                  <span className="text-[11px] font-mono text-[var(--color-ink-faint)]">
                    {cell.area_km2} km²
                  </span>
                </div>
                <div className="text-[11px] text-[var(--color-ink-faint)] mt-0.5 truncate">
                  {cell.severity}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-[13px] font-mono tabular" style={{ color: SEVERITY_COLOR.SEVERE }}>
                  {cell.max_dbz} dBZ
                </div>
                <div className="text-[11px] text-[var(--color-ink-faint)]">
                  hail {cell.hail_risk_pct}%
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  </section>
);
