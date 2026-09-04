import React, { useEffect } from 'react';
import { useNowcastStore, TIME_STEPS } from '../store/nowcastStore';
import { Play, Pause, SkipBack, SkipForward, Clock, Repeat } from 'lucide-react';

export const TimeScrubber: React.FC = () => {
  const { timeIndex, setTimeIndex, isPlaying, togglePlayback } = useNowcastStore();

  // Animation playback loop
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setTimeIndex((timeIndex + 1) % TIME_STEPS.length);
    }, 1300);
    return () => clearInterval(interval);
  }, [isPlaying, timeIndex, setTimeIndex]);

  const currentStep = TIME_STEPS[timeIndex];

  return (
    <div className="bg-[#161b22]/95 border border-white/10 rounded-2xl p-3 lg:p-4 space-y-3 backdrop-blur-md shadow-xl">
      {/* Top Header: Step Status & Transport Controls */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div
            className={`px-2.5 py-1 rounded-lg text-xs font-black font-mono flex items-center gap-1.5 shadow-sm ${
              currentStep.isForecast
                ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40'
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                currentStep.isForecast ? 'bg-sky-400 animate-pulse' : 'bg-emerald-400'
              }`}
            />
            <span>{currentStep.isForecast ? 'CONVLSTM ROLLOUT' : 'OBSERVED DWR'}</span>
          </div>

          <div className="flex flex-col">
            <span className="text-xs lg:text-sm font-bold text-slate-100">
              {currentStep.label}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">
              {currentStep.isForecast
                ? `Forecast Horizon: +${currentStep.leadTimeMin} min`
                : currentStep.leadTimeMin === 0
                ? 'Current Verification Baseline (t=0)'
                : `Historical Archive: ${currentStep.leadTimeMin} min`}
            </span>
          </div>
        </div>

        {/* Transport buttons */}
        <div className="flex items-center gap-1.5 bg-black/40 p-1 rounded-xl border border-white/10">
          <button
            onClick={() => setTimeIndex(Math.max(0, timeIndex - 1))}
            disabled={timeIndex === 0}
            className="p-2 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-25 text-slate-300 transition-colors"
            title="Step Back 15 Min"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={togglePlayback}
            className={`p-2 rounded-lg transition-all flex items-center justify-center ${
              isPlaying
                ? 'bg-amber-500 text-slate-950 font-black shadow-lg shadow-amber-500/30'
                : 'bg-sky-500 hover:bg-sky-400 text-white shadow-lg shadow-sky-500/30'
            }`}
            title={isPlaying ? 'Pause Timeline' : 'Play Auto-Regressive Rollout'}
          >
            {isPlaying ? (
              <Pause className="w-4 h-4" />
            ) : (
              <Play className="w-4 h-4 fill-current ml-0.5" />
            )}
          </button>

          <button
            onClick={() => setTimeIndex(Math.min(TIME_STEPS.length - 1, timeIndex + 1))}
            disabled={timeIndex === TIME_STEPS.length - 1}
            className="p-2 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-25 text-slate-300 transition-colors"
            title="Step Forward 15 Min"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Progress Range Slider */}
      <div className="relative pt-1 px-1">
        <input
          type="range"
          min={0}
          max={TIME_STEPS.length - 1}
          value={timeIndex}
          onChange={(e) => setTimeIndex(Number(e.target.value))}
          className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-400 hover:accent-sky-300 transition-all"
        />

        {/* Step Ticks Bar with Clear Division */}
        <div className="flex justify-between items-center px-1 mt-2">
          {TIME_STEPS.map((step, idx) => {
            const isSelected = idx === timeIndex;
            const isNow = idx === 3;

            return (
              <button
                key={step.index}
                onClick={() => setTimeIndex(idx)}
                className="flex flex-col items-center group transition-all"
              >
                <span
                  className={`rounded-full mb-1 transition-all ${
                    isSelected
                      ? 'w-2.5 h-2.5 bg-sky-400 ring-4 ring-sky-400/30 scale-125'
                      : isNow
                      ? 'w-2 h-2 bg-emerald-400 shadow-sm shadow-emerald-400'
                      : step.isForecast
                      ? 'w-1.5 h-1.5 bg-slate-600 group-hover:bg-slate-400'
                      : 'w-1.5 h-1.5 bg-slate-500 group-hover:bg-slate-400'
                  }`}
                />
                <span
                  className={`text-[10px] font-mono leading-none ${
                    isSelected
                      ? 'text-sky-400 font-black scale-110'
                      : isNow
                      ? 'text-emerald-400 font-bold'
                      : 'text-slate-500 group-hover:text-slate-300'
                  }`}
                >
                  {step.shortLabel}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
