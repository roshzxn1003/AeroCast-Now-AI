/**
 * Unified gazetteer search for the globe.
 *
 * One box searches every locatable thing the app knows about — 734 districts,
 * 37 states, the DWR radar network and whatever convective nodes are live —
 * because from the operator's side "find Nagpur" is one question regardless of
 * which dataset happens to hold the answer. Results carry a kind badge so the
 * source is never ambiguous.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, MapPin, Radar, Zap, Layers, X } from 'lucide-react';
import {
  District,
  loadDistrictIndex,
  normalise,
  searchDistricts,
} from '../services/districts';
import { DEFAULT_STATIONS } from '../services/api';
import { useLiveStore } from '../store/liveStore';
import { ConvectiveNode, RadarStation } from '../types/nowcast';
import { ACCENT, severityColor } from '../design/tokens';

export type SearchKind = 'district' | 'state' | 'station' | 'node';

export interface SearchResult {
  kind: SearchKind;
  id: string;
  label: string;
  detail: string;
  lat: number;
  lon: number;
  /** Present for districts, so selection can drive the boundary layer. */
  district?: District;
  /** Tint for the leading icon; severity where one is known. */
  tone?: string;
}

interface DistrictSearchProps {
  onSelect: (result: SearchResult) => void;
  className?: string;
}

const KIND_META: Record<SearchKind, { icon: React.ElementType; label: string }> = {
  district: { icon: MapPin, label: 'District' },
  state: { icon: Layers, label: 'State' },
  station: { icon: Radar, label: 'DWR' },
  node: { icon: Zap, label: 'Live cell' },
};

const MAX_RESULTS = 10;

