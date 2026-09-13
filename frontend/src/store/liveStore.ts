import { create } from 'zustand';
import {
  ConvectiveField,
  ConvectiveNode,
  DomainSummary,
  LightningField,
  NetworkStatus,
} from '../types/nowcast';
import {
  fetchConvectiveField,
  fetchDomainSummary,
  fetchLightningField,
  fetchNetworkStatus,
} from '../services/api';

/**
 * Live observation state for the globe.
 *
 * Poll cadences are matched to how fast each upstream actually changes, rather
 * than to a single arbitrary timer: the lightning field turns over in seconds,
 * the convective analysis is regenerated on a quarter-hour model cycle.
 */
const STRIKE_POLL_MS = 20_000;
const CONVECTIVE_POLL_MS = 300_000;
const STATUS_POLL_MS = 60_000;

interface LiveState {
  summary: DomainSummary | null;
  convective: ConvectiveField | null;
  lightning: LightningField | null;
  network: NetworkStatus | null;

  /** Node the operator has drilled into, driving the detail panels. */
  focusedNode: ConvectiveNode | null;

  isLoading: boolean;
  lastError: string | null;
  lastUpdated: string | null;

  setFocusedNode: (node: ConvectiveNode | null) => void;
  refreshAll: () => Promise<void>;
  refreshStrikes: () => Promise<void>;
  startPolling: () => () => void;
}

export const useLiveStore = create<LiveState>((set, get) => ({
  summary: null,
  convective: null,
  lightning: null,
  network: null,
  focusedNode: null,
  isLoading: false,
  lastError: null,
  lastUpdated: null,

  setFocusedNode: (node) => set({ focusedNode: node }),

  refreshStrikes: async () => {
    try {
      const lightning = await fetchLightningField(30, 3000);
      set({ lightning, lastUpdated: new Date().toISOString(), lastError: null });
    } catch (err) {
      set({ lastError: (err as Error).message });
    }
  },

  refreshAll: async () => {
    set({ isLoading: true });
    // Settled rather than all-or-nothing: one dead provider must not blank the
    // panels that are still receiving data.
    const [summary, convective, lightning, network] = await Promise.allSettled([
      fetchDomainSummary(),
      fetchConvectiveField(),
      fetchLightningField(30, 3000),
      fetchNetworkStatus(),
    ]);

    const failures: string[] = [];
    const next: Partial<LiveState> = {
      isLoading: false,
      lastUpdated: new Date().toISOString(),
    };

    if (summary.status === 'fulfilled') next.summary = summary.value;
    else failures.push('summary');

    if (convective.status === 'fulfilled') next.convective = convective.value;
    else failures.push('convective');

    if (lightning.status === 'fulfilled') next.lightning = lightning.value;
    else failures.push('lightning');

    if (network.status === 'fulfilled') next.network = network.value;
    else failures.push('network');

    next.lastError = failures.length
      ? `Provider unreachable: ${failures.join(', ')}`
      : null;

    set(next as LiveState);
  },

  startPolling: () => {
    const { refreshAll, refreshStrikes } = get();
    void refreshAll();

    const strikeTimer = setInterval(() => void refreshStrikes(), STRIKE_POLL_MS);
    const convectiveTimer = setInterval(() => {
      void fetchConvectiveField()
        .then((convective) => set({ convective }))
        .catch(() => undefined);
      void fetchDomainSummary()
        .then((summary) => set({ summary }))
        .catch(() => undefined);
    }, CONVECTIVE_POLL_MS);
    const statusTimer = setInterval(() => {
      void fetchNetworkStatus()
        .then((network) => set({ network }))
        .catch(() => undefined);
    }, STATUS_POLL_MS);

    return () => {
      clearInterval(strikeTimer);
      clearInterval(convectiveTimer);
      clearInterval(statusTimer);
    };
  },
}));
