import { useRef, useState, useEffect, useCallback } from "react";
import { Radio, Send } from "lucide-react";

const WS_URL = "ws://localhost:8765";

interface DriverRadioInputProps {
  onSend?: (text: string, time: string) => void;
  onSessionReset?: () => void;
}

function formatSessionTime(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function DriverRadioInput({ onSend, onSessionReset }: DriverRadioInputProps) {
  const [message, setMessage] = useState("");
  const prevSessionTime = useRef<number>(0);
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
          const st = msg.sessionTime ?? 0;
          if (st < prevSessionTime.current) {
            onSessionReset?.();
          }
          prevSessionTime.current = st;
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        if (!unmounted) {
          reconnectTimer.current = setTimeout(connect, 2000);
        }
      };
      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  const send = useCallback(() => {
    const text = message.trim();
    if (!text) return;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ driverMessage: text }));
      onSend?.(text, formatSessionTime(prevSessionTime.current));
      setMessage("");
    }
  }, [message, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    },
    [send],
  );

  return (
    <div className="bg-card border border-primary/20 rounded-md glow-primary overflow-hidden telemetry-grid">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/50 bg-primary/5">
        <Radio className="h-4 w-4 text-primary animate-pulse" />
        <h2 className="font-display text-sm font-bold tracking-widest uppercase text-foreground">
          Driver Radio
        </h2>
      </div>
      <div className="flex items-center gap-2 p-3">
        <span className="font-display text-[10px] font-bold tracking-wider text-accent shrink-0">
          FERNANDO &gt;
        </span>
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message to the race engineer..."
          className="flex-1 bg-secondary/50 border border-border/50 rounded px-3 py-2 text-[11px] text-card-foreground placeholder:text-muted-foreground/50 outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/30"
        />
        <button
          onClick={send}
          disabled={!message.trim()}
          className="shrink-0 p-2 rounded border border-border/50 bg-secondary/50 text-muted-foreground hover:text-primary hover:border-primary/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
