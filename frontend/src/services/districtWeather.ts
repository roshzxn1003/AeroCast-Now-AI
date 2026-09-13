/**
 * Live per-district weather and convective diagnosis.
 *
 * This talks to Open-Meteo directly from the browser rather than through the
 * FastAPI backend. Open-Meteo is keyless and sends permissive CORS headers, so
 * proxying it would add a hop and a failure mode without adding anything — and
 * it keeps the district layer independent of whether the Python service is up.
 *
 * The endpoint accepts comma-separated coordinate lists and answers with one
 * result object per point, which is what makes a district choropleth practical:
 * the ~60 districts in a typical viewport cost two requests, not sixty.
 */

import { District } from './districts';
import { SeverityLevel } from '../design/tokens';

const ENDPOINT = 'https://api.open-meteo.com/v1/forecast';

/** Points per request. Keeps the query string well inside URL length limits. */
const BATCH_SIZE = 50;

/**
 * How long a reading stays usable. Open-Meteo refreshes on a 15-minute cycle
 * and the nowcasting domain is 0-2 h, so a 10-minute cache never shows the user
 * a value the upstream has already superseded.
 */
const TTL_MS = 15 * 60 * 1000;

/** localStorage key for the persisted reading cache. */
const STORE_KEY = 'aerocast.districtWeather.v1';

/** Fallback cooldown when the provider rate-limits without a Retry-After. */
const DEFAULT_COOLDOWN_MS = 10 * 60 * 1000;

export interface DistrictWeather {
  districtId: string;
  /** Epoch ms at which this reading was retrieved. */
  fetchedAt: number;

  // -- Observed surface state -------------------------------------------------
  temperatureC: number | null;
  apparentC: number | null;
  humidityPct: number | null;
  precipitationMm: number | null;
  cloudCoverPct: number | null;
  pressureHpa: number | null;
  windKph: number | null;
  gustKph: number | null;
  windDirDeg: number | null;
  weatherCode: number | null;

  // -- Convective diagnosis ---------------------------------------------------
  /** Convective Available Potential Energy, J/kg. */
  capeJkg: number | null;
  /**
   * Convective Inhibition, J/kg, negative by meteorological convention.
   * Open-Meteo reports it as a positive magnitude; it is negated on parse so
   * it reads the same way as the CIN the backend and radar panels show.
   */
  cinJkg: number | null;
  /** Lifted Index, °C. Negative is unstable. */
  liftedIndex: number | null;
  /** Probability of precipitation in the current hour, %. */
  precipProbPct: number | null;
  /** 0-6 km bulk shear proxy from the 10 m and 500 hPa wind vectors, kt. */
  shearKt: number | null;

  // -- Derived ----------------------------------------------------------------
  severity: SeverityLevel;
  /** 0-100 composite convective threat. */
  threatScore: number;
  /** Plain-language summary of the WMO weather code. */
  conditions: string;
  /** True when the WMO code reports thunderstorm at the surface. */
  thunderstorm: boolean;
}

// -----------------------------------------------------------------------------
// WMO 4677 weather codes
// -----------------------------------------------------------------------------

const WMO: Record<number, string> = {
  0: 'Clear sky',
  1: 'Mainly clear',
  2: 'Partly cloudy',
  3: 'Overcast',
  45: 'Fog',
  48: 'Rime fog',
  51: 'Light drizzle',
  53: 'Drizzle',
  55: 'Dense drizzle',
  56: 'Freezing drizzle',
  57: 'Dense freezing drizzle',
  61: 'Light rain',
  63: 'Moderate rain',
  65: 'Heavy rain',
  66: 'Freezing rain',
  67: 'Heavy freezing rain',
  71: 'Light snow',
  73: 'Moderate snow',
  75: 'Heavy snow',
  77: 'Snow grains',
  80: 'Light showers',
  81: 'Moderate showers',
  82: 'Violent showers',
  85: 'Light snow showers',
  86: 'Heavy snow showers',
  95: 'Thunderstorm',
  96: 'Thunderstorm with hail',
  99: 'Thunderstorm with heavy hail',
};

const THUNDER_CODES = new Set([95, 96, 99]);

export const describeCode = (code: number | null): string =>
  code == null ? 'Unavailable' : (WMO[code] ?? `WMO ${code}`);

