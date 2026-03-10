import { useEffect, useRef, useState } from "react";
import type { Alert } from "@/components/AlertBox";

export interface TyreData {
  surfaceTemp: number;
  innerTemp: number;
  pressure: number;
  wear: number;
  damage: number;
  blisters: number;
  brakeTemp: number;
}

export interface TyreTelemetryData {
  tyres: Record<"fl" | "fr" | "rl" | "rr", TyreData>;
  compound: string;
  compoundVisual: string;
  tyresAgeLaps: number;
  currentLap: number;
  speed: number;
  sessionTime: number;
  totalDistanceM?: number;
  lapDistanceM?: number;
  session?: { trackLengthM?: number };
}

export interface WearHistoryPoint {
  distanceKm: number;
  fl: number;
  fr: number;
  rl: number;
  rr: number;
}

export interface LapBoundary {
  distanceKm: number;
  lapNum: number;
}

interface TyreAlerts {
  alerts: Alert[];
  activeCount: number;
}

export interface TyresReportEntry {
  text: string;
  time: string;
}

export interface TyresReport {
  responses: TyresReportEntry[];
}

const WS_URL = "ws://localhost:8765";
const RECONNECT_INTERVAL_MS = 2000;

const EMPTY_ALERTS: TyreAlerts = { alerts: [], activeCount: 0 };

const WEAR_HISTORY_MIN_DELTA_M = 5;
const MAX_WEAR_HISTORY_POINTS = 2000;

export function useTyreTelemetry(): {
  data: TyreTelemetryData | null;
  tyreAlerts: TyreAlerts;
  tyresReport: TyresReport;
  wearHistory: WearHistoryPoint[];
  lapBoundaries: LapBoundary[];
} {
  const [data, setData] = useState<TyreTelemetryData | null>(null);
  const [tyreAlerts, setTyreAlerts] = useState<TyreAlerts>(EMPTY_ALERTS);
  const [tyresReport, setTyresReport] = useState<TyresReport>({ responses: [] });
  const [wearHistory, setWearHistory] = useState<WearHistoryPoint[]>([]);
  const [lapBoundaries, setLapBoundaries] = useState<LapBoundary[]>([]);
  const lastTyresResponse = useRef<string | null>(null);
  const lastSessionTime = useRef<number>(0);
  const lastLapNum = useRef<number>(0);
  const lastDistanceM = useRef<number>(0);
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
          const sessionTime = typeof msg.sessionTime === "number" ? msg.sessionTime : 0;
          const totalDistanceM = typeof msg.totalDistanceM === "number" ? msg.totalDistanceM : null;
          const currentLap = typeof msg.currentLap === "number" ? msg.currentLap : 0;
          const tyres = msg.tyres;

          if (sessionTime < lastSessionTime.current) {
            lastSessionTime.current = sessionTime;
            lastLapNum.current = 0;
            lastDistanceM.current = 0;
            setWearHistory([]);
            setLapBoundaries([]);
          }
          lastSessionTime.current = sessionTime;

          if (totalDistanceM != null && tyres && typeof tyres.fl?.wear === "number") {
            const distanceDelta = totalDistanceM - lastDistanceM.current;
            const shouldAdd =
              lastDistanceM.current === 0 || distanceDelta >= WEAR_HISTORY_MIN_DELTA_M;
            if (shouldAdd) {
              lastDistanceM.current = totalDistanceM;
              const point: WearHistoryPoint = {
                distanceKm: totalDistanceM / 1000,
                fl: tyres.fl.wear,
                fr: tyres.fr.wear,
                rl: tyres.rl.wear,
                rr: tyres.rr.wear,
              };
              setWearHistory((prev) => {
                const next = [...prev, point];
                return next.length > MAX_WEAR_HISTORY_POINTS ? next.slice(-MAX_WEAR_HISTORY_POINTS) : next;
              });
            }
          }

          if (currentLap > lastLapNum.current && totalDistanceM != null) {
            lastLapNum.current = currentLap;
            setLapBoundaries((prev) => [...prev, { distanceKm: totalDistanceM / 1000, lapNum: currentLap }]);
          }

          setData(msg);
          if (msg.tyreAlerts) {
            setTyreAlerts(msg.tyreAlerts);
          }
          if (msg.tyresReport) {
            if (msg.tyresReport.response === null) {
              lastTyresResponse.current = null;
              setTyresReport({ responses: [] });
            } else if (msg.tyresReport.response !== lastTyresResponse.current) {
              lastTyresResponse.current = msg.tyresReport.response;
              setTyresReport((prev) => ({
                responses: [...prev.responses, { text: msg.tyresReport.response, time: msg.tyresReport.time ?? "" }],
              }));
            }
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

  return { data, tyreAlerts, tyresReport, wearHistory, lapBoundaries };
}
