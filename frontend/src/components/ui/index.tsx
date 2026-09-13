/**
 * UI primitives.
 *
 * Every surface in the app is built from these. The previous build repeated
 * `bg-[#161b22] border border-white/10 rounded-xl` inline roughly forty times,
 * which is why nothing stayed consistent; container styling now has exactly one
 * definition.
 */

import React from 'react';
import clsx from 'clsx';
import { PROVENANCE, Provenance, severityColor } from '../../design/tokens';

// -----------------------------------------------------------------------------
// Panel
// -----------------------------------------------------------------------------

interface PanelProps {
  title?: string;
  /** Right-aligned slot in the header: status, counts, controls. */
  action?: React.ReactNode;
  /** Small text under the title, for units or method notes. */
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  /** Drop body padding when the child manages its own (canvas, tables). */
  flush?: boolean;
}

export const Panel: React.FC<PanelProps> = ({
  title,
  action,
  subtitle,
  children,
  className,
  bodyClassName,
  flush = false,
}) => (
  <section className={clsx('panel flex flex-col min-h-0', className)}>
    {(title || action) && (
      <header className="panel-header shrink-0">
        <div className="min-w-0">
          {title && <h2 className="panel-title truncate">{title}</h2>}
          {subtitle && (
            <p className="text-[11px] text-[var(--color-ink-faint)] mt-0.5 truncate">
              {subtitle}
            </p>
          )}
        </div>
        {action && <div className="shrink-0 flex items-center gap-2">{action}</div>}
      </header>
    )}
    <div className={clsx('min-h-0 flex-1', !flush && 'p-3.5', bodyClassName)}>
      {children}
    </div>
  </section>
);

// -----------------------------------------------------------------------------
// Stat — a single labelled reading
// -----------------------------------------------------------------------------

interface StatProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  /** Qualifier under the value: a category, trend or threshold note. */
  note?: string;
  /** Tints the value only. Labels stay grey so colour keeps one meaning. */
  tone?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const STAT_SIZE = {
  sm: 'text-[13px]',
  md: 'text-[22px] leading-none',
  lg: 'text-[32px] leading-none',
} as const;

export const Stat: React.FC<StatProps> = ({
  label,
  value,
  unit,
  note,
  tone,
  size = 'md',
  className,
}) => (
  <div className={clsx('min-w-0', className)}>
    <div className="eyebrow truncate">{label}</div>
    <div className="flex items-baseline gap-1 mt-1">
      <span
        className={clsx('font-mono font-medium tabular truncate', STAT_SIZE[size])}
        style={{ color: tone ?? 'var(--color-ink)' }}
      >
        {value}
      </span>
      {unit && (
        <span className="text-[11px] text-[var(--color-ink-faint)] font-mono shrink-0">
          {unit}
        </span>
      )}
    </div>
    {note && (
      <div className="text-[11px] text-[var(--color-ink-faint)] mt-0.5 truncate">
        {note}
      </div>
    )}
  </div>
);

// -----------------------------------------------------------------------------
// Badge
// -----------------------------------------------------------------------------

interface BadgeProps {
  children: React.ReactNode;
  /** Any CSS colour. Rendered as tinted text on a 12%-alpha wash of itself. */
  color?: string;
  title?: string;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ children, color, title, className }) => {
  const tint = color ?? 'var(--color-ink-muted)';
  return (
    <span
      title={title}
      className={clsx(
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-mono font-medium',
        'text-[10px] tracking-[0.08em] uppercase whitespace-nowrap border',
        className,
      )}
      style={{
        color: tint,
        borderColor: color ? `color-mix(in srgb, ${color} 34%, transparent)` : 'var(--color-line)',
        background: color ? `color-mix(in srgb, ${color} 12%, transparent)` : 'transparent',
      }}
    >
      {children}
    </span>
  );
};

// -----------------------------------------------------------------------------
// ProvenanceBadge — states where a number came from
// -----------------------------------------------------------------------------

