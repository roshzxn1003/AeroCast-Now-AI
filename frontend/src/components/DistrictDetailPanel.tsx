/**
 * Live detail readout for a selected district.
 *
 * Three bands, in the order a forecaster reads them: what is happening at the
 * surface now, what the sounding says about whether it will develop, and what
 * the observing network around the district can see. Every figure carries its
 * provenance, so a measured temperature and a derived shear proxy are never
 * mistaken for each other.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { X, Crosshair, Radar, Zap, RefreshCw } from 'lucide-react';
import { District, haversineKm } from '../services/districts';
import {
  DistrictOutlook,
  DistrictWeather,
  compass,
  fetchDistrictOutlook,
  fetchOneDistrictWeather,
  peekDistrictOutlook,
  peekDistrictWeather,
  providerStatus,
} from '../services/districtWeather';
import { DEFAULT_STATIONS, fetchDistrictNowcast } from '../services/api';
import { useLiveStore } from '../store/liveStore';
import { ConvectiveNode, RadarStation, Strike, DistrictNowcastResponse } from '../types/nowcast';
import { Badge, Loading, SeverityTag, Stat } from './ui';
import { severityColor } from '../design/tokens';

interface DistrictDetailPanelProps {
  district: District;
  onClose: () => void;
  /** Re-frame the camera on this district. */
  onLocate: () => void;
  className?: string;
}

/** Radius around the district centroid counted as "nearby" for strikes. */
const STRIKE_RADIUS_KM = 120;

const fmt = (v: number | null, digits = 0, dash = '--'): string =>
  v == null ? dash : v.toFixed(digits);

