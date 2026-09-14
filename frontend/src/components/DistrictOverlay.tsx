/**
 * District layer controller for the globe.
 *
 * Owns everything district-related that sits on top of the 3D scene: the
 * boundary/choropleth layer, the gazetteer search, the detail readout and the
 * legend. LightningGlobe mounts this with its globe instance and otherwise
 * knows nothing about districts, which keeps the two independently editable.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { GlobeInstance } from 'globe.gl';
import { Loader2, Layers, ChevronDown, ChevronUp, Zap, Info } from 'lucide-react';
import {
  attachDistrictLayer,
  BORDER_VISIBLE_ALTITUDE,
  DistrictLayerHandle,
} from '../globe/districtLayer';
import { attachTileLayer, TileLayerHandle, TileStyle } from '../globe/tileLayer';
import { District, loadDistrictIndex } from '../services/districts';
import {
  fetchDistrictWeather,
  peekDistrictWeather,
  providerStatus,
} from '../services/districtWeather';
import { DistrictSearch, SearchResult } from './DistrictSearch';
import { DistrictDetailPanel } from './DistrictDetailPanel';
import { FLASH, SEVERITY_COLOR, SEVERITY_LEVELS, SeverityLevel } from '../design/tokens';
import { useNowcastStore } from '../store/nowcastStore';
import '../styles/districts.css';

interface DistrictOverlayProps {
  /** Globe instance, once it exists. Null until the globe has initialised. */
  globe: GlobeInstance | null;
  /** The element the globe canvas renders into — labels and picking attach here. */
  container: HTMLElement | null;
}

/**
 * Districts fetched per viewport change.
 *
 * Open-Meteo's free tier is generous but not unlimited, and a user panning
 * across the country would otherwise issue a request for every district they
 * sweep past. The cap keeps a single pan bounded; the 10-minute cache in the
 * weather service absorbs the repeats.
 */
const MAX_VIEWPORT_FETCH = 60;

/** Minimum gap between viewport-driven fetches. */
const FETCH_THROTTLE_MS = 1200;

/**
 * Quiet period after the last viewport change before fetching.
 *
 * A `flyTo` animation runs ~1.1 s and reports a new viewport several times on
 * the way, each of which would otherwise bill a fetch for districts the camera
 * is merely passing over. Waiting for the camera to settle collapses a flight
 * into a single request for where it actually landed.
 */
const SETTLE_MS = 700;