// -----------------------------------------------------------------------------
// Convective diagnosis
// -----------------------------------------------------------------------------

/**
 * Composite 0-100 convective threat score.
 *
 * Weighted the way a duty forecaster reads a sounding: buoyancy (CAPE) is the
 * single largest term because nothing convective happens without it, lifted
 * index corroborates it from the temperature profile, deep-layer shear decides
 * whether a cell organises or collapses, and the precipitation signal confirms
 * that something is actually happening rather than merely possible. CIN is
 * subtracted last, as a cap that suppresses an otherwise loaded sounding.
 */
function computeThreat(w: {
  capeJkg: number | null;
  liftedIndex: number | null;
  cinJkg: number | null;
  shearKt: number | null;
  precipProbPct: number | null;
  weatherCode: number | null;
}): number {
  let score = 0;

  // Buoyancy: 0 at 0 J/kg, saturating at 3500 J/kg. 40 points.
  if (w.capeJkg != null) score += Math.min(1, w.capeJkg / 3500) * 40;

  // Lifted index: 0 at LI >= 0, full at LI <= -8. 20 points.
  if (w.liftedIndex != null) {
    score += Math.min(1, Math.max(0, -w.liftedIndex) / 8) * 20;
  }

  // Deep-layer shear: organisation threshold is ~20 kt, well-organised ~40 kt.
  // 15 points.
  if (w.shearKt != null) score += Math.min(1, w.shearKt / 40) * 15;

  // Precipitation probability. 15 points.
  if (w.precipProbPct != null) score += (w.precipProbPct / 100) * 15;

  // Observed thunderstorm at the surface is not a forecast — it is the event.
  if (w.weatherCode != null && THUNDER_CODES.has(w.weatherCode)) score += 20;

  // Convective inhibition caps the sounding: a strong lid suppresses a loaded
  // profile until something breaks it.
  if (w.cinJkg != null) {
    const cin = Math.abs(w.cinJkg);
    if (cin > 50) score -= Math.min(18, (cin - 50) / 12);
  }

  return Math.round(Math.min(100, Math.max(0, score)));
}

function severityFor(score: number, thunderstorm: boolean): SeverityLevel {
  if (thunderstorm && score >= 60) return 'EXTREME';
  if (score >= 70) return 'EXTREME';
  if (score >= 52) return 'SEVERE';
  if (score >= 34) return 'MODERATE';
  if (score >= 18) return 'MARGINAL';
  return 'STABLE';
}

/**
 * Bulk shear magnitude between the 10 m and 500 hPa wind vectors, in knots.
 *
 * This is a proxy, not the operational 0-6 km bulk shear: 500 hPa sits near
 * 5.5 km, and Open-Meteo gives winds at levels rather than heights. It tracks
 * the real quantity closely enough to separate organised convection from
 * pulse storms, which is the distinction the score needs it for.
 */
function bulkShearKt(
  sfcSpeedKph: number | null,
  sfcDirDeg: number | null,
  upperSpeedKph: number | null,
  upperDirDeg: number | null,
): number | null {
  if (
    sfcSpeedKph == null ||
    sfcDirDeg == null ||
    upperSpeedKph == null ||
    upperDirDeg == null
  ) {
    return null;
  }
  const vec = (speedKph: number, dirDeg: number) => {
    // Meteorological convention: direction is where the wind comes FROM.
    const rad = ((dirDeg + 180) * Math.PI) / 180;
    const kt = speedKph * 0.539957;
    return [kt * Math.sin(rad), kt * Math.cos(rad)] as const;
  };
  const [ux, uy] = vec(sfcSpeedKph, sfcDirDeg);
  const [vx, vy] = vec(upperSpeedKph, upperDirDeg);
  return Math.round(Math.hypot(vx - ux, vy - uy));
}

// -----------------------------------------------------------------------------
// Fetching
// -----------------------------------------------------------------------------

const CURRENT_VARS = [
  'temperature_2m',
  'relative_humidity_2m',
  'apparent_temperature',
  'precipitation',
  'weather_code',
  'cloud_cover',
  'surface_pressure',
  'wind_speed_10m',
  'wind_gusts_10m',
  'wind_direction_10m',
].join(',');

