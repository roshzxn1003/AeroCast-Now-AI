import React, { useEffect } from 'react';
import { useNowcastStore } from './store/nowcastStore';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import { NowcastScreen } from './pages/NowcastScreen';
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
    <div className="min-h-screen bg-[#0d1117] text-[#e6edf3] flex flex-col font-sans selection:bg-sky-500/30 selection:text-sky-200">
      {/* Top Header */}
      <Header />

      {/* Main Content Viewport */}
      <main className="flex-1 overflow-y-auto">
        {activeTab === 'nowcast' && <NowcastScreen />}
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
