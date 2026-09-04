import React from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { Zap, AlertOctagon, Clock, ArrowRight } from 'lucide-react';

export const LightningJumpBanner: React.FC = () => {
  const { nowcastData, setActiveTab } = useNowcastStore();

  if (!nowcastData) return null;

  const jump = nowcastData.lightning_jump;

  if (!jump.jump_detected) {
    return (
      <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-2.5 flex items-center justify-between text-xs text-emerald-300">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="font-semibold">Normal Convective State</span>
          <span className="text-emerald-400/70 text-[11px] font-mono">
            ({jump.sigma_metric}σ • {jump.current_rate_fpm} fpm)
          </span>
        </div>
        <span className="text-[10px] text-slate-400">No Surge</span>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-r from-red-500/20 via-orange-500/20 to-red-500/20 border border-red-500/40 rounded-xl p-3 shadow-lg shadow-red-950/40 alert-pulse space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-red-500/30 text-red-300">
            <Zap className="w-4 h-4 animate-bounce" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-black tracking-wide text-red-200">
                CRITICAL LIGHTNING JUMP
              </span>
              <span className="bg-red-500 text-white text-[9px] font-black px-1.5 py-0.2 rounded-full">
                {jump.sigma_metric}σ
              </span>
            </div>
            <div className="text-[11px] text-red-300/90 font-medium">
              Rate surge +{jump.dfr_dt} fpm/5min
            </div>
          </div>
        </div>

        {/* Lead time pill */}
        <div className="flex items-center gap-1 bg-red-900/60 border border-red-500/40 px-2 py-1 rounded-lg text-amber-300 text-xs font-bold shrink-0">
          <Clock className="w-3.5 h-3.5 text-amber-400" />
          <span>~{jump.estimated_lead_time_min}m LEAD</span>
        </div>
      </div>

      <p className="text-[11px] text-slate-300 leading-snug">
        Rapid storm electrification in mixed-phase layer. Severe downbursts, hail, and cloud-to-ground strikes imminent.
      </p>

      <div className="flex items-center justify-between pt-1 border-t border-red-500/20 text-[10px]">
        <span className="text-red-300/80 font-mono">
          Current Flash Rate: {jump.current_rate_fpm} flashes/min
        </span>
        <button
          onClick={() => setActiveTab('alerts')}
          className="text-amber-300 font-bold hover:underline flex items-center gap-0.5"
        >
          View Bulletin
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
};