export const ProvenanceBadge: React.FC<{ provenance: string; className?: string }> = ({
  provenance,
  className,
}) => {
  const meta = PROVENANCE[provenance as Provenance] ?? PROVENANCE.MODEL;
  return (
    <Badge color={meta.color} title={meta.description} className={className}>
      {provenance === 'LIVE' && (
        <span
          className="live-dot w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: meta.color }}
        />
      )}
      {meta.label}
    </Badge>
  );
};

// -----------------------------------------------------------------------------
// SeverityTag
// -----------------------------------------------------------------------------

export const SeverityTag: React.FC<{ level: string; className?: string }> = ({
  level,
  className,
}) => (
  <Badge color={severityColor(level)} className={className}>
    {level}
  </Badge>
);

// -----------------------------------------------------------------------------
// Button
// -----------------------------------------------------------------------------

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'outline';
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'ghost',
  size = 'sm',
  icon,
  children,
  className,
  ...rest
}) => (
  <button
    {...rest}
    className={clsx(
      'inline-flex items-center justify-center gap-1.5 rounded-[6px] font-medium',
      'transition-colors disabled:opacity-45 disabled:cursor-not-allowed',
      size === 'sm' ? 'px-2.5 py-1.5 text-[12px]' : 'px-3.5 py-2 text-[13px]',
      variant === 'primary' &&
        'bg-[var(--color-accent)] text-[#04202e] hover:brightness-110 font-semibold',
      variant === 'outline' &&
        'border border-[var(--color-accent-line)] text-[var(--color-accent)] hover:bg-[var(--color-accent-dim)]',
      variant === 'ghost' &&
        'border border-[var(--color-line)] text-[var(--color-ink-muted)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface-overlay)]',
      className,
    )}
  >
    {icon}
    {children}
  </button>
);

// -----------------------------------------------------------------------------
// Field — one row of a key/value readout table
// -----------------------------------------------------------------------------

export const Field: React.FC<{
  label: string;
  value: React.ReactNode;
  tone?: string;
}> = ({ label, value, tone }) => (
  <div className="flex items-baseline justify-between gap-3 py-1.5 border-b border-[var(--color-line-faint)] last:border-0">
    <span className="text-[12px] text-[var(--color-ink-faint)] truncate">{label}</span>
    <span
      className="text-[12px] font-mono tabular text-right shrink-0"
      style={{ color: tone ?? 'var(--color-ink)' }}
    >
      {value}
    </span>
  </div>
);

// -----------------------------------------------------------------------------
// Meter — proportional bar for a 0..1 index
// -----------------------------------------------------------------------------

export const Meter: React.FC<{
  value: number;
  color?: string;
  className?: string;
}> = ({ value, color, className }) => (
  <div
    className={clsx('h-1 rounded-full bg-white/8 overflow-hidden', className)}
    role="presentation"
  >
    <div
      className="h-full rounded-full transition-[width] duration-500"
      style={{
        width: `${Math.max(0, Math.min(1, value)) * 100}%`,
        background: color ?? 'var(--color-accent)',
      }}
    />
  </div>
);

// -----------------------------------------------------------------------------
// EmptyState / Loading
// -----------------------------------------------------------------------------

export const Loading: React.FC<{ label?: string; className?: string }> = ({
  label = 'Acquiring observations',
  className,
}) => (
  <div
    className={clsx(
      'flex flex-col items-center justify-center gap-3 py-10 text-center',
      className,
    )}
  >
    <div className="flex gap-1" aria-hidden>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1 h-4 rounded-full bg-[var(--color-accent)] live-dot"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </div>
    <p className="text-[12px] text-[var(--color-ink-faint)] font-mono">{label}</p>
  </div>
);

export const EmptyState: React.FC<{ title: string; detail?: string }> = ({
  title,
  detail,
}) => (
  <div className="py-8 text-center">
    <p className="text-[13px] text-[var(--color-ink-muted)]">{title}</p>
    {detail && (
      <p className="text-[11px] text-[var(--color-ink-faint)] mt-1 max-w-xs mx-auto">
        {detail}
      </p>
    )}
  </div>
);
