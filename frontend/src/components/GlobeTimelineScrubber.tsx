import React, { useEffect, useState } from 'react';
import { useNowcastStore, TIME_STEPS } from '../store/nowcastStore';
import { Play, Pause, SkipBack, SkipForward, ChevronUp, ChevronDown, Clock, Activity } from 'lucide-react';

interface GlobeTimelineScrubberProps {
  className?: string;
}

export const GlobeTimelineScrubber: React.FC<GlobeTimelineScrubberProps> = ({
  className = '',
}) => {
  const { timeIndex, setTimeIndex, isPlaying, togglePlayback, nowcastData } = useNowcastStore();
  const [collapsed, setCollapsed] = useState(false);

  // Playback timer
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setTimeIndex((timeIndex + 1) % TIME_STEPS.length);
    }, 1200);
    return () => clearInterval(interval);
  }, [isPlaying, timeIndex, setTimeIndex]);

  const currentStep = TIME_STEPS[timeIndex];

  return (
    <div
      className={`absolute bottom-16 left-1/2 -translate-x-1/2 z-25 max-w-xl w-[94%] sm:w-auto min-w-[340px] rounded-2xl bg-slate-900/92 border border-white/15 shadow-2xl backdrop-blur-xl p-2.5 sm:p-3 transition-all duration-300 ${className}`}
    >
      {/* Header Bar */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={`px-2 py-0.5 rounded-full text-[10px] font-bold font-mono uppercase tracking-wider flex items-center gap-1.5 shrink-0 ${
              currentStep.isForecast
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                : currentStep.leadTimeMin === 0
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'bg-slate-700/50 text-slate-300 border border-slate-600/40'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                currentStep.isForecast
                  ? 'bg-cyan-400 animate-pulse'
                  : currentStep.leadTimeMin === 0
                  ? 'bg-emerald-400'
                  : 'bg-slate-400'
              }`}
            />
            <span>{currentStep.isForecast ? 'AI NOWCAST' : currentStep.leadTimeMin === 0 ? 'VERIFIED NOW' : 'HISTORICAL'}</span>
          </div>

          <div className="flex items-baseline gap-1.5 truncate">
            <span className="text-xs font-bold text-white truncate">
              {currentStep.label}
            </span>
            {nowcastData?.observation_timestamp && (
              <span className="text-[10px] text-slate-400 font-mono hidden md:inline truncate">
                {currentStep.leadTimeMin === 0 ? nowcastData.observation_timestamp : ''}
              </span>
            )}
          </div>
        </div>

        {/* Controls and Collapse */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setTimeIndex(Math.max(0, timeIndex - 1))}
            disabled={timeIndex === 0}
            className="p-1 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-30 transition-colors"
            title="Step Backward 15m"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={togglePlayback}
            className={`px-2.5 py-1 rounded-lg text-xs font-bold flex items-center gap-1 transition-all ${
              isPlaying
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                : 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-md shadow-cyan-500/20'
            }`}
            title={isPlaying ? 'Pause Auto-Rollout' : 'Play Auto-Rollout'}
          >
            {isPlaying ? (
              <>
                <Pause className="w-3 h-3 fill-current" />
                <span className="hidden sm:inline text-[10px]">PAUSE</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 fill-current" />
                <span className="hidden sm:inline text-[10px]">ROLLOUT</span>
              </>
            )}
          </button>

          <button
            onClick={() => setTimeIndex(Math.min(TIME_STEPS.length - 1, timeIndex + 1))}
            disabled={timeIndex === TIME_STEPS.length - 1}
            className="p-1 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-30 transition-colors"
            title="Step Forward 15m"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setCollapsed((v) => !v)}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors ml-1"
            title={collapsed ? 'Expand Scrubber' : 'Collapse Scrubber'}
          >
            {collapsed ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Expanded Pills Bar */}
      {!collapsed && (
        <div className="mt-2.5 pt-2 border-t border-white/10">
          <div className="flex items-center justify-between gap-1 overflow-x-auto no-scrollbar py-0.5">
            {TIME_STEPS.map((step, idx) => {
              const isSelected = idx === timeIndex;
              const isNow = idx === 3;

              return (
                <button
                  key={step.index}
                  onClick={() => setTimeIndex(idx)}
                  className={`flex-1 min-w-[32px] sm:min-w-[40px] py-1 px-1 rounded-lg flex flex-col items-center gap-0.5 transition-all text-center ${
                    isSelected
                      ? step.isForecast
                        ? 'bg-cyan-500/30 text-cyan-200 border border-cyan-400 shadow-sm'
                        : 'bg-emerald-500/30 text-emerald-200 border border-emerald-400 shadow-sm'
                      : 'hover:bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-transparent'
                  }`}
                  title={step.label}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isSelected
                        ? step.isForecast
                          ? 'bg-cyan-400'
                          : 'bg-emerald-400'
                        : isNow
                        ? 'bg-emerald-500/60'
                        : step.isForecast
                        ? 'bg-cyan-700/60'
                        : 'bg-slate-600'
                    }`}
                  />
                  <span
                    className={`text-[9px] sm:text-[10px] font-mono leading-none font-semibold ${
                      isSelected ? 'font-bold' : ''
                    }`}
                  >
                    {step.shortLabel}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
