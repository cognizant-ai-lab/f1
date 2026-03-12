import { ExpandableReportPanel } from "./ExpandableReportPanel";
import type { ReportEntry } from "./ExpandableReportPanel";
import type { RaceEngineerReport } from "@/hooks/useRaceEngineerReport";

interface RaceEngineerPanelProps {
  report: RaceEngineerReport;
  driverMessages: ReportEntry[];
  className?: string;
}

export function RaceEngineerPanel({ report, driverMessages, className }: RaceEngineerPanelProps) {
  const merged: ReportEntry[] = [
    ...driverMessages,
    ...report.responses.map((r) => ({ ...r, source: "engineer" as const })),
  ].sort((a, b) => a.time.localeCompare(b.time));

  return (
    <ExpandableReportPanel
      title="Race Engineer Agent"
      responses={merged}
      emptyMessage="Awaiting engineer reports..."
      className={className}
    />
  );
}