const HOURLY_VARS = [
  'cape',
  'lifted_index',
  'convective_inhibition',
  'precipitation_probability',
  'wind_speed_500hPa',
  'wind_direction_500hPa',
].join(',');

interface RawPoint {
  utc_offset_seconds?: number;
  current?: Record<string, number>;
  hourly?: Record<string, (number | null)[]> & { time?: string[] };
}

const cache = new Map<string, DistrictWeather>();
const inFlight = new Map<string, Promise<void>>();

const num = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

/**
 * Index of the hour matching the observation time.
 *
 * The hourly arrays start at local midnight of the current day, so the current
 * hour is simply its local hour-of-day. Derived from the payload's own UTC
 * offset rather than the browser clock, which may sit in a different zone.
 */
function currentHourIndex(p: RawPoint): number {
  const offsetMs = (p.utc_offset_seconds ?? 0) * 1000;
  const local = new Date(Date.now() + offsetMs);
  return Math.min(23, Math.max(0, local.getUTCHours()));
}

function parsePoint(district: District, p: RawPoint): DistrictWeather {
  const cur = p.current ?? {};
  const h = p.hourly ?? {};
  const i = currentHourIndex(p);
  const at = (key: string): number | null => num(h[key]?.[i]);

  const weatherCode = num(cur.weather_code);
  const windKph = num(cur.wind_speed_10m);
  const windDirDeg = num(cur.wind_direction_10m);

  const capeJkg = at('cape');
  const rawCin = at('convective_inhibition');
  const cinJkg = rawCin == null ? null : -Math.abs(rawCin);
  const liftedIndex = at('lifted_index');
  const precipProbPct = at('precipitation_probability');
  const shearKt = bulkShearKt(
    windKph,
    windDirDeg,
    at('wind_speed_500hPa'),
    at('wind_direction_500hPa'),
  );

  const thunderstorm = weatherCode != null && THUNDER_CODES.has(weatherCode);
  const threatScore = computeThreat({
    capeJkg,
    liftedIndex,
    cinJkg,
    shearKt,
    precipProbPct,
    weatherCode,
  });

  return {
    districtId: district.id,
    fetchedAt: Date.now(),
    temperatureC: num(cur.temperature_2m),
    apparentC: num(cur.apparent_temperature),
    humidityPct: num(cur.relative_humidity_2m),
    precipitationMm: num(cur.precipitation),
    cloudCoverPct: num(cur.cloud_cover),
    pressureHpa: num(cur.surface_pressure),
    windKph,
    gustKph: num(cur.wind_gusts_10m),
    windDirDeg,
    weatherCode,
    capeJkg,
    cinJkg,
    liftedIndex,
    precipProbPct,
    shearKt,
    severity: severityFor(threatScore, thunderstorm),
    threatScore,
    conditions: describeCode(weatherCode),
    thunderstorm,
  };
}

const isFresh = (w: DistrictWeather) => Date.now() - w.fetchedAt < TTL_MS;

/** Cached reading for a district, if one was fetched recently. */
export const peekDistrictWeather = (id: string): DistrictWeather | null => {
  const hit = cache.get(id);
  return hit && isFresh(hit) ? hit : null;
};

/**
 * Provider rate-limit state.
 *
 * Open-Meteo's free tier bills a multi-coordinate request as one call per
 * coordinate, so a viewport of 60 districts costs 60 against the hourly
 * allowance -- a few minutes of panning can exhaust it. When that happens the
 * API answers 429, and continuing to hammer it neither helps nor recovers
 * faster. Every batch is gated on this cooldown, and the UI reports being rate
 * limited as its own state rather than as "provider unreachable", because the
 * two call for completely different responses from the user.
 */
let cooldownUntil = 0;

export interface ProviderStatus {
  /** True while the provider is rate limiting us. */
  limited: boolean;
  /** Epoch ms at which requests resume. */
  retryAt: number;
}

export const providerStatus = (): ProviderStatus => ({
  limited: Date.now() < cooldownUntil,
  retryAt: cooldownUntil,
});

// -----------------------------------------------------------------------------
// Persistence
// -----------------------------------------------------------------------------

