import React from 'react';
import { useNowcastStore } from '../store/nowcastStore';
import { ActiveTab } from '../types/nowcast';
import {
  Radar,
  AlertTriangle,
  Activity,
  ShieldAlert,
  Menu,
} from 'lucide-react';

export const BottomNav: React.FC = () => {
  const { activeTab, setActiveTab, nowcastData, uiMode } = useNowcastStore();

  const hasJump = nowcastData?.lightning_jump?.jump_detected;
  const activeCellsCount = nowcastData?.observation?.storm_cells?.length || 0;

  const tabs: { id: ActiveTab; label: string; icon: React.ComponentType<{ className?: string }>; badge?: string | number; badgeColor?: string }[] = [
    {
      id: 'nowcast',
      label: uiMode === 'citizen' ? 'EARTH' : 'NOWCAST',
      icon: Radar,
    },
    {
      id: 'alerts',
      label: uiMode === 'citizen' ? 'WARNINGS' : 'ALERTS',
      icon: AlertTriangle,
      badge: hasJump ? 'JUMP' : undefined,
      badgeColor: 'bg-red-500 text-white animate-pulse',
    },
    {
      id: 'storms',
      label: uiMode === 'citizen' ? 'RADAR' : 'STORMS',
      icon: Activity,
      badge: activeCellsCount > 0 ? activeCellsCount : undefined,
      badgeColor: 'bg-amber-500 text-[#06080b]',
    },
    {
      id: 'risk',
      label: uiMode === 'citizen' ? 'SAFETY' : 'RISK',
      icon: ShieldAlert,
    },
    {
      id: 'more',
      label: uiMode === 'citizen' ? 'ABOUT' : 'MORE',
      icon: Menu,
    },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-[var(--color-surface-void)]/95 backdrop-blur-lg border-t border-[var(--color-line)] bottom-nav lg:hidden">
      <div className="max-w-md mx-auto grid grid-cols-5 px-1 py-1">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex flex-col items-center justify-center py-2 px-1 rounded-[10px] transition-all duration-200 ${
                isActive
                  ? 'text-[var(--color-accent)] font-bold'
                  : 'text-[var(--color-ink-muted)] hover:text-[var(--color-ink)] font-medium'
              }`}
            >
              {/* Active indicator dot/glow */}
              {isActive && (
                <span className="absolute top-1 w-6 h-0.5 rounded-full bg-sky-400 shadow-sm shadow-sky-400" />
              )}

              <div className="relative mt-0.5">
                <Icon
                  className={`w-5 h-5 transition-transform ${
                    isActive ? 'scale-110 text-[var(--color-accent)]' : 'text-[var(--color-ink-muted)]'
                  }`}
                />
                {tab.badge && (
                  <span
                    className={`absolute -top-1 -right-2 text-[11px] font-semibold px-1 rounded-full leading-tight shadow ${tab.badgeColor}`}
                  >
                    {tab.badge}
                  </span>
                )}
              </div>

              <span className="text-[11px] tracking-wider mt-1 font-mono">
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
