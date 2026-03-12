import { useEffect, useRef, useState } from "react";

export interface SessionData {
  sessionType: string;
  trackName: string;
  totalLaps: number;
  sessionTimeLeft: number;
  sessionDuration: number;
  trackLength: number;
  trackTemp: number;
  airTemp: number;
  weather: number;
  carPosition: number;
  currentLapTimeMs: number;
  lastLapTimeMs: number;
}

const WS_URL = "ws://localhost:8765";
const RECONNECT_INTERVAL_MS = 2000;

/** Format milliseconds as M:SS.mmm */
export function formatLapTime(ms: number): string {
  if (ms <= 0) return "—";
  const totalSeconds = ms / 1000;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toFixed(3).padStart(6, "0")}`;
}

/** Format seconds as MM:SS */
export function formatTimeLeft(seconds: number): string {
  if (seconds <= 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function useSessionTelemetry(): SessionData | null {
  const [data, setData] = useState<SessionData | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    let unmounted = false;

    function connect() {
      if (unmounted) return;

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.session) {
            setData(msg.session);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!unmounted) {
          reconnectTimer.current = setTimeout(connect, RECONNECT_INTERVAL_MS);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  return data;
}