/**
 * Readings survive a reload.
 *
 * Without this every refresh re-buys the whole viewport from a metered API.
 * Entries carry their own timestamp and are re-checked against the TTL on
 * load, so a stale cache expires exactly as an in-memory one would.
 */
function loadPersisted(): void {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Record<string, DistrictWeather>;
    const now = Date.now();
    for (const [id, w] of Object.entries(parsed)) {
      if (w && typeof w.fetchedAt === 'number' && now - w.fetchedAt < TTL_MS) {
        cache.set(id, w);
      }
    }
  } catch {
    // Private browsing, blocked site data, or a corrupt entry. The cache is an
    // optimisation, never a correctness requirement.
  }
}

let persistTimer: number | null = null;

function schedulePersist(): void {
  if (persistTimer != null) return;
  persistTimer = window.setTimeout(() => {
    persistTimer = null;
    try {
      const now = Date.now();
      const fresh: Record<string, DistrictWeather> = {};
      for (const [id, w] of cache) {
        if (now - w.fetchedAt < TTL_MS) fresh[id] = w;
      }
      localStorage.setItem(STORE_KEY, JSON.stringify(fresh));
    } catch {
      // Quota exceeded or storage unavailable -- nothing to do about it.
    }
  }, 2000);
}

/**
 * Fetch one batch and write every parsed point straight into the cache.
 *
 * Never rejects: a failed batch must leave the rest of the map intact.
 */
async function runBatch(
  batch: District[],
  signal?: AbortSignal,
): Promise<void> {
  const params = new URLSearchParams({
    latitude: batch.map((d) => d.centroid[1].toFixed(4)).join(','),
    longitude: batch.map((d) => d.centroid[0].toFixed(4)).join(','),
    current: CURRENT_VARS,
    hourly: HOURLY_VARS,
    forecast_days: '1',
    timezone: 'auto',
  });

  if (Date.now() < cooldownUntil) return;

  try {
    const res = await fetch(`${ENDPOINT}?${params}`, { signal });

    if (res.status === 429) {
      const retryAfter = Number(res.headers.get('retry-after'));
      cooldownUntil =
        Date.now() +
        (Number.isFinite(retryAfter) && retryAfter > 0
          ? retryAfter * 1000
          : DEFAULT_COOLDOWN_MS);
      console.warn('District weather rate limited; pausing until', new Date(cooldownUntil).toISOString());
      return;
    }

    if (!res.ok) throw new Error(`open-meteo ${res.status}`);
    const body = await res.json();
    // A single-coordinate request answers with an object, not an array.
    const points: RawPoint[] = Array.isArray(body) ? body : [body];
    batch.forEach((d, i) => {
      const point = points[i];
      if (point) cache.set(d.id, parsePoint(d, point));
    });
    schedulePersist();
  } catch (err) {
    if ((err as Error)?.name !== 'AbortError') {
      console.warn('District weather batch failed:', err);
    }
  }
}

/**
 * Fetch live weather for a set of districts.
 *
 * Fresh cache entries are served without a request and identical in-flight
 * requests are shared rather than duplicated. Sharing has one trap worth
 * naming: the request a caller waits on belongs to someone else and may be
 * aborted by them, which would otherwise leave this caller with nothing and
 * no way to tell that apart from a genuine provider failure. So anything still
 * missing after the shared requests settle is fetched directly in a second,
 * unshared pass.
 */
export async function fetchDistrictWeather(
  districts: District[],
  signal?: AbortSignal,
): Promise<Map<string, DistrictWeather>> {
  const out = new Map<string, DistrictWeather>();
  const pending: District[] = [];
  const deferred: District[] = [];
  const waits: Promise<void>[] = [];

  for (const d of districts) {
    const hit = peekDistrictWeather(d.id);
    if (hit) {
      out.set(d.id, hit);
      continue;
    }
    const running = inFlight.get(d.id);
    if (running) {
      deferred.push(d);
      waits.push(running);
    } else {
      pending.push(d);
    }
  }

  const work: Promise<void>[] = [];
  for (let i = 0; i < pending.length; i += BATCH_SIZE) {
    const batch = pending.slice(i, i + BATCH_SIZE);
    const run = runBatch(batch, signal).finally(() => {
      batch.forEach((d) => inFlight.delete(d.id));
    });
    batch.forEach((d) => inFlight.set(d.id, run));
    work.push(run);
  }

  await Promise.all([...work, ...waits]);

  // Second pass: districts whose shared request was aborted or failed.
  const stranded = deferred.filter((d) => !peekDistrictWeather(d.id));
  if (stranded.length && !signal?.aborted) {
    const retries: Promise<void>[] = [];
    for (let i = 0; i < stranded.length; i += BATCH_SIZE) {
      retries.push(runBatch(stranded.slice(i, i + BATCH_SIZE), signal));
    }
    await Promise.all(retries);
  }

  for (const d of districts) {
    if (out.has(d.id)) continue;
    const hit = peekDistrictWeather(d.id);
    if (hit) out.set(d.id, hit);
  }

  return out;
}

