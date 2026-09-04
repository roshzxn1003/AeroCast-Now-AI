import React from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { Zap, CloudRain, Droplets, CloudFog, Flame } from 'lucide-react';

export const MetricCards: React.FC = () => {
  const { nowcastData, timeIndex } = useNowcastStore();

  if (!nowcastData) return null;

  // Active frame data based on timeIndex
  // Indices 0..3 are past (observed), 4..9 are forecast steps
  let activeMaxDbz = nowcastData.observation.max_dbz;
  let activeMaxVil = nowcastData.observation.max_vil;
  let activeMinTir = nowcastData.observation.min_tir_c;
  const activeFlash = nowcastData.observation.flash_rate_fpm;

  if (timeIndex >= 4) {
    const fcIndex = timeIndex - 4;
    const fc = nowcastData.forecast[fcIndex];
    if (fc) {
      activeMaxDbz = fc.max_dbz;
      activeMaxVil = fc.max_vil;
      activeMinTir = fc.min_tir_c;
    }
  }

  const jump = nowcastData.lightning_jump;
  const sounding = nowcastData.sounding;

  const cards = [
    {
      title: 'LIGHTNING JUMP',
      value: `${jump.threat_level.split(' ')[0]}`,
      sub: `Lead: ~${jump.estimated_lead_time_min}m (${jump.sigma_metric}σ)`,
      icon: Zap,
      color: jump.jump_detected ? 'text-red-400' : 'text-emerald-400',
      bgColor: jump.jump_detected ? 'bg-red-500/10' : 'bg-emerald-500/10',
      borderColor: jump.jump_detected ? 'border-red-500/30' : 'border-emerald-500/30',
    },
    {
      title: 'MAX REFLECTIVITY',
      value: `${activeMaxDbz.toFixed(1)} dBZ`,
      sub: activeMaxDbz >= 50 ? 'Severe Storm Core' : 'Moderate Convection',
      icon: CloudRain,
      color: activeMaxDbz >= 50 ? 'text-orange-400' : 'text-yellow-400',
      bgColor: 'bg-orange-500/10',
      borderColor: 'border-orange-500/30',
    },
    {
      title: 'VIL DENSITY',
      value: `${activeMaxVil.toFixed(1)} kg/m²`,
      sub: activeMaxVil >= 35 ? 'High Hail Potential' : 'Convective Rain',
      icon: Droplets,
      color: 'text-sky-400',
      bgColor: 'bg-sky-500/10',
      borderColor: 'border-sky-500/30',
    },
    {
      title: 'CLOUD TOP TEMP',
      value: `${activeMinTir.toFixed(1)} °C`,
      sub: activeMinTir <= -60 ? 'Overshooting Anvil' : 'High Cloud Layer',
      icon: CloudFog,
      color: 'text-purple-400',
      bgColor: 'bg-purple-500/10',
      borderColor: 'border-purple-500/30',
    },
    {
      title: 'INSTABILITY CAPE',
      value: `${sounding.CAPE_J_kg.toFixed(0)} J/kg`,
      sub: sounding.CAPE_J_kg >= 2500 ? 'Extreme Energy' : 'Moderate Instability',
      icon: Flame,
      color: 'text-amber-400',
      bgColor: 'bg-amber-500/10',
      borderColor: 'border-amber-500/30',
    },
  ];

  return (
    <div className="overflow-x-auto pb-1 -mx-3 px-3 lg:mx-0 lg:px-0 lg:overflow-visible scrollbar-none">
      <div className="flex gap-2 min-w-max lg:min-w-0 lg:grid lg:grid-cols-5 lg:gap-3">
        {cards.map((c, i) => {
          const Icon = c.icon;
          return (
            <div
              key={i}
              className={`p-2.5 rounded-xl border ${c.borderColor} ${c.bgColor} backdrop-blur-sm min-w-[130px] flex-1 flex flex-col justify-between`}
            >
              <div className="flex items-center justify-between text-[10px] font-bold tracking-wider text-slate-400 mb-1">
                <span>{c.title}</span>
                <Icon className={`w-3.5 h-3.5 ${c.color}`} />
              </div>
              <div className={`text-base font-extrabold ${c.color} leading-none my-0.5`}>
                {c.value}
              </div>
              <div className="text-[10px] text-slate-400 font-medium truncate mt-0.5">
                {c.sub}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