export const DistrictOverlay: React.FC<DistrictOverlayProps> = ({
  globe,
  container,
}) => {
  const layerRef = useRef<DistrictLayerHandle | null>(null);
  const tileRef = useRef<TileLayerHandle | null>(null);
  const severityRef = useRef(new Map<string, SeverityLevel>());
  const lastFetchRef = useRef(0);
  const fetchTimerRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [layerReady, setLayerReady] = useState(false);
  const [layerError, setLayerError] = useState<string | null>(null);
  const [selected, setSelected] = useState<District | null>(null);
  const [hovered, setHovered] = useState<District | null>(null);
  const [scored, setScored] = useState(0);
  const [index, setIndex] = useState<Map<string, District>>(new Map());
  const [tileZoom, setTileZoom] = useState<number | null>(null);
  const [attribution, setAttribution] = useState('');

  const earthTheme = useNowcastStore((s) => s.earthTheme);

  // One basemap, always true-colour imagery. The globe's day/night control
  // still swaps the far-view Earth texture and atmosphere, but it no longer
  // switches the close-range basemap to a grey cartographic canvas: grey under
  // a weather product reads as missing data.
  // 'satellite-clean' omits the provider's own place-name raster. The district
  // label layer already names what is on screen, and running both printed every
  // city twice, a few pixels apart.
  const tileStyle: TileStyle = 'satellite-clean';

  // The index is small and the panel needs plain District records, while the
  // layer works in geometry records. Keeping the lookup here means the panel
  // never has to hold the 1.3 MB geometry payload.
  useEffect(() => {
    let cancelled = false;
    loadDistrictIndex()
      .then((list) => {
        if (!cancelled) setIndex(new Map(list.map((d) => [d.id, d])));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Weather -> choropleth
  // ---------------------------------------------------------------------------

  const paint = useCallback(() => {
    layerRef.current?.setSeverity(severityRef.current);
    setScored(severityRef.current.size);
  }, []);

  const loadWeatherFor = useCallback(
    (districts: District[]) => {
      const wanted = districts.slice(0, MAX_VIEWPORT_FETCH);
      if (!wanted.length) return;

      // Anything already cached can colour the map immediately, without
      // waiting on the network.
      let fromCache = false;
      for (const d of wanted) {
        const cached = peekDistrictWeather(d.id);
        if (cached && severityRef.current.get(d.id) !== cached.severity) {
          severityRef.current.set(d.id, cached.severity);
          fromCache = true;
        }
      }
      if (fromCache) paint();

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      lastFetchRef.current = Date.now();

      fetchDistrictWeather(wanted, controller.signal)
        .then((map) => {
          if (controller.signal.aborted) return;
          for (const [id, w] of map) severityRef.current.set(id, w.severity);
          paint();
        })
        .catch(() => undefined);
    },
    [paint],
  );

  const onViewportChange = useCallback(
    (visible: District[], altitude: number) => {
      // Above this altitude no district boundary is drawn, so a choropleth
      // nobody can see is not worth the requests it would cost.
      if (altitude >= BORDER_VISIBLE_ALTITUDE) return;
      if (fetchTimerRef.current != null) window.clearTimeout(fetchTimerRef.current);
      const wait = Math.max(
        SETTLE_MS,
        FETCH_THROTTLE_MS - (Date.now() - lastFetchRef.current),
      );
      fetchTimerRef.current = window.setTimeout(() => {
        fetchTimerRef.current = null;
        loadWeatherFor(visible);
      }, wait);
    },
    [loadWeatherFor],
  );

  // ---------------------------------------------------------------------------
  // Basemap tile pyramid
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!globe) return;
    const handle = attachTileLayer(globe, {
      style: tileStyle,
      onZoomChange: setTileZoom,
    });
    tileRef.current = handle;
    handle.setTheme?.(earthTheme);
    setAttribution(handle.attribution());
    // Development-only handle, alongside the globe's own __globe, so the
    // basemap can be toggled and inspected when diagnosing layer ordering.
    if (import.meta.env.DEV) {
      (window as unknown as { __tileLayer?: unknown }).__tileLayer = handle;
    }
    return () => {
      tileRef.current = null;
      handle.dispose();
    };
    // Style changes are applied through setStyle below rather than by
    // rebuilding the layer, so this intentionally depends on the globe alone.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [globe]);

  useEffect(() => {
    tileRef.current?.setTheme?.(earthTheme);
  }, [earthTheme]);

  useEffect(() => {
    const handle = tileRef.current;
    if (!handle) return;
    handle.setStyle(tileStyle);
    setAttribution(handle.attribution());
  }, [tileStyle]);

  // ---------------------------------------------------------------------------
  // Layer lifecycle
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!globe || !container) return;

    let disposed = false;
    let handle: DistrictLayerHandle | null = null;

    attachDistrictLayer(globe, container, {
      onHover: (d) => setHovered(d),
      onSelect: (d) => {
        setSelected(d);
        if (d) {
          layerRef.current?.flyTo(d.id, 900);
          loadWeatherFor([d]);
        }
      },
      onViewportChange,
    })
      .then((h) => {
        // The globe can unmount while the 1.3 MB geometry is still in flight.
        if (disposed) {
          h.dispose();
          return;
        }
        handle = h;
        layerRef.current = h;
        if (import.meta.env.DEV) {
          (window as unknown as { __districtLayer?: unknown }).__districtLayer = h;
        }
        setLayerReady(true);
        h.setSeverity(severityRef.current);
      })
      .catch((err) => {
        if (!disposed) setLayerError(String(err?.message ?? err));
      });

    return () => {
      disposed = true;
      if (fetchTimerRef.current != null) window.clearTimeout(fetchTimerRef.current);
      abortRef.current?.abort();
      handle?.dispose();
      layerRef.current = null;
      setLayerReady(false);
    };
  }, [globe, container, onViewportChange]);

  // Mirror selection into the layer so the outline follows panel-driven changes
  // (search, close button) as well as clicks on the globe itself.
  useEffect(() => {
    layerRef.current?.setSelected(selected?.id ?? null);
  }, [selected]);

  // ---------------------------------------------------------------------------
  // Search
  // ---------------------------------------------------------------------------

  const onSearchSelect = useCallback(
    (result: SearchResult) => {
      if (result.kind === 'district' && result.district) {
        setSelected(result.district);
        layerRef.current?.flyTo(result.district.id);
        loadWeatherFor([result.district]);
        return;
      }

      // States, radar stations and live cells are locations rather than
      // districts: fly there and clear any district selection, leaving the
      // user to pick a district from the boundaries now in frame.
      setSelected(null);
      const altitude = result.kind === 'state' ? 0.55 : 0.3;
      globe?.pointOfView({ lat: result.lat, lng: result.lon, altitude }, 1200);
    },
    [globe, loadWeatherFor],
  );

  const legend = useMemo(
    () =>
      SEVERITY_LEVELS.map((level) => ({
        level,
        color: SEVERITY_COLOR[level],
      })),
    [],
  );

  // Re-read on each paint tick; the cooldown is time-based, not reactive.
  const limited = providerStatus().limited;

  const selectedDistrict = selected
    ? (index.get(selected.id) ?? selected)
    : null;

  const [legendOpen, setLegendOpen] = useState(false);
  const [legendTab, setLegendTab] = useState<'districts' | 'radar'>('districts');

  return (
    <>
      <DistrictSearch onSelect={onSearchSelect} className="district-search-dock" />

      {hovered && !layerError && (
        <div className="district-hover" role="status">
          <span className="district-hover__name">{hovered.name}</span>
          <span className="district-hover__state text-slate-400">· {hovered.state}</span>
          <HoverSeverity id={hovered.id} />
        </div>
      )}

      {selectedDistrict && (
        <DistrictDetailPanel
          district={selectedDistrict}
          onClose={() => setSelected(null)}
          onLocate={() => layerRef.current?.flyTo(selectedDistrict.id)}
          className="district-panel-dock"
        />
      )}

      {/* Unified Collapsible Legend & Layers Widget */}
      <div className="absolute bottom-4 left-4 z-20">
        {!legendOpen ? (
          <button
            onClick={() => setLegendOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 hover:bg-slate-800/95 border border-white/10 text-xs font-mono text-slate-300 hover:text-white shadow-xl backdrop-blur-md transition-all hover:border-cyan-500/40"
            title="Open Map Legend & Layer Reference"
          >
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            <span className="font-semibold">Map Legend</span>
            <ChevronUp className="w-3 h-3 text-slate-400" />
          </button>
        ) : (
          <div className="district-legend enter">
            <div className="district-legend__head pb-1.5 border-b border-white/10">
              <div className="flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span className="district-legend__title">Map Legend</span>
              </div>
              <div className="flex items-center gap-1.5">
                {!layerReady && !layerError && (
                  <Loader2 className="w-3 h-3 spin text-cyan-400" />
                )}
                <button
                  onClick={() => setLegendOpen(false)}
                  className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                  title="Collapse Legend"
                >
                  <ChevronDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex rounded-lg bg-black/40 p-0.5 mt-2 text-[10px] font-mono">
              <button
                onClick={() => setLegendTab('districts')}
                className={`flex-1 py-1 rounded-md transition-all font-semibold ${
                  legendTab === 'districts'
                    ? 'bg-cyan-500/20 text-cyan-300 shadow-sm border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Districts
              </button>
              <button
                onClick={() => setLegendTab('radar')}
                className={`flex-1 py-1 rounded-md transition-all font-semibold ${
                  legendTab === 'radar'
                    ? 'bg-cyan-500/20 text-cyan-300 shadow-sm border border-cyan-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Lightning & Radar
              </button>
            </div>

            {legendTab === 'districts' ? (
              <div className="mt-2.5 space-y-2">
                <div
                  className="district-legend__scale"
                  role="img"
                  aria-label="Threat scale from stable to extreme"
                >
                  {legend.map(({ level, color }) => (
                    <span key={level} title={level} style={{ background: color }} />
                  ))}
                </div>
                <div className="district-legend__ends text-[10px] font-mono">
                  <span className="text-sky-300">Stable</span>
                  <span className="text-amber-300">Severe</span>
                  <span className="text-fuchsia-400">Extreme</span>
                </div>

                <p className="district-legend__note text-[11px] leading-relaxed">
                  {layerError
                    ? 'District boundaries unavailable'
                    : !layerReady
                      ? 'Loading 734 districts…'
                      : limited
                        ? `Provider limited · resumes ${new Date(
                            providerStatus().retryAt,
                          ).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                        : scored > 0
                          ? `${scored} of 734 districts scored`
                          : '734 districts · zoom in to score'}
                </p>

                {attribution && (
                  <p className="district-legend__credit" title={attribution}>
                    {tileZoom != null ? `z${tileZoom} · ` : ''}
                    {attribution}
                  </p>
                )}
              </div>
            ) : (
              <div className="mt-2.5 space-y-1.5 text-[11px]">
                <div className="flex items-center justify-between text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: FLASH.cg }} />
                    <span>Ground Strike (CG)</span>
                  </span>
                  <span className="font-mono text-[10px] text-amber-400">Amber</span>
                </div>
                <div className="flex items-center justify-between text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: FLASH.ic }} />
                    <span>In-Cloud Flash (IC)</span>
                  </span>
                  <span className="font-mono text-[10px] text-purple-400">Violet</span>
                </div>
                <div className="flex items-center justify-between text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-cyan-400" />
                    <span>DWR Radar City</span>
                  </span>
                  <span className="font-mono text-[10px] text-cyan-400">250km</span>
                </div>
                <div className="pt-1.5 border-t border-white/10 text-[10px] text-slate-400 leading-snug">
                  Sounding column height encodes convective vigour. Double-click or scroll to zoom.
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
};

/** Severity chip for the hover strip, read straight from the weather cache. */
const HoverSeverity: React.FC<{ id: string }> = ({ id }) => {
  const cached = peekDistrictWeather(id);
  if (!cached) return null;
  return (
    <span
      className="district-hover__sev"
      style={{ color: SEVERITY_COLOR[cached.severity] }}
    >
      {cached.severity} · {cached.threatScore}
    </span>
  );
};