/** Convenience wrapper for a single district. */
export async function fetchOneDistrictWeather(
  district: District,
  signal?: AbortSignal,
): Promise<DistrictWeather | null> {
  const map = await fetchDistrictWeather([district], signal);
  return map.get(district.id) ?? null;
}

/** Compass point for a meteorological wind direction. */
export function compass(deg: number | null): string {
  if (deg == null) return '--';
  const points = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  return points[Math.round(deg / 22.5) % 16];
}

// Hydrate from the previous session before anything asks for a reading.
loadPersisted();

// =============================================================================
// 120-hour convective outlook
// =============================================================================

/**
 * The extended outlook is a different product from the nowcast, and the UI must
 * never let them blur together.
 *
 * The ConvLSTM nowcast answers "where is this storm in the next two hours" from
 * observed radar, satellite and lightning. This answers "which days this week
 * look convectively dangerous" from NWP forecast fields. Different horizon,
 * different physics, very different confidence — so it is scored with the same
 * threat function for comparability, but labelled and cached separately.
 */

/** Hours requested. Open-Meteo serves hourly fields out to 16 days. */
const OUTLOOK_HOURS = 120;

/** Forecast fields change on a model cycle, not minute to minute. */
const OUTLOOK_TTL_MS = 60 * 60 * 1000;

const OUTLOOK_VARS = [
  'temperature_2m',
  'cape',
  'lifted_index',
  'convective_inhibition',
  'precipitation_probability',
  'precipitation',
  'weather_code',
  'wind_gusts_10m',
  'wind_speed_10m',
  'wind_direction_10m',
  'wind_speed_500hPa',
  'wind_direction_500hPa',
].join(',');

export interface OutlookHour {
  /** Epoch ms of the forecast hour, in the district's local time. */
  time: number;
  temperatureC: number | null;
  capeJkg: number | null;
  liftedIndex: number | null;
  precipProbPct: number | null;
  precipitationMm: number | null;
  gustKph: number | null;
  weatherCode: number | null;
  thunderstorm: boolean;
  threatScore: number;
  severity: SeverityLevel;
}

export interface OutlookDay {
  /** Local calendar date, ISO yyyy-mm-dd. */
  date: string;
  /** Short weekday label, e.g. "Mon". */
  label: string;
  /** Worst hour of the day. */
  peakThreat: number;
  peakSeverity: SeverityLevel;
  /** Local hour (0-23) at which the peak occurs — convection has a diurnal cycle. */
  peakHour: number;
  maxCapeJkg: number | null;
  maxPrecipProbPct: number | null;
  /** Hours whose WMO code reports a thunderstorm. */
  thunderstormHours: number;
}

export interface DistrictOutlook {
  districtId: string;
  fetchedAt: number;
  hours: OutlookHour[];
  days: OutlookDay[];
}

const outlookCache = new Map<string, DistrictOutlook>();

export const peekDistrictOutlook = (id: string): DistrictOutlook | null => {
  const hit = outlookCache.get(id);
  return hit && Date.now() - hit.fetchedAt < OUTLOOK_TTL_MS ? hit : null;
};

/**
 * Fetch the 120-hour convective outlook for one district.
 *
 * Returns null rather than throwing, and respects the same rate-limit cooldown
 * as the nowcast readings — the outlook is the less urgent of the two, so it
 * must never spend the remaining quota that live readings need.
 */
