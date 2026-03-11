import { Circle } from "lucide-react";
import { Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";
import { TelemetryCard, BarGauge } from "./TelemetryCard";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "./ui/chart";
import type { ChartConfig } from "./ui/chart";
import { useTyreTelemetry } from "@/hooks/useTyreTelemetry";
import type { WearHistoryPoint } from "@/hooks/useTyreTelemetry";

const TYRE_LINE_COLORS = { rl: "#ef4444", rr: "#f97316", fl: "#3b82f6", fr: "#22c55e" } as const;

const WEAR_CHART_CONFIG: ChartConfig = {
  distanceKm: { label: "Distance (km)", color: "hsl(var(--muted-foreground))" },
  rl: { label: "Rear Left", color: TYRE_LINE_COLORS.rl },
  rr: { label: "Rear Right", color: TYRE_LINE_COLORS.rr },
  fl: { label: "Front Left", color: TYRE_LINE_COLORS.fl },
  fr: { label: "Front Right", color: TYRE_LINE_COLORS.fr },
};

const TYRE_POSITIONS = [
  { key: "fl" as const, label: "FL" },
  { key: "fr" as const, label: "FR" },
  { key: "rl" as const, label: "RL" },
  { key: "rr" as const, label: "RR" },
];

const MIN_DISTANCE_KM_FOR_PROJECTION = 0.1; // 100 m – start estimating as soon as car has traveled this far

/**
 * Estimate laps until 100% wear using average wear rate over a distance window.
 * With 2+ lap boundaries uses the last full lap; otherwise uses all data so far.
 * Works with less than one lap of data: wear_rate_per_km = Δwear / Δdistance, then
 * wear_per_lap = wear_rate_per_km × lap_length_km, laps_left = (100 − current_wear) / wear_per_lap.
 * Requires at least 100 m of distance span so the rate is meaningful.
 */
function projectedLapsUntil100(
  wearHistory: WearHistoryPoint[],
  lapBoundaries: { distanceKm: number; lapNum: number }[],
  trackLengthM: number,
  currentWear: { fl: number; fr: number; rl: number; rr: number }
): number | null {
  if (wearHistory.length < 2 || trackLengthM <= 0) return null;

  const lapLengthKm = trackLengthM / 1000;
  let startKm: number;
  let endKm: number;

  if (lapBoundaries.length >= 2) {
    startKm = lapBoundaries[lapBoundaries.length - 2].distanceKm;
    endKm = lapBoundaries[lapBoundaries.length - 1].distanceKm;
  } else {
    // Less than one lap: use all data so far (first to last point)
    startKm = wearHistory[0].distanceKm;
    endKm = wearHistory[wearHistory.length - 1].distanceKm;
  }

  const pointsInRange = wearHistory.filter((p) => p.distanceKm >= startKm && p.distanceKm <= endKm);
  if (pointsInRange.length < 2) return null;

  const first = pointsInRange[0];
  const last = pointsInRange[pointsInRange.length - 1];
  const deltaKm = last.distanceKm - first.distanceKm;
  if (deltaKm < MIN_DISTANCE_KM_FOR_PROJECTION) return null;

  const tyrePositions = ["fl", "fr", "rl", "rr"] as const;
  let minLapsLeft: number | null = null;

  for (const t of tyrePositions) {
    const deltaWear = last[t] - first[t];
    const wearRatePerKm = deltaWear / deltaKm;
    const wearPerLap = wearRatePerKm * lapLengthKm;
    if (wearPerLap <= 0) continue;
    const current = currentWear[t];
    if (current >= 100) return 0;
    const lapsLeft = (100 - current) / wearPerLap;
    if (minLapsLeft === null || lapsLeft < minLapsLeft) minLapsLeft = lapsLeft;
  }

  return minLapsLeft;
}

export function TyreWear() {
  const { data, wearHistory, lapBoundaries } = useTyreTelemetry();

  if (!data) {
    return (
      <TelemetryCard
        title="TYRE WEAR"
        icon={<Circle className="h-4 w-4 text-primary" />}
        status="nominal"
      >
        <div className="flex items-center justify-center py-6 text-[10px] text-muted-foreground uppercase tracking-wider font-display">
          Waiting for telemetry…
        </div>
      </TelemetryCard>
    );
  }

  const hasData = wearHistory.length > 0;
  const yMax = hasData
    ? Math.min(100, Math.ceil(Math.max(...wearHistory.flatMap((p) => [p.fl, p.fr, p.rl, p.rr])) / 2) * 2 + 2)
    : 20;

  const trackLengthM = data.session?.trackLengthM ?? 0;
  const currentWear = data.tyres
    ? {
        fl: data.tyres.fl.wear,
        fr: data.tyres.fr.wear,
        rl: data.tyres.rl.wear,
        rr: data.tyres.rr.wear,
      }
    : { fl: 0, fr: 0, rl: 0, rr: 0 };
  const projectedLaps = hasData && trackLengthM > 0
    ? projectedLapsUntil100(wearHistory, lapBoundaries, trackLengthM, currentWear)
    : null;

  return (
    <TelemetryCard
      title="TYRE WEAR"
      icon={<Circle className="h-4 w-4 text-primary" />}
      status="nominal"
    >
      {!hasData ? (
        <div className="flex items-center justify-center py-6 text-[10px] text-muted-foreground uppercase tracking-wider font-display">
          No distance data yet — drive to see wear over distance
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-3 items-stretch">
          <ChartContainer config={WEAR_CHART_CONFIG} className="h-[200px] w-full min-w-0">
            <LineChart
              data={wearHistory}
              margin={{ top: 28, right: 8, bottom: 24, left: 8 }}
            >
              <XAxis
                dataKey="distanceKm"
                type="number"
                tickFormatter={(v) => `${v.toFixed(1)}`}
                domain={["dataMin", "dataMax"]}
                tick={{ fontSize: 10 }}
                label={{
                  value: "Distance (kilometers)",
                  position: "insideBottom",
                  offset: -18,
                  style: { fontSize: 10, fill: "hsl(var(--muted-foreground))" },
                }}
              />
              <YAxis
                domain={[0, yMax]}
                tickFormatter={(v) => `${v}%`}
                label={{ value: "Wear (%)", angle: -90, position: "insideLeft", style: { fontSize: 10 } }}
                tick={{ fontSize: 10 }}
              />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload != null
                        ? `Distance: ${(payload[0].payload as { distanceKm: number }).distanceKm.toFixed(2)} km`
                        : ""
                    }
                    formatter={(value) => <span>{Number(value).toFixed(1)}%</span>}
                  />
                }
              />
              {lapBoundaries.map((b) => (
                <ReferenceLine
                  key={`${b.distanceKm}-${b.lapNum}`}
                  x={b.distanceKm}
                  stroke="hsl(var(--border))"
                  strokeDasharray="2 2"
                  label={{
                    value: `L${b.lapNum}`,
                    position: "top",
                    fontSize: 10,
                    fill: "hsl(var(--muted-foreground))",
                  }}
                />
              ))}
              <Line type="monotone" dataKey="rl" stroke={TYRE_LINE_COLORS.rl} dot={false} strokeWidth={2} name="Rear Left" />
              <Line type="monotone" dataKey="rr" stroke={TYRE_LINE_COLORS.rr} dot={false} strokeWidth={2} name="Rear Right" />
              <Line type="monotone" dataKey="fl" stroke={TYRE_LINE_COLORS.fl} dot={false} strokeWidth={2} name="Front Left" />
              <Line type="monotone" dataKey="fr" stroke={TYRE_LINE_COLORS.fr} dot={false} strokeWidth={2} name="Front Right" />
            </LineChart>
          </ChartContainer>
          <div className="flex flex-col min-w-[140px] sm:min-w-[160px] gap-2 flex-1">
            <div className="shrink-0 flex flex-col items-center justify-center border border-border/50 rounded-md bg-secondary/30 px-3 py-1.5">
              <span className="text-[9px] font-display font-bold tracking-wider text-muted-foreground uppercase">
                Projected Tyre Life (laps)
              </span>
              <span className="font-display text-2xl font-bold tabular-nums text-primary leading-tight">
                {projectedLaps != null && projectedLaps < 999
                  ? projectedLaps < 0
                    ? "—"
                    : projectedLaps.toFixed(1)
                  : "—"}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 min-h-0 flex-1">
              <div className="flex flex-col gap-1 bg-secondary/30 rounded-md border border-border/50 p-2">
                <span className="text-[9px] font-display font-bold tracking-wider text-muted-foreground uppercase">Damage</span>
                {TYRE_POSITIONS.map((p) => (
                  <BarGauge
                    key={p.key}
                    value={data.tyres[p.key].damage}
                    max={255}
                    label={p.label}
                    warn={50}
                    critical={150}
                  />
                ))}
              </div>
              <div className="flex flex-col gap-1 bg-secondary/30 rounded-md border border-border/50 p-2">
                <span className="text-[9px] font-display font-bold tracking-wider text-muted-foreground uppercase">Blisters</span>
                {TYRE_POSITIONS.map((p) => (
                  <BarGauge
                    key={p.key}
                    value={data.tyres[p.key].blisters}
                    max={255}
                    label={p.label}
                    warn={50}
                    critical={150}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </TelemetryCard>
  );
}
