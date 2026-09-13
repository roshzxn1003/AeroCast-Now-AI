import React, { useEffect } from 'react';
import { useNowcastStore } from './store/nowcastStore';
import { CommandBar } from './components/CommandBar';
import { BottomNav } from './components/BottomNav';
import { CommandScreen } from './pages/CommandScreen';
import { AlertsScreen } from './pages/AlertsScreen';
import { StormsScreen } from './pages/StormsScreen';
import { RiskScreen } from './pages/RiskScreen';
import { MoreScreen } from './pages/MoreScreen';

export const App: React.FC = () => {
  const { activeTab, loadStations, loadNowcast } = useNowcastStore();

  useEffect(() => {
    loadStations();
    loadNowcast();
  }, [loadStations, loadNowcast]);

  return (
    <div className="min-h-[100dvh] flex flex-col">
      <CommandBar />

      <main className="flex-1 min-h-0">
        {activeTab === 'nowcast' && <CommandScreen />}
        {activeTab === 'alerts' && <AlertsScreen />}
        {activeTab === 'storms' && <StormsScreen />}
        {activeTab === 'risk' && <RiskScreen />}
        {activeTab === 'more' && <MoreScreen />}
      </main>

      {/* Fixed Bottom Navigation */}
      <BottomNav />
    </div>
  );
};

export default App;
