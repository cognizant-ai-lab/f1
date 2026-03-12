import { useEffect, useRef, useState } from "react";
import type { Alert } from "@/components/AlertBox";

export interface RaceEngineerReportEntry {
  text: string;
  time: string;
}

export interface RaceEngineerReport {
  responses: RaceEngineerReportEntry[];
  alerts: Alert[];
}

const WS_URL = "ws://localhost:8765";
const RECONNECT_INTERVAL_MS = 2000;

export function useRaceEngineerReport(): RaceEngineerReport {
  const [report, setReport] = useState<RaceEngineerReport>({ responses: [], alerts: [] });
  const lastResponseCount = useRef<number>(0);
  const lastAlertCount = useRef<number>(0);
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
          if (msg.raceEngineerReport) {
            const re = msg.raceEngineerReport;
            const serverResponses: RaceEngineerReportEntry[] = re.responses ?? [];
            const serverAlerts: Alert[] = re.alerts ?? [];

            if (serverResponses.length === 0 && serverAlerts.length === 0) {
              lastResponseCount.current = 0;
              lastAlertCount.current = 0;
              setReport({ responses: [], alerts: [] });
            } else {
              const responsesChanged = serverResponses.length !== lastResponseCount.current;
              const alertsChanged = serverAlerts.length !== lastAlertCount.current;

              if (responsesChanged || alertsChanged) {
                lastResponseCount.current = serverResponses.length;
                lastAlertCount.current = serverAlerts.length;
                setReport({
                  responses: serverResponses,
                  alerts: serverAlerts,
                });
              }
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

  return report;
}
