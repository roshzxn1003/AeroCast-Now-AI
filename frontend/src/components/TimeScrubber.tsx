import React, { useEffect } from 'react';
import { useNowcastStore, TIME_STEPS } from '../store/nowcastStore';
import { Play, Pause, SkipBack, SkipForward, Clock } from 'lucide-react';

export const TimeScrubber: React.FC = () => {
  const { timeIndex, setTimeIndex, isPlaying, togglePlayback } = useNowcastStore();

  // Animation playback loop
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setTimeIndex((timeIndex + 1) % TIME_STEPS.length);
    }, 1400);
    return () => clearInterval(interval);
  }, [isPlaying, timeIndex, setTimeIndex]);

  const currentStep = TIME_STEPS[timeIndex];

  return (
    <div className="bg-[#161b22]/90 border border-white/10 rounded-xl p-3 space-y-2 backdrop-blur-md">
      {/* Top Header: Step Label & Playback Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className={`px-2 py-0.5 rounded-md text-[11px] font-extrabold font-mono ${
              currentStep.isForecast
                ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            }`}
          >
            {currentStep.isForecast ? '⚡ AI NOWCAST' : '📡 OBSERVED'}
          </div>
          <span className="text-xs font-bold text-slate-200">
            {currentStep.label}
          </span>
        </div>

        {/* Transport buttons */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setTimeIndex(Math.max(0, timeIndex - 1))}
            disabled={timeIndex === 0}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 text-slate-300 transition-colors"
            title="Step Back"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={togglePlayback}
            className={`p-1.5 rounded-lg transition-colors ${
              isPlaying
                ? 'bg-amber-500 text-slate-900 font-bold'
                : 'bg-sky-500 hover:bg-sky-400 text-white'
            }`}
            title={isPlaying ? 'Pause' : 'Play Sequence'}
          >
            {isPlaying ? (
              <Pause className="w-3.5 h-3.5" />
            ) : (
              <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
            )}
          </button>

          <button
            onClick={() => setTimeIndex(Math.min(TIME_STEPS.length - 1, timeIndex + 1))}
            disabled={timeIndex === TIME_STEPS.length - 1}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 text-slate-300 transition-colors"
            title="Step Forward"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Progress Slider */}
      <div className="relative pt-1">
        <input
          type="range"
          min={0}
          max={TIME_STEPS.length - 1}
          value={timeIndex}
          onChange={(e) => setTimeIndex(Number(e.target.value))}
          className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400"
        />

        {/* Step Ticks Bar */}
        <div className="flex justify-between items-center px-0.5 mt-1">
          {TIME_STEPS.map((step, idx) => {
            const isSelected = idx === timeIndex;
            const isNow = idx === 3;

            return (
              <button
                key={step.index}
                onClick={() => setTimeIndex(idx)}
                className={`flex flex-col items-center group transition-all`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full mb-0.5 transition-all ${
                    isSelected
                      ? 'w-2 h-2 bg-sky-400 ring-2 ring-sky-400/50'
                      : isNow
                      ? 'bg-emerald-400'
                      : step.isForecast
                      ? 'bg-slate-600 group-hover:bg-slate-400'
                      : 'bg-slate-500 group-hover:bg-slate-400'
                  }`}
                />
                <span
                  className={`text-[9px] font-mono leading-none ${
                    isSelected
                      ? 'text-sky-400 font-extrabold scale-110'
                      : isNow
                      ? 'text-emerald-400 font-bold'
                      : 'text-slate-500'
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
