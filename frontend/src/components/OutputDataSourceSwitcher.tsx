import React from 'react';
import { Radio, Brain, Layers } from 'lucide-react';
import { useNowcastStore } from '../store/nowcastStore';
import { OutputDataSource } from '../types/nowcast';

interface OutputDataSourceSwitcherProps {
  value?: OutputDataSource;
  onChange?: (source: OutputDataSource) => void;
  size?: 'xs' | 'sm' | 'md';
  compact?: boolean;
  className?: string;
  showLabels?: boolean;
}

export const OutputDataSourceSwitcher: React.FC<OutputDataSourceSwitcherProps> = ({
  value,
  onChange,
  size = 'sm',
  compact = false,
  className = '',
  showLabels = true,
}) => {
  const globalSource = useNowcastStore((s) => s.outputDataSource);
  const setGlobalSource = useNowcastStore((s) => s.setOutputDataSource);

  const activeSource = value ?? globalSource;
  const handleChange = onChange ?? setGlobalSource;

  const sizeClasses = {
    xs: 'text-[10px] p-0.5 gap-0.5',
    sm: 'text-xs p-0.5 gap-1',
    md: 'text-xs sm:text-sm p-1 gap-1.5',
  };

  const btnPadding = {
    xs: 'px-1.5 py-0.5',
    sm: 'px-2.5 py-1',
    md: 'px-3 py-1.5',
  };

  const iconSize = {
    xs: 'w-2.5 h-2.5',
    sm: 'w-3.5 h-3.5',
    md: 'w-4 h-4',
  };

  return (
    <div
      role="group"
      aria-label="Output Data Source Switcher (Live vs Model vs All)"
      className={`inline-flex items-center rounded-xl bg-slate-900/90 border border-white/10 backdrop-blur-md shadow-lg ${sizeClasses[size]} ${className}`}
    >
      {/* ALL (HYBRID) BUTTON */}
      <button
        type="button"
        onClick={() => handleChange('all')}
        aria-pressed={activeSource === 'all'}
        title="Show All Outputs: Combined live sensor observations and AI model predictions"
        className={`flex items-center gap-1.5 rounded-lg font-mono font-medium transition-all ${btnPadding[size]} ${
          activeSource === 'all'
            ? 'bg-slate-800/95 text-white font-bold shadow-md border border-white/20'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
        }`}
      >
        <Layers className={`${iconSize[size]} ${activeSource === 'all' ? 'text-cyan-400' : 'text-slate-400'}`} />
        {showLabels && (
          <span>{compact ? 'All' : 'All Data'}</span>
        )}
      </button>

      {/* LIVE (OBSERVED SENSORS) BUTTON */}
      <button
        type="button"
        onClick={() => handleChange('live')}
        aria-pressed={activeSource === 'live'}
        title="Live Observations Only: Real-time ground weather sensors, Doppler radar reflectivities, and Blitzortung lightning strikes"
        className={`flex items-center gap-1.5 rounded-lg font-mono font-medium transition-all ${btnPadding[size]} ${
          activeSource === 'live'
            ? 'bg-emerald-500/20 text-emerald-300 font-bold shadow-md border border-emerald-500/50'
            : 'text-slate-400 hover:text-emerald-300 hover:bg-emerald-950/30'
        }`}
      >
        <span className="relative flex h-2 w-2 items-center justify-center">
          {activeSource === 'live' && (
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          )}
          <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${activeSource === 'live' ? 'bg-emerald-400' : 'bg-emerald-600'}`} />
        </span>
        <Radio className={iconSize[size]} />
        {showLabels && (
          <span>{compact ? 'Live' : 'Live Obs'}</span>
        )}
      </button>

      {/* MODEL (AI NOWCAST & PREDICTIONS) BUTTON */}
      <button
        type="button"
        onClick={() => handleChange('model')}
        aria-pressed={activeSource === 'model'}
        title="AI Model Outputs Only: ConvLSTM2D nowcasting grids, 2σ lightning jump ML alerts, and 120-hour outlooks"
        className={`flex items-center gap-1.5 rounded-lg font-mono font-medium transition-all ${btnPadding[size]} ${
          activeSource === 'model'
            ? 'bg-purple-500/20 text-purple-300 font-bold shadow-md border border-purple-500/50'
            : 'text-slate-400 hover:text-purple-300 hover:bg-purple-950/30'
        }`}
      >
        <Brain className={`${iconSize[size]} ${activeSource === 'model' ? 'text-purple-400' : 'text-slate-400'}`} />
        {showLabels && (
          <span>{compact ? 'Model' : 'AI Model'}</span>
        )}
      </button>
    </div>
  );
};
