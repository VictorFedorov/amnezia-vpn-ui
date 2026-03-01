import { create } from 'zustand';

interface RealtimeAlert {
  type: string;
  config_id?: number;
  reason?: string;
  timestamp?: string;
}

interface RealtimeState {
  connected: boolean;
  lastUpdate: number;
  alerts: RealtimeAlert[];
  ws: WebSocket | null;
  connect: () => void;
  disconnect: () => void;
  clearAlerts: () => void;
}

const WS_RECONNECT_DELAY = 5000;

const getWsUrl = () => {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
  const host = apiUrl.replace(/^https?:\/\//, '');
  const token = localStorage.getItem('access_token') || '';
  return `${wsProtocol}://${host}/api/ws?token=${token}`;
};

export const useRealtimeStore = create<RealtimeState>((set, get) => {
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const scheduleReconnect = () => {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      const state = get();
      if (!state.connected && !state.ws) {
        state.connect();
      }
    }, WS_RECONNECT_DELAY);
  };

  return {
    connected: false,
    lastUpdate: 0,
    alerts: [],
    ws: null,

    connect: () => {
      const existing = get().ws;
      if (existing && existing.readyState <= WebSocket.OPEN) return;

      const token = localStorage.getItem('access_token');
      if (!token) return;

      try {
        const ws = new WebSocket(getWsUrl());

        ws.onopen = () => {
          set({ connected: true, ws });
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'traffic_update') {
              set({ lastUpdate: Date.now() });
            } else if (data.type === 'config_blocked') {
              set((state) => ({
                alerts: [...state.alerts.slice(-49), data],
                lastUpdate: Date.now(),
              }));
            }
          } catch {
            // ignore non-JSON messages like "pong"
          }
        };

        ws.onclose = () => {
          set({ connected: false, ws: null });
          scheduleReconnect();
        };

        ws.onerror = () => {
          ws.close();
        };

        set({ ws });
      } catch {
        scheduleReconnect();
      }
    },

    disconnect: () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      const ws = get().ws;
      if (ws) {
        ws.close();
      }
      set({ connected: false, ws: null });
    },

    clearAlerts: () => set({ alerts: [] }),
  };
});