export async function fetchDistrictOutlook(
  district: District,
  signal?: AbortSignal,
): Promise<DistrictOutlook | null> {
  const cached = peekDistrictOutlook(district.id);
  if (cached) return cached;
  if (Date.now() < cooldownUntil) return null;

  const params = new URLSearchParams({
    latitude: district.centroid[1].toFixed(4),
    longitude: district.centroid[0].toFixed(4),
    hourly: OUTLOOK_VARS,
    forecast_hours: String(OUTLOOK_HOURS),
    timezone: 'auto',
  });

  try {
    const res = await fetch(`${ENDPOINT}?${params}`, { signal });
    if (res.status === 429) {
      const retryAfter = Number(res.headers.get('retry-after'));
      cooldownUntil =
        Date.now() +
        (Number.isFinite(retryAfter) && retryAfter > 0
          ? retryAfter * 1000
          : DEFAULT_COOLDOWN_MS);
      return null;
    }
    if (!res.ok) throw new Error(`open-meteo ${res.status}`);

    const body = await res.json();
    const point: RawPoint = Array.isArray(body) ? body[0] : body;
    const h = point?.hourly;
    const times = (h?.time as unknown as string[] | undefined) ?? [];
    if (!h || !times.length) return null;

    const hours: OutlookHour[] = [];
    for (let i = 0; i < times.length; i++) {
      const at = (key: string) => num(h[key]?.[i]);
      const weatherCode = at('weather_code');
      const rawCin = at('convective_inhibition');
      const capeJkg = at('cape');
      const liftedIndex = at('lifted_index');
      const precipProbPct = at('precipitation_probability');
      const shearKt = bulkShearKt(
        at('wind_speed_10m'),
        at('wind_direction_10m'),
        at('wind_speed_500hPa'),
        at('wind_direction_500hPa'),
      );
      const thunderstorm = weatherCode != null && THUNDER_CODES.has(weatherCode);
      const threatScore = computeThreat({
        capeJkg,
        liftedIndex,
        cinJkg: rawCin == null ? null : -Math.abs(rawCin),
        shearKt,
        precipProbPct,
        weatherCode,
      });

      hours.push({
        // Open-Meteo returns local wall-clock with timezone=auto; parsed as
        // local so the diurnal peak lands on the right hour for the district.
        time: new Date(times[i]).getTime(),
        temperatureC: at('temperature_2m'),
        capeJkg,
        liftedIndex,
        precipProbPct,
        precipitationMm: at('precipitation'),
        gustKph: at('wind_gusts_10m'),
        weatherCode,
        thunderstorm,
        threatScore,
        severity: severityFor(threatScore, thunderstorm),
      });
    }

    const byDate = new Map<string, OutlookHour[]>();
    for (let i = 0; i < hours.length; i++) {
      const date = times[i].slice(0, 10);
      const bucket = byDate.get(date);
      if (bucket) bucket.push(hours[i]);
      else byDate.set(date, [hours[i]]);
    }

    const days: OutlookDay[] = [...byDate.entries()].map(([date, bucket]) => {
      let peak = bucket[0];
      for (const hr of bucket) if (hr.threatScore > peak.threatScore) peak = hr;
      const maxOf = (pick: (hr: OutlookHour) => number | null): number | null => {
        const vals = bucket.map(pick).filter((v): v is number => v != null);
        return vals.length ? Math.max(...vals) : null;
      };
      return {
        date,
        label: new Date(`${date}T12:00:00`).toLocaleDateString([], { weekday: 'short' }),
        peakThreat: peak.threatScore,
        peakSeverity: peak.severity,
        peakHour: new Date(peak.time).getHours(),
        maxCapeJkg: maxOf((hr) => hr.capeJkg),
        maxPrecipProbPct: maxOf((hr) => hr.precipProbPct),
        thunderstormHours: bucket.filter((hr) => hr.thunderstorm).length,
      };
    });

    const outlook: DistrictOutlook = {
      districtId: district.id,
      fetchedAt: Date.now(),
      hours,
      days,
    };
    outlookCache.set(district.id, outlook);
    return outlook;
  } catch (err) {
    if ((err as Error)?.name !== 'AbortError') {
      console.warn('District outlook failed:', err);
    }
    return null;
  }
}