export const DistrictDetailPanel: React.FC<DistrictDetailPanelProps> = ({
  district,
  onClose,
  onLocate,
  className,
}) => {
  const [weather, setWeather] = useState<DistrictWeather | null>(() =>
    peekDistrictWeather(district.id),
  );
  const [nowcast, setNowcast] = useState<DistrictNowcastResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  const [outlook, setOutlook] = useState<DistrictOutlook | null>(() =>
    peekDistrictOutlook(district.id),
  );

  const lightning = useLiveStore((s) => s.lightning);
  const convective = useLiveStore((s) => s.convective);

  // The 120-hour outlook is fetched separately from the live reading: it is a
  // different horizon on a much slower cache, and a failure in one must not
  // blank the other.
  useEffect(() => {
    setOutlook(peekDistrictOutlook(district.id));
    const controller = new AbortController();
    fetchDistrictOutlook(district, controller.signal)
      .then((o) => !controller.signal.aborted && o && setOutlook(o))
      .catch(() => undefined);
    return () => controller.abort();
  }, [district, reloadToken]);

  useEffect(() => {
    const cached = peekDistrictWeather(district.id);
    setWeather(cached);
    setFailed(false);

    const controller = new AbortController();
    setLoading(true);

    fetchOneDistrictWeather(district, controller.signal)
      .then((w) => {
        if (controller.signal.aborted) return;
        setWeather(w);
        setFailed(w == null);
      })
      .catch(() => !controller.signal.aborted && setFailed(true))
      .finally(() => !controller.signal.aborted && setLoading(false));

    fetchDistrictNowcast(district.name)
      .then((nc) => {
        if (!controller.signal.aborted) setNowcast(nc);
      })
      .catch(() => {});

    return () => controller.abort();
  }, [district, reloadToken]);

  const [lon, lat] = district.centroid;

  // Nearest radar in the DWR network, and whether the district falls inside
  // its scan radius — a district outside every radar's range is a genuine gap
  // in coverage and the panel should say so.
  const nearestStation = useMemo(() => {
    let best: { station: RadarStation; km: number } | null = null;
    for (const station of DEFAULT_STATIONS as RadarStation[]) {
      const km = haversineKm(lat, lon, station.lat, station.lon);
      if (!best || km < best.km) best = { station, km };
    }
    return best;
  }, [lat, lon]);

  const nearestNode = useMemo(() => {
    let best: { node: ConvectiveNode; km: number } | null = null;
    for (const node of convective?.nodes ?? []) {
      const km = haversineKm(lat, lon, node.lat, node.lon);
      if (!best || km < best.km) best = { node, km };
    }
    return best;
  }, [convective, lat, lon]);

  const nearbyStrikes = useMemo(() => {
    const strikes = (lightning?.strikes ?? []) as Strike[];
    const near = strikes.filter(
      (s) => haversineKm(lat, lon, s.lat, s.lon) <= STRIKE_RADIUS_KM,
    );
    return {
      total: near.length,
      cg: near.filter((s) => s.type === 'CG').length,
      newest: near.reduce<Strike | null>(
        (acc, s) => (!acc || s.age_s < acc.age_s ? s : acc),
        null,
      ),
    };
  }, [lightning, lat, lon]);

  const tone = weather ? severityColor(weather.severity) : undefined;

  return (
    <aside className={`district-panel ${className ?? ''}`} aria-live="polite">
      <header className="district-panel__head">
        <div className="min-w-0">
          <div className="eyebrow">District readout</div>
          <h2 className="district-panel__title">{district.name}</h2>
          <p className="district-panel__sub">{district.state}</p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onLocate}
            className="district-panel__icon"
            title="Centre the globe on this district"
            aria-label="Centre the globe on this district"
          >
            <Crosshair className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setReloadToken((t) => t + 1)}
            className="district-panel__icon"
            title="Refetch live observations"
            aria-label="Refetch live observations"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'spin' : ''}`} />
          </button>
          <button
            onClick={onClose}
            className="district-panel__icon"
            title="Close"
            aria-label="Close district readout"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {loading && !weather && <Loading label="Retrieving observations" />}

      {failed && !weather && <ObservationFailure />}

      {weather && (
        <>
          {/* -- Threat headline ------------------------------------------- */}
          <div className="district-panel__threat">
            <div className="min-w-0">
              <div className="eyebrow">Convective threat</div>
              <div className="flex items-baseline gap-2 mt-1">
                <span
                  className="font-mono tabular text-[32px] leading-none"
                  style={{ color: tone }}
                >
                  {weather.threatScore}
                </span>
                <span className="text-[11px] text-[var(--color-ink-faint)]">/ 100</span>
              </div>
            </div>
            <div className="flex flex-col items-end gap-1.5 shrink-0">
              <SeverityTag level={weather.severity} />
              {weather.thunderstorm && (
                <Badge color="var(--color-flash-cg)">TS OBSERVED</Badge>
              )}
            </div>
          </div>

          <div className="district-panel__bar" role="presentation">
            <div
              style={{
                width: `${weather.threatScore}%`,
                background: tone,
              }}
            />
          </div>

          <p className="district-panel__conditions">{weather.conditions}</p>

          {/* -- Surface --------------------------------------------------- */}
          <Section title="Surface" provenance="LIVE">
            <div className="district-grid">
              <Stat label="Temp" value={fmt(weather.temperatureC, 1)} unit="°C" size="sm" />
              <Stat label="Feels like" value={fmt(weather.apparentC, 1)} unit="°C" size="sm" />
              <Stat label="Humidity" value={fmt(weather.humidityPct)} unit="%" size="sm" />
              <Stat label="Cloud" value={fmt(weather.cloudCoverPct)} unit="%" size="sm" />
              <Stat
                label="Wind"
                value={fmt(weather.windKph)}
                unit="km/h"
                note={compass(weather.windDirDeg)}
                size="sm"
              />
              <Stat label="Gusts" value={fmt(weather.gustKph)} unit="km/h" size="sm" />
              <Stat label="Pressure" value={fmt(weather.pressureHpa)} unit="hPa" size="sm" />
              <Stat label="Precip" value={fmt(weather.precipitationMm, 1)} unit="mm" size="sm" />
            </div>
          </Section>

          {/* -- Sounding -------------------------------------------------- */}
          <Section title="Instability" provenance="LIVE-DERIVED">
            <div className="district-grid">
              <Stat
                label="CAPE"
                value={fmt(weather.capeJkg)}
                unit="J/kg"
                note={capeNote(weather.capeJkg)}
                size="sm"
              />
              <Stat
                label="CIN"
                value={fmt(weather.cinJkg)}
                unit="J/kg"
                note={cinNote(weather.cinJkg)}
                size="sm"
              />
              <Stat
                label="Lifted index"
                value={fmt(weather.liftedIndex, 1)}
                unit="°C"
                note={liNote(weather.liftedIndex)}
                size="sm"
              />
              <Stat
                label="Bulk shear"
                value={fmt(weather.shearKt)}
                unit="kt"
                note={shearNote(weather.shearKt)}
                size="sm"
              />
              <Stat
                label="Precip prob"
                value={fmt(weather.precipProbPct)}
                unit="%"
                size="sm"
              />
            </div>
            <p className="district-panel__note">
              Shear is a 10 m to 500 hPa proxy for 0–6 km bulk shear, not a
              measured sounding.
            </p>
          </Section>

          {/* -- AI Nowcast Timeline (+15m to +120m) ------------------ */}
          {nowcast && (
            <>
              {nowcast.lightning_jump_alert?.jump_detected && (
                <div className="mx-4 my-2 p-2.5 rounded-lg border border-purple-500/40 bg-purple-950/40 text-purple-200 text-xs flex items-start gap-2">
                  <Zap className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold text-purple-300">2σ Lightning Jump Surge Precursor</div>
                    <div className="text-[11px] text-purple-200/80 mt-0.5">
                      Statistically significant surge in total flash rate. {nowcast.lightning_jump_alert.lead_time_minutes > 0 ? `${nowcast.lightning_jump_alert.lead_time_minutes} min early-warning lead time` : 'Immediate high strike probability'}.
                    </div>
                  </div>
                </div>
              )}

              <Section title="AI Nowcast Timeline (ConvLSTM2D)" provenance={nowcast.observation_station?.data_provenance || "MODEL"}>
                <div className="flex gap-2 overflow-x-auto pb-1.5 scrollbar-thin">
                  {nowcast.nowcast_timeline?.map((step) => (
                    <div
                      key={step.lead_time_min}
                      className="flex-shrink-0 w-24 p-2 rounded-lg border border-[var(--color-edge)] bg-[var(--color-surface-soft)] text-center flex flex-col justify-between"
                    >
                      <div className="text-[10px] font-mono text-[var(--color-ink-faint)]">+{step.lead_time_min}m ({step.forecast_time})</div>
                      <div className="my-1">
                        <span
                          className="text-xs px-1.5 py-0.5 rounded font-bold font-mono"
                          style={{ backgroundColor: `${step.threat_color}25`, color: step.threat_color }}
                        >
                          {step.reflectivity_dbz} dBZ
                        </span>
                      </div>
                      <div className="text-[10px] text-[var(--color-ink-muted)]">
                        <div>{step.rain_intensity_mm_h} mm/h</div>
                        <div>{step.wind_gust_kmh} km/h</div>
                      </div>
                    </div>
                  ))}
                </div>

                {nowcast.current_observation?.nearest_storm_core && (
                  <div className="mt-2 p-2 rounded bg-[var(--color-surface-soft)] border border-[var(--color-edge)] text-xs flex items-center justify-between">
                    <span className="text-[var(--color-ink-muted)]">Active Core ({nowcast.current_observation.nearest_storm_core.cell_id}):</span>
                    <span className="font-mono text-orange-400 font-semibold">{nowcast.current_observation.nearest_storm_core.distance_km} km away (ETA ~{nowcast.current_observation.nearest_storm_core.eta_minutes}m)</span>
                  </div>
                )}
              </Section>

              {nowcast.advisory && (
                <Section title="Emergency Advisory (IMD CAP v1.2)" provenance="NDMA-ALIGNED">
                  <div className="text-xs text-[var(--color-ink-muted)] space-y-1.5">
                    <p className="leading-relaxed"><strong className="text-[var(--color-ink)]">English:</strong> {nowcast.advisory.en}</p>
                    <p className="leading-relaxed text-yellow-200/90"><strong className="text-[var(--color-ink)]">हिन्दी:</strong> {nowcast.advisory.hi}</p>
                  </div>
                </Section>
              )}
            </>
          )}
        </>
      )}

      {outlook && outlook.days.length > 0 && <OutlookSection outlook={outlook} />}

      {/* -- Observing network -------------------------------------------- */}
      <Section title="Observing network">
        {nearestStation && (
          <Row
            icon={Radar}
            label={nearestStation.station.name}
            value={`${nearestStation.km.toFixed(0)} km`}
            note={
              nearestStation.km <= nearestStation.station.range_km
                ? `Inside ${nearestStation.station.range_km} km scan radius`
                : `Outside ${nearestStation.station.range_km} km scan radius — radar gap`
            }
            tone={
              nearestStation.km <= nearestStation.station.range_km
                ? 'var(--color-prov-live)'
                : 'var(--color-sev-severe)'
            }
          />
        )}

        {nearestNode && (
          <Row
            icon={Crosshair}
            label={`Nearest cell · ${nearestNode.node.name}`}
            value={`${nearestNode.km.toFixed(0)} km`}
            note={`${nearestNode.node.instability} · CAPE ${nearestNode.node.cape_j_kg.toFixed(0)} J/kg`}
            tone={severityColor(nearestNode.node.instability)}
          />
        )}

        <Row
          icon={Zap}
          label={`Strikes within ${STRIKE_RADIUS_KM} km`}
          value={String(nearbyStrikes.total)}
          note={
            nearbyStrikes.total === 0
              ? 'No flashes in the detection window'
              : `${nearbyStrikes.cg} cloud-to-ground · newest ${
                  nearbyStrikes.newest ? `${Math.round(nearbyStrikes.newest.age_s)}s ago` : '--'
                }`
          }
          tone={nearbyStrikes.total > 0 ? 'var(--color-flash-cg)' : undefined}
        />
      </Section>

      <footer className="district-panel__foot">
        <span>
          {lat.toFixed(3)}°N {lon.toFixed(3)}°E
        </span>
        {weather && (
          <span title={new Date(weather.fetchedAt).toLocaleString()}>
            {new Date(weather.fetchedAt).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        )}
      </footer>
    </aside>
  );
};

// -----------------------------------------------------------------------------
// Local presentation pieces
// -----------------------------------------------------------------------------

/**
 * Why the surface readings are missing.
 *
 * Rate limiting and an outage look identical in a try/catch but call for
 * different responses -- one resolves on a clock, the other does not -- so the
 * panel names which one it is and, when it can, when the data returns.
 */
const ObservationFailure: React.FC = () => {
  const status = providerStatus();
  if (status.limited) {
    const at = new Date(status.retryAt).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
    return (
      <p className="district-panel__error">
        Observation provider rate limit reached. Live surface readings resume
        around {at}. Boundary and network figures below are unaffected.
      </p>
    );
  }
  return (
    <p className="district-panel__error">
      Observation provider unreachable. The boundary and network figures below
      are unaffected.
    </p>
  );
};

/**
 * 120-hour convective outlook.
 *
 * Two resolutions, because they answer different questions. The hourly strip
 * shows *when* — convection has a strong diurnal cycle and a forecaster reads
 * the afternoon spikes at a glance. The day cells show *which day* is worth
 * planning around.
 *
 * Labelled as a forecast, not a nowcast: these are NWP model fields at up to
 * five days, not the 0-2 h observed-radar product, and presenting them with
 * equal confidence would be misleading.
 */
const OutlookSection: React.FC<{ outlook: DistrictOutlook }> = ({ outlook }) => {
  const peak = outlook.days.reduce(
    (worst, d) => (d.peakThreat > worst.peakThreat ? d : worst),
    outlook.days[0],
  );

  return (
    <Section title="Outlook · 120 h" provenance="MODEL">
      <div className="outlook-strip" role="img" aria-label="Hourly convective threat for the next 120 hours">
        {outlook.hours.map((hr) => (
          <span
            key={hr.time}
            style={{
              height: `${Math.max(6, hr.threatScore)}%`,
              background: severityColor(hr.severity),
            }}
            title={`${new Date(hr.time).toLocaleString([], {
              weekday: 'short',
              hour: '2-digit',
            })} · ${hr.severity} ${hr.threatScore}`}
          />
        ))}
      </div>

      <div className="outlook-days">
        {outlook.days.map((day) => (
          <div key={day.date} className="outlook-day">
            <span className="outlook-day__label">{day.label}</span>
            <span
              className="outlook-day__score font-mono tabular"
              style={{ color: severityColor(day.peakSeverity) }}
            >
              {day.peakThreat}
            </span>
            <span className="outlook-day__meta">
              {day.thunderstormHours > 0
                ? `${day.thunderstormHours}h TS`
                : `${String(day.peakHour).padStart(2, '0')}:00`}
            </span>
          </div>
        ))}
      </div>

      <p className="district-panel__note">
        Peak {peak.peakThreat} on {peak.label}
        {peak.maxCapeJkg != null && ` · CAPE to ${peak.maxCapeJkg.toFixed(0)} J/kg`}.
        Forecast model fields — not the 0–2 h nowcast.
      </p>
    </Section>
  );
};

const Section: React.FC<{
  title: string;
  provenance?: string;
  children: React.ReactNode;
}> = ({ title, provenance, children }) => (
  <section className="district-section">
    <div className="district-section__head">
      <span className="eyebrow">{title}</span>
      {provenance && <span className="district-section__prov">{provenance}</span>}
    </div>
    {children}
  </section>
);

const Row: React.FC<{
  icon: React.ElementType;
  label: string;
  value: string;
  note?: string;
  tone?: string;
}> = ({ icon: Icon, label, value, note, tone }) => (
  <div className="district-row">
    <Icon
      className="w-3.5 h-3.5 shrink-0 mt-0.5"
      style={{ color: tone ?? 'var(--color-ink-faint)' }}
    />
    <div className="min-w-0 flex-1">
      <div className="district-row__label">{label}</div>
      {note && <div className="district-row__note">{note}</div>}
    </div>
    <span className="district-row__value font-mono tabular" style={{ color: tone }}>
      {value}
    </span>
  </div>
);

// -----------------------------------------------------------------------------
// Operational interpretation of each sounding parameter
// -----------------------------------------------------------------------------

const capeNote = (v: number | null): string | undefined => {
  if (v == null) return undefined;
  if (v < 300) return 'Insufficient buoyancy';
  if (v < 1000) return 'Weak instability';
  if (v < 2500) return 'Moderate instability';
  if (v < 3500) return 'Strong instability';
  return 'Extreme instability';
};

const cinNote = (v: number | null): string | undefined => {
  if (v == null) return undefined;
  const cap = Math.abs(v);
  if (cap < 25) return 'Uncapped';
  if (cap < 75) return 'Weak cap';
  if (cap < 150) return 'Moderate cap';
  return 'Strong cap — needs forcing';
};

const liNote = (v: number | null): string | undefined => {
  if (v == null) return undefined;
  if (v > 0) return 'Stable';
  if (v > -3) return 'Marginally unstable';
  if (v > -6) return 'Unstable';
  return 'Very unstable';
};

const shearNote = (v: number | null): string | undefined => {
  if (v == null) return undefined;
  if (v < 20) return 'Pulse / single-cell';
  if (v < 35) return 'Multicell organisation';
  return 'Supercell-capable';
};
