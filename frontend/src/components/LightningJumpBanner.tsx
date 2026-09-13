import React from 'react';
import { ArrowRight, Clock, Zap } from 'lucide-react';
import { useNowcastStore } from '../store/nowcastStore';
import { Badge, Field, Panel, ProvenanceBadge, Stat } from './ui';
import { SEVERITY_COLOR } from '../design/tokens';

/**
 * Lightning jump precursor readout.
 *
 * A sustained 2-sigma surge in total flash rate marks rapid electrification of
 * the mixed-phase layer, and reliably leads severe downbursts and ground
 * strikes by roughly 15-45 minutes. The quiet state is reported as plainly as
 * the alert state — a monitor that only ever shouts stops being read.
 */
export const LightningJumpBanner: React.FC = () => {
  const { nowcastData, setActiveTab } = useNowcastStore();

  if (!nowcastData) return null;
  const jump = nowcastData.lightning_jump;

  if (!jump.jump_detected) {
    return (
      <Panel
        title="Lightning Jump Precursor"
        action={<ProvenanceBadge provenance="MODEL" />}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: SEVERITY_COLOR.MARGINAL }}
            />
            <span className="text-[13px] text-[var(--color-ink)]">
              No surge detected
            </span>
          </div>
          <span className="text-[12px] font-mono tabular text-[var(--color-ink-muted)] shrink-0">
            {jump.sigma_metric}σ · {jump.current_rate_fpm} fpm
          </span>
        </div>
        <p className="text-[11px] text-[var(--color-ink-faint)] mt-2 leading-relaxed">
          Flash rate is within two standard deviations of its running mean.
          Threshold for alert is 2σ sustained.
        </p>
      </Panel>
    );
  }

  return (
    <Panel
      title="Lightning Jump Precursor"
      className="border-[color-mix(in_srgb,var(--color-sev-extreme)_45%,transparent)]"
      action={
        <>
          <Badge color={SEVERITY_COLOR.EXTREME}>{jump.sigma_metric}σ</Badge>
          <ProvenanceBadge provenance="MODEL" />
        </>
      }
    >
      <div className="flex items-start gap-3 mb-3">
        <div
          className="p-1.5 rounded-[6px] shrink-0"
          style={{
            background: 'color-mix(in srgb, var(--color-sev-extreme) 16%, transparent)',
          }}
        >
          <Zap className="w-4 h-4" style={{ color: SEVERITY_COLOR.EXTREME }} />
        </div>
        <div className="min-w-0">
          <div
            className="text-[13px] font-medium"
            style={{ color: SEVERITY_COLOR.EXTREME }}
          >
            Jump detected — rapid electrification
          </div>
          <p className="text-[11px] text-[var(--color-ink-muted)] leading-relaxed mt-1">
            Mixed-phase updraft intensifying. Severe downbursts, hail and
            cloud-to-ground strikes are likely within the lead window.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <Stat
          label="Lead time"
          value={`~${jump.estimated_lead_time_min}`}
          unit="min"
          tone={SEVERITY_COLOR.MODERATE}
        />
        <Stat label="Flash rate" value={jump.current_rate_fpm} unit="fpm" />
        <Stat label="Surge" value={`+${jump.dfr_dt}`} unit="fpm/5m" />
      </div>

      <Field label="Threat level" value={jump.threat_level} />
      <Field label="Status" value={jump.status} />

      <button
        onClick={() => setActiveTab('alerts')}
        className="mt-3 inline-flex items-center gap-1 text-[12px] text-[var(--color-accent)] hover:underline"
      >
        <Clock className="w-3.5 h-3.5" />
        View CAP bulletin
        <ArrowRight className="w-3 h-3" />
      </button>
    </Panel>
  );
};
