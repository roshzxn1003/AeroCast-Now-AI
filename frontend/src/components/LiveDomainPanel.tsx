import React, { useMemo } from 'react';
import { CloudLightning, Radio, Wifi, WifiOff } from 'lucide-react';
import { useLiveStore } from '../store/liveStore';
import { Badge, EmptyState, Field, Loading, Meter, Panel, ProvenanceBadge, Stat } from './ui';
import { FLASH, severityColor } from '../design/tokens';
import { ConvectiveNode } from '../types/nowcast';

/**
 * Live domain readout: what the observation networks are reporting right now,
 * independent of anything the model predicts.
 */
export const LiveDomainPanel: React.FC = () => {
  const summary = useLiveStore((s) => s.summary);
  const convective = useLiveStore((s) => s.convective);
  const lightning = useLiveStore((s) => s.lightning);
  const focusedNode = useLiveStore((s) => s.focusedNode);
  const setFocusedNode = useLiveStore((s) => s.setFocusedNode);

  /** Rank by convective vigour so the worst environment is always on top. */
  const ranked = useMemo(
    () =>
      [...(convective?.nodes ?? [])]
        .sort((a, b) => b.intensity - a.intensity)
        .slice(0, 8),
    [convective],
  );

  if (!summary) {
    return (
      <Panel title="Live Domain">
        <Loading label="Contacting observation networks" />
      </Panel>
    );
  }

  return (
    <Panel
      title="Live Domain"
      subtitle={`Updated ${new Date(summary.retrieved_at).toLocaleTimeString()}`}
      action={<ProvenanceBadge provenance={summary.convective_status} />}
      bodyClassName="space-y-4 overflow-y-auto"
    >
      {/* Headline lightning figures */}
      <div className="grid grid-cols-3 gap-3">
        <Stat
          label="Flashes 30m"
          value={summary.strike_count_30min.toLocaleString()}
          tone={FLASH.cg}
        />
        <Stat label="Rate" value={summary.flash_rate_per_min} unit="/min" />
        <Stat
          label="Max CAPE"
          value={summary.max_cape_j_kg.toFixed(0)}
          unit="J/kg"
          tone={severityColor(summary.most_unstable?.instability ?? 'STABLE')}
        />
      </div>

      {lightning && (
        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="flex items-center gap-1.5 text-[var(--color-ink-muted)]">
            <span className="w-2 h-2 rounded-full" style={{ background: FLASH.cg }} />
            {lightning.cg_count.toLocaleString()} CG
          </span>
          <span className="flex items-center gap-1.5 text-[var(--color-ink-muted)]">
            <span className="w-2 h-2 rounded-full" style={{ background: FLASH.ic }} />
            {lightning.ic_count.toLocaleString()} IC
          </span>
          <ProvenanceBadge provenance={lightning.status} />
        </div>
      )}

      {lightning?.status === 'LIVE-DERIVED' && (
        <p className="text-[11px] text-[var(--color-ink-faint)] leading-relaxed border-l-2 pl-2.5 border-[var(--color-sev-moderate)]">
          {lightning.note}
        </p>
      )}

      {/* Most unstable environments */}
      <div>
        <h3 className="eyebrow mb-2">Most unstable environments</h3>
        {ranked.length === 0 ? (
          <EmptyState
            title="No convective analysis available"
            detail="The upstream provider did not return sounding data."
          />
        ) : (
          <ul className="space-y-1">
            {ranked.map((node) => (
              <NodeRow
                key={node.name}
                node={node}
                selected={focusedNode?.name === node.name}
                onSelect={() => setFocusedNode(node)}
              />
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
};

const NodeRow: React.FC<{
  node: ConvectiveNode;
  selected: boolean;
  onSelect: () => void;
}> = ({ node, selected, onSelect }) => {
  const tone = severityColor(node.instability);
  return (
    <li>
      <button
        onClick={onSelect}
        aria-pressed={selected}
        className={`w-full text-left rounded-[6px] px-2.5 py-2 border transition-colors ${
          selected
            ? 'border-[var(--color-accent-line)] bg-[var(--color-accent-dim)]'
            : 'border-transparent hover:bg-[var(--color-surface-raised)]'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 min-w-0">
            {node.thunderstorm_observed && (
              <CloudLightning
                className="w-3.5 h-3.5 shrink-0"
                style={{ color: FLASH.cg }}
                aria-label="Thunderstorm observed at surface"
              />
            )}
            <span className="text-[13px] truncate">{node.name}</span>
          </span>
          <span
            className="text-[12px] font-mono tabular shrink-0"
            style={{ color: tone }}
          >
            {node.cape_j_kg.toFixed(0)}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-1.5">
          <Meter value={node.intensity} color={tone} className="flex-1" />
          <span className="text-[10px] font-mono text-[var(--color-ink-faint)] shrink-0">
            LI {node.lifted_index_c.toFixed(1)}
          </span>
        </div>
      </button>
    </li>
  );
};

/**
 * Upstream provider health. Shown plainly so a viewer can see exactly which
 * networks are feeding the display at any moment.
 */
export const NetworkStatusPanel: React.FC = () => {
  const network = useLiveStore((s) => s.network);

  if (!network) {
    return (
      <Panel title="Observation Networks">
        <Loading label="Polling providers" />
      </Panel>
    );
  }

  return (
    <Panel title="Observation Networks" bodyClassName="space-y-2.5">
      {network.providers.map((p) => (
        <div key={p.id}>
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 min-w-0">
              {p.connected ? (
                <Wifi
                  className="w-3.5 h-3.5 shrink-0"
                  style={{ color: 'var(--color-prov-live)' }}
                />
              ) : (
                <WifiOff
                  className="w-3.5 h-3.5 shrink-0"
                  style={{ color: 'var(--color-sev-extreme)' }}
                />
              )}
              <span className="text-[12px] truncate">{p.name}</span>
            </span>
            <ProvenanceBadge
              provenance={p.status ?? (p.connected ? 'LIVE' : 'UNAVAILABLE')}
            />
          </div>
          <p className="text-[11px] text-[var(--color-ink-faint)] ml-5 mt-0.5">
            {p.role}
          </p>
          {p.id === 'ldn' && !p.connected && p.last_error && (
            <p className="text-[10px] font-mono text-[var(--color-ink-faint)] ml-5 mt-1">
              {p.last_error} — falling back to derived field
            </p>
          )}
        </div>
      ))}
    </Panel>
  );
};

/** Detail readout for whichever node the operator has selected on the globe. */
export const NodeDetailPanel: React.FC = () => {
  const node = useLiveStore((s) => s.focusedNode);

  if (!node) {
    return (
      <Panel title="Node Detail">
        <EmptyState
          title="No node selected"
          detail="Select a point on the globe to inspect its live sounding."
        />
      </Panel>
    );
  }

  const tone = severityColor(node.instability);

  return (
    <Panel
      title={node.name}
      subtitle={node.region}
      action={
        <>
          <Badge color={tone}>{node.instability}</Badge>
          <ProvenanceBadge provenance={node.source} />
        </>
      }
    >
      <div className="grid grid-cols-3 gap-3 mb-3">
        <Stat label="CAPE" value={node.cape_j_kg.toFixed(0)} unit="J/kg" tone={tone} />
        <Stat label="Lifted Index" value={node.lifted_index_c.toFixed(1)} unit="°C" />
        <Stat label="CIN" value={node.cin_j_kg.toFixed(0)} unit="J/kg" />
      </div>

      <Field label="Surface temperature" value={`${node.temperature_c} °C`} />
      <Field label="Cloud cover" value={`${node.cloud_cover_pct} %`} />
      <Field
        label="Wind"
        value={`${node.wind_speed_kmh} km/h @ ${node.wind_direction_deg}°`}
      />
      <Field label="Precipitation probability" value={`${node.precipitation_probability} %`} />
      <Field
        label="Thunderstorm observed"
        value={node.thunderstorm_observed ? `Yes (WMO ${node.weather_code})` : 'No'}
        tone={node.thunderstorm_observed ? FLASH.cg : undefined}
      />

      <p className="text-[10px] text-[var(--color-ink-faint)] font-mono mt-3 flex items-center gap-1.5">
        <Radio className="w-3 h-3" />
        {node.provider}
      </p>
    </Panel>
  );
};
