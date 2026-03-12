import { TyreWear } from "@/components/TyreWear";
import { EngineTelemetry } from "@/components/EngineTelemetry";
import { AeroTelemetry } from "@/components/AeroTelemetry";
import { TyreAlertPanel } from "@/components/TyreAlertPanel";
import { PuAlertPanel } from "@/components/PuAlertPanel";
import { DamageAlertPanel } from "@/components/DamageAlertPanel";
import { RaceEngineerPanel } from "@/components/RaceEngineerPanel";
import { DriverRadioInput } from "@/components/DriverRadioInput";
import { TrackMap } from "@/components/TrackMap";
import { useSessionTelemetry, formatLapTime, formatTimeLeft } from "@/hooks/useSessionTelemetry";
import { useTyreTelemetry } from "@/hooks/useTyreTelemetry";
import { usePowerUnitTelemetry } from "@/hooks/usePowerUnitTelemetry";
import { useAeroTelemetry } from "@/hooks/useAeroTelemetry";
import { useRaceEngineerReport } from "@/hooks/useRaceEngineerReport";
import { Flag, Timer, Gauge, Clock, Info } from "lucide-react";
import { useState, useCallback, useRef, useEffect } from "react";
import type { ReportEntry } from "@/components/ExpandableReportPanel";

const WEATHER_LABELS: Record<number, string> = {
  0: "Clear", 1: "Light Cloud", 2: "Overcast",
  3: "Light Rain", 4: "Heavy Rain", 5: "Storm",
};

const Index = () => {
  const session = useSessionTelemetry();
  const { tyreAlerts: { alerts: tyreAlerts, activeCount: tyreActiveCount }, tyresReport } = useTyreTelemetry();
  const { puAlerts: { alerts: puAlerts, activeCount: puActiveCount }, puReport } = usePowerUnitTelemetry();
  const { aeroAlerts: { alerts: aeroAlerts, activeCount: aeroActiveCount }, damageReport } = useAeroTelemetry();
  const raceEngineerReport = useRaceEngineerReport();
  const [driverMessages, setDriverMessages] = useState<ReportEntry[]>([]);
  const [showSessionInfo, setShowSessionInfo] = useState(false);
  const infoBubbleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showSessionInfo) return;
    const handleClick = (e: MouseEvent) => {
      if (infoBubbleRef.current && !infoBubbleRef.current.contains(e.target as Node)) {
        setShowSessionInfo(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showSessionInfo]);

  const handleDriverSend = useCallback((text: string, time: string) => {
    setDriverMessages((prev) => [...prev, { text, time, source: "driver" as const }]);
  }, []);

  const handleSessionReset = useCallback(() => {
    setDriverMessages([]);
  }, []);

  const sessionType = session?.sessionType ?? "—";
  const trackName = session?.trackName ?? "—";
  const timeLeftStr = session ? formatTimeLeft(session.sessionTimeLeft) : "—";
  const position = session?.carPosition ?? 0;
  const lastLapStr = session ? formatLapTime(session.lastLapTimeMs) : "—";
  const totalLaps = session?.totalLaps ?? 0;

  return (
    <div className="h-screen overflow-hidden bg-background p-3 flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between mb-3 pb-2 border-b border-border/50 shrink-0">
        <div className="flex items-center gap-3">
          <Flag className="h-4 w-4 text-accent" />
          <h1 className="font-display text-sm md:text-base font-bold tracking-wider text-foreground">
            {trackName} — PIT WALL
          </h1>
          <span className="font-display text-[10px] font-bold tracking-wider text-accent bg-accent/10 border border-accent/30 px-2 py-0.5 rounded">
            {sessionType}
          </span>
          <div className="relative" ref={infoBubbleRef}>
            <button
              onClick={() => setShowSessionInfo((v) => !v)}
              className="p-1 rounded border border-border/50 bg-secondary/50 text-muted-foreground hover:text-primary hover:border-primary/50 transition-colors"
            >
              <Info className="h-3.5 w-3.5" />
            </button>
            {showSessionInfo && session && (
              <div className="absolute top-full left-0 mt-2 z-50 bg-card border border-border/50 rounded-md shadow-xl p-3 min-w-[200px]">
                <h3 className="font-display text-[10px] font-bold tracking-widest uppercase text-muted-foreground mb-2">
                  Session Context
                </h3>
                <div className="space-y-1 text-[11px] text-card-foreground">
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Session</span>
                    <span className="font-bold">{sessionType}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Track</span>
                    <span className="font-bold">{trackName}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Weather</span>
                    <span className="font-bold">{WEATHER_LABELS[session.weather] ?? "Unknown"}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Air Temp</span>
                    <span className="font-bold">{session.airTemp}°C</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Track Temp</span>
                    <span className="font-bold">{session.trackTemp}°C</span>
                  </div>
                  {totalLaps > 0 && (
                    <div className="flex justify-between gap-4">
                      <span className="text-muted-foreground">Total Laps</span>
                      <span className="font-bold">{totalLaps}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4 text-[10px] text-muted-foreground uppercase tracking-wider font-display">
          {session && session.sessionTimeLeft > 0 ? (
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3 text-warning animate-pulse" />
              <span className="text-warning">{timeLeftStr} LEFT</span>
            </div>
          ) : totalLaps > 0 ? (
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3 text-primary" />
              <span>{totalLaps} LAPS</span>
            </div>
          ) : null}
          <div className="flex items-center gap-1">
            <Gauge className="h-3 w-3 text-primary" />
            <span>P{position || "—"}</span>
          </div>
          <div className="flex items-center gap-1">
            <Timer className="h-3 w-3 text-primary" />
            <span className="text-primary font-bold">{lastLapStr}</span>
          </div>
        </div>
      </header>

      {/* Telemetry Grid + Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-3 flex-1 min-h-0">
        <div className="flex flex-col gap-2 min-h-0">
          <TyreWear />
          <TyreAlertPanel alerts={tyreAlerts} activeCount={tyreActiveCount} engineerResponses={tyresReport.responses} />
        </div>
        <div className="flex flex-col gap-2 min-h-0">
          <EngineTelemetry />
          <PuAlertPanel alerts={puAlerts} activeCount={puActiveCount} engineerResponses={puReport.responses} />
        </div>
        <div className="flex flex-col gap-2 min-h-0">
          <AeroTelemetry />
          <DamageAlertPanel alerts={aeroAlerts} activeCount={aeroActiveCount} engineerResponses={damageReport.responses} />
        </div>
      </div>

      {/* Bottom: Race Engineer + Driver Radio (left 2/3) | Track Map (right 1/3) */}
      <div className="shrink-0 grid grid-cols-1 lg:grid-cols-3 gap-3 h-[22rem]">
        <div className="lg:col-span-2 flex flex-col gap-2 min-h-0">
          <RaceEngineerPanel report={raceEngineerReport} driverMessages={driverMessages} className="flex-1 min-h-0" />
          <DriverRadioInput onSend={handleDriverSend} onSessionReset={handleSessionReset} />
        </div>
        <div className="min-h-0">
          <TrackMap />
        </div>
      </div>
    </div>
  );
};

export default Index;
