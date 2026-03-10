import { TyreWear } from "@/components/TyreWear";
import { EngineTelemetry } from "@/components/EngineTelemetry";
import { AeroTelemetry } from "@/components/AeroTelemetry";
import { TyreAlertPanel } from "@/components/TyreAlertPanel";
import { PuAlertPanel } from "@/components/PuAlertPanel";
import { AeroAlertPanel } from "@/components/AeroAlertPanel";
import { RaceEngineerPanel } from "@/components/RaceEngineerPanel";
import { DriverRadioInput } from "@/components/DriverRadioInput";
import { useSessionTelemetry, formatLapTime, formatTimeLeft } from "@/hooks/useSessionTelemetry";
import { useTyreTelemetry } from "@/hooks/useTyreTelemetry";
import { usePowerUnitTelemetry } from "@/hooks/usePowerUnitTelemetry";
import { useAeroTelemetry } from "@/hooks/useAeroTelemetry";
import { useRaceEngineerReport } from "@/hooks/useRaceEngineerReport";
import { Flag, Timer, Gauge, Clock } from "lucide-react";

const Index = () => {
  const session = useSessionTelemetry();
  const { tyreAlerts: { alerts: tyreAlerts, activeCount: tyreActiveCount }, tyresReport } = useTyreTelemetry();
  const { puAlerts: { alerts: puAlerts, activeCount: puActiveCount }, puReport } = usePowerUnitTelemetry();
  const { aeroAlerts: { alerts: aeroAlerts, activeCount: aeroActiveCount }, damageReport } = useAeroTelemetry();
  const raceEngineerReport = useRaceEngineerReport();

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
          <AeroAlertPanel alerts={aeroAlerts} activeCount={aeroActiveCount} engineerResponses={damageReport.responses} />
        </div>
      </div>

      {/* Race Engineer */}
      <div className="shrink-0">
        <RaceEngineerPanel report={raceEngineerReport} />
      </div>

      {/* Driver Radio */}
      <div className="shrink-0">
        <DriverRadioInput />
      </div>
    </div>
  );
};

export default Index;