export const DistrictSearch: React.FC<DistrictSearchProps> = ({
  onSelect,
  className,
}) => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [districts, setDistricts] = useState<District[]>([]);
  const [loadError, setLoadError] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const convective = useLiveStore((s) => s.convective);
  const nodes = useMemo(() => convective?.nodes ?? [], [convective]);

  useEffect(() => {
    let cancelled = false;
    loadDistrictIndex()
      .then((d) => !cancelled && setDistricts(d))
      .catch(() => !cancelled && setLoadError(true));
    return () => {
      cancelled = true;
    };
  }, []);

  // Distinct states, derived from the district index so the two can never
  // disagree about which states exist.
  const states = useMemo(() => {
    const seen = new Map<string, { lat: number; lon: number; count: number }>();
    for (const d of districts) {
      const hit = seen.get(d.state);
      if (hit) {
        hit.lat += d.centroid[1];
        hit.lon += d.centroid[0];
        hit.count += 1;
      } else {
        seen.set(d.state, { lat: d.centroid[1], lon: d.centroid[0], count: 1 });
      }
    }
    return [...seen.entries()].map(([name, v]) => ({
      name,
      lat: v.lat / v.count,
      lon: v.lon / v.count,
      count: v.count,
    }));
  }, [districts]);

  const results = useMemo<SearchResult[]>(() => {
    const q = normalise(query);
    if (!q) return [];

    // Every kind is scored on one scale rather than concatenated in a fixed
    // order. Grouping by kind meant a live cell that happened to share a
    // district's name pushed the district itself off the top of the list, so
    // typing a district name and pressing Enter flew somewhere else.
    const scored: { result: SearchResult; score: number }[] = [];

    const add = (result: SearchResult, haystacks: string[], bonus: number) => {
      let best = 0;
      for (const h of haystacks) {
        const n = normalise(h);
        if (!n) continue;
        let score = 0;
        if (n === q) score = 1000;
        else if (n.startsWith(q)) score = 800 - n.length;
        else if (n.includes(q)) score = 400 - n.length;
        if (score > best) best = score;
      }
      if (best > 0) scored.push({ result, score: best + bonus });
    };

    for (const s of states) {
      add(
        {
          kind: 'state',
          id: `state:${s.name}`,
          label: s.name,
          detail: `${s.count} districts`,
          lat: s.lat,
          lon: s.lon,
        },
        [s.name],
        3,
      );
    }

    for (const station of DEFAULT_STATIONS as RadarStation[]) {
      add(
        {
          kind: 'station',
          id: `station:${station.name}`,
          label: station.name,
          detail: `${station.state} · ${station.radar_type}`,
          lat: station.lat,
          lon: station.lon,
        },
        [station.name, station.state],
        2,
      );
    }

    for (const node of nodes as ConvectiveNode[]) {
      add(
        {
          kind: 'node',
          id: `node:${node.name}`,
          label: node.name,
          detail: `${node.instability} · CAPE ${node.cape_j_kg.toFixed(0)} J/kg`,
          lat: node.lat,
          lon: node.lon,
          tone: severityColor(node.instability),
        },
        [node.name, node.region],
        4,
      );
    }

    // Districts keep the richer matcher in `searchDistricts` -- aliases,
    // word-boundary and subsequence matching -- and a bonus that wins ties,
    // since a named place is what the box is primarily for.
    for (const match of searchDistricts(districts, query, MAX_RESULTS)) {
      scored.push({
        result: {
          kind: 'district',
          id: match.district.id,
          label: match.district.name,
          detail: match.district.state,
          lat: match.district.centroid[1],
          lon: match.district.centroid[0],
          district: match.district,
        },
        score: match.score + 6,
      });
    }

    scored.sort(
      (a, b) => b.score - a.score || a.result.label.length - b.result.label.length,
    );
    return scored.slice(0, MAX_RESULTS).map((s) => s.result);
  }, [query, districts, states, nodes]);

  useEffect(() => setActive(0), [query]);

  const choose = useCallback(
    (result: SearchResult) => {
      onSelect(result);
      setQuery(result.kind === 'district' ? result.label : '');
      setOpen(false);
      inputRef.current?.blur();
    },
    [onSelect],
  );

  const onKeyDown = (ev: React.KeyboardEvent) => {
    if (ev.key === 'Escape') {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (!results.length) return;

    if (ev.key === 'ArrowDown') {
      ev.preventDefault();
      setActive((i) => (i + 1) % results.length);
    } else if (ev.key === 'ArrowUp') {
      ev.preventDefault();
      setActive((i) => (i - 1 + results.length) % results.length);
    } else if (ev.key === 'Enter') {
      ev.preventDefault();
      choose(results[active]);
    }
  };

  // "/" focuses the box from anywhere, the convention for a map search field.
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const target = ev.target as HTMLElement | null;
      const typing =
        target?.tagName === 'INPUT' ||
        target?.tagName === 'TEXTAREA' ||
        target?.isContentEditable;
      if (ev.key === '/' && !typing) {
        ev.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Close on any click outside, so the list never strands over the globe.
  useEffect(() => {
    if (!open) return;
    const onDown = (ev: PointerEvent) => {
      if (!rootRef.current?.contains(ev.target as Node)) setOpen(false);
    };
    window.addEventListener('pointerdown', onDown);
    return () => window.removeEventListener('pointerdown', onDown);
  }, [open]);

  const showList = open && (results.length > 0 || query.length > 0);

  return (
    <div ref={rootRef} className={className}>
      <div className="district-search">
        <Search className="w-3.5 h-3.5 shrink-0" style={{ color: ACCENT }} />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={
            loadError ? 'Gazetteer unavailable' : 'Search district, state, radar…'
          }
          disabled={loadError}
          spellCheck={false}
          autoComplete="off"
          aria-label="Search districts, states, radar stations and live convective cells"
          aria-expanded={showList}
          role="combobox"
          aria-controls="district-search-results"
        />
        {query ? (
          <button
            onClick={() => {
              setQuery('');
              inputRef.current?.focus();
            }}
            className="district-search__clear"
            aria-label="Clear search"
          >
            <X className="w-3 h-3" />
          </button>
        ) : (
          <kbd className="district-search__kbd">/</kbd>
        )}
      </div>

      {showList && (
        <ul id="district-search-results" role="listbox" className="district-results">
          {results.length === 0 && (
            <li className="district-results__empty">
              No match for “{query}”
            </li>
          )}
          {results.map((result, i) => {
            const { icon: Icon, label: kindLabel } = KIND_META[result.kind];
            return (
              <li key={result.id}>
                <button
                  role="option"
                  aria-selected={i === active}
                  className={`district-result ${i === active ? 'is-active' : ''}`}
                  onPointerEnter={() => setActive(i)}
                  onClick={() => choose(result)}
                >
                  <Icon
                    className="w-3.5 h-3.5 shrink-0"
                    style={{ color: result.tone ?? 'var(--color-ink-faint)' }}
                  />
                  <span className="district-result__label">{result.label}</span>
                  <span className="district-result__detail">{result.detail}</span>
                  <span className="district-result__kind">{kindLabel}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
